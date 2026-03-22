# Handoff Skill — v0.2 Design Spec

> **Status:** Reviewed (blockers fixed)
> **Date:** 2026-03-21
> **Location:** `handoff/`
> **Prior art:** claude-handoff v0.1 (files.zip) — evaluated and found non-functional against real Claude Code session format. This spec is a ground-up redesign.

---

## Problem

Claude Code's "plan then build" workflow wastes context. A planning session consumes significant context window on exploration, architectural debate, and decision-making. By the time the plan is approved, the remaining context is shallow for implementation.

The current workarounds (manual HANDOFF.md, `/compact`, copy-pasting) are lossy, manual, and break flow. No existing tool automates the plan-detect → extract → fresh-session pipeline.

## Solution

A Claude Code skill (`/handoff`) that reads the current session's transcript, extracts structured context (plan, decisions, negative knowledge, constraints), writes a handoff document, and presents the launch command for a fresh build session.

The key insight: **Claude itself is the extraction engine.** Instead of brittle regex heuristics (v0.1's approach), the skill uses Claude's reasoning to identify plans, decisions, and constraints from conversational transcripts. Extraction prompts live in separate files for iterative refinement via ralph-loop.

---

## Architecture

```
User types /handoff
       │
       ├─ Phase 1: Locate & Preprocess (Bash + Python)
       │   ├─ Derive session JSONL path from $PWD encoding
       │   ├─ Python script extracts conversation text + thinking blocks
       │   │   (strips progress, tool_results, queue-ops, system entries)
       │   │   Thinking blocks: full for last 60% of session, stripped for first 40%
       │   └─ Also captures: file paths from tool_use blocks, git state
       │
       ├─ Phase 2: Extract (Claude reads condensed transcript)
       │   ├─ Reads prompts/extract.md for extraction instructions
       │   ├─ Identifies the approved plan
       │   ├─ Extracts decisions + reasoning (flags [FRAGILE] from thinking blocks)
       │   ├─ Extracts negative knowledge (tried & failed / ruled out)
       │   ├─ Extracts constraints + conversational agreements
       │   └─ Derives next steps in dependency order
       │
       ├─ Phase 3: Knowledge Routing
       │   ├─ Ephemeral → handoff document (~800 tokens)
       │   ├─ Project-durable → suggested CLAUDE.md additions (with user approval)
       │   └─ User-durable → suggested memory updates
       │
       ├─ Phase 4: Generate & Write
       │   ├─ Assembles structured markdown handoff document
       │   ├─ Writes to .claude/handoffs/<timestamp>-<slug>.md (slug from git branch)
       │   ├─ Updates latest.md symlink
       │   └─ Logs generation event to log.jsonl
       │
       └─ Phase 5: Present & Launch
           ├─ Prints diagnostics (section counts, token estimate)
           ├─ Presents CLAUDE.md convention suggestions for approval
           └─ Prints launch command: claude --append-system-prompt-file <path>
```

---

## Real JSONL Format (Verified)

Claude Code session logs use this schema (NOT the v0.1 fixture format):

| Aspect | Reality |
|--------|---------|
| Entry types | `user`, `assistant`, `progress`, `system`, `queue-operation`, `file-history-snapshot`, `pr-link`, `last-prompt` |
| User messages | `type: "user"`, `message.content` is string OR array of content blocks |
| Assistant messages | `type: "assistant"`, `message.content` is always an array of `{type: "text"}`, `{type: "thinking"}`, `{type: "tool_use"}` blocks |
| Tool calls | Embedded inside assistant `message.content` arrays as `{type: "tool_use", name: "Bash", input: {...}}` |
| Tool results | Embedded inside user `message.content` arrays as `{type: "tool_result", tool_use_id: "...", content: "..."}` |
| Session metadata | `sessionId` on every entry, `slug` field for session name, no summary entry |
| Common fields (user/assistant/system/progress only) | `sessionId`, `timestamp`, `cwd`, `version`, `gitBranch`, `uuid`, `parentUuid` — other entry types have varying field sets |

Session files live at: `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`
- Encoded CWD replaces both `/` and `.` with `-` (e.g., `/Users/foo/.worktrees/bar` → `-Users-foo--worktrees-bar`)
- No `sessions/` subdirectory
- Only top-level `*.jsonl` files — do NOT recurse into `<session-id>/subagents/` subdirectories

---

## Handoff Document Format

Six sections, imperative voice, 600-1000 token target. Every line must pass: *"Would a fresh session make a materially different choice without this?"*

```markdown
# Handoff: <slug>
> Generated: <timestamp> | Session: <id> | Branch: <branch>

## Summary
2-3 sentences. What was accomplished, where it stopped.

## Decisions
- **<topic>:** <choice> over <alternatives>. <reasoning> [FRAGILE]?
(Only decisions that affect how the next session proceeds.
[FRAGILE] flag when thinking blocks reveal Claude was uncertain.)

## Do Not Retry
- <what was tried/considered> — <why it failed or was ruled out>
(Highest-value section. Prevents re-attempting known dead ends.)

## Constraints
- <agreement or boundary not captured in code>
(Conversational agreements: "no new deps", "defer X until Y", etc.)

## Next Steps
1. <first task> — depends on nothing
2. <second task> — depends on #1 because <reason>
(Dependency-ordered. Concrete enough to execute without discovery.)

## Key Files
- `path/to/file` — <one-line annotation>
(Only files the next session needs to touch or reference.)
```

---

## Cross-Session Knowledge Routing

During extraction, Claude categorizes each insight into three buckets:

**Ephemeral** → handoff document
- Session-specific implementation details, plan steps, file references

**Project-durable** → suggested CLAUDE.md additions (requires user approval)
- Conventions established this session that apply to ALL future work
- Test: "Would this still be useful 2 weeks from now in an unrelated session?"
- Dedup check against existing CLAUDE.md content before suggesting

**User-durable** → memory system updates
- Observations about user preferences, expertise, working style
- Feeds the auto-memory system for future conversations

The skill presents durable suggestions separately after writing the handoff:
```
Handoff written to .claude/handoffs/20260321-auth-service.md

Suggested CLAUDE.md additions (3 conventions established this session):
  + New auth modules use Result<T, AuthError> pattern, not thrown exceptions
  + All auth code scoped to src/auth/ directory
  + bcrypt for password hashing

Apply these? [y/n/edit]
```

For `edit`: present each suggestion individually with y/n/edit per item, where edit allows inline text replacement before appending to CLAUDE.md.

---

## Preprocessing Pipeline

### Why Preprocess

Real session files are 1-61MB. Content distribution varies significantly by session type:

| Category | Code-heavy session | Paste-heavy session | Mixed session |
|----------|-------------------|--------------------|--------------|
| Progress/queue/system | ~7% | ~28% | ~7% |
| Tool results (in user entries) | ~78% | ~14% | ~80% |
| User human text | ~11% | ~52% | ~1% |
| Assistant text | ~0.3% | ~0.6% | ~0.4% |
| Thinking blocks | ~0.4% | ~1% | ~4% |

The preprocessor filters to conversation text + thinking blocks. However, individual user messages can be enormous (500KB+ when users paste specs or code). Without a size cap, preprocessed output can exceed the context window.

### Size Budget for Extraction Input

**Hard cap: 150K tokens (~600KB) of preprocessed output.** If the condensed transcript exceeds this:
1. Keep ALL messages from the last 40% of the session in full
2. Truncate individual user messages over 2000 characters to first/last 200 chars with `[truncated — N chars omitted]`
3. If still over budget, progressively drop early-session messages (oldest first)

This ensures the extraction always receives the most decision-relevant portion of the conversation.

### What Gets Kept

| Content | First 40% of session | Last 60% of session |
|---------|---------------------|---------------------|
| User text messages | Keep | Keep |
| Assistant text blocks | Keep | Keep |
| Thinking blocks | **Strip** (exploratory) | **Keep** (decision-crystallizing) |
| Tool use file paths | Keep (paths only) | Keep (paths only) |
| Tool results | Strip | Strip |
| Progress/system/queue | Strip | Strip |

### Thinking Block Value

Thinking blocks contain Claude's internal deliberation — often richer than the visible response:
- Rejected approaches Claude didn't surface (negative knowledge)
- Risk assessments weighed internally
- Architectural reasoning chains trimmed from the response
- Uncertainty signals that inform [FRAGILE] flagging
- Observations about user preferences (feeds memory updates)

Recency weighting (last 60% full, first 40% stripped) captures the reasoning that matters while dropping early exploration noise.

### Session File Discovery

```
1. Get git root via `git rev-parse --show-toplevel`
2. Compute encoded path: replace both / and . with - in the git root path
3. Look for top-level *.jsonl in ~/.claude/projects/<encoded-git-root>/
   (do NOT recurse into subdirectories — those are subagent sessions)
4. Pick most recently modified file (current session was just written to)
5. Fallback: try $PWD encoding if different from git root
6. Emergency fallback: scan all project dirs for JSONL modified in last 10 seconds
```

---

## Extraction Prompt Design

The extraction prompt lives at `prompts/extract.md` — separate from SKILL.md for independent ralph-loop iteration.

### Core Principles

1. **Prime for specific categories** — ask for Decisions, Do Not Retry, Constraints, Next Steps by name. Never ask to "summarize the session."
2. **Instruct for compression** — "Be ruthlessly selective. A handoff with 20 minor decisions buries the 3 that matter."
3. **Anti-hallucination guardrail** — "Only extract what was explicitly discussed. Do not infer decisions that were not stated. Do not fabricate alternatives."
4. **[FRAGILE] detection** — "If thinking blocks reveal uncertainty about a decision, flag it as [FRAGILE]."
5. **Output template** — provide the exact markdown structure. Don't let Claude choose its own format.
6. **Token budget** — "Target ~800 tokens. If the session was long, prioritize recency and relevance over completeness."

### Convention Detection Prompt

Lives at `prompts/conventions.md`. Separate extraction pass focused on:
- Patterns that apply to ALL future work (not just next session)
- CLAUDE.md dedup check (read existing file first)
- User preference observations for memory system

---

## File Structure

```
handoff/
  SKILL.md                      ← Orchestration logic (stable)
  prompts/
    extract.md                  ← Primary extraction prompt (ralph-loop target)
    conventions.md              ← Convention/preference detection (ralph-loop target)
  scripts/
    preprocess.py               ← JSONL preprocessor (~50 lines Python)
```

### The `prompts/` Convention

Reusable pattern across the entire skills repo. Any skill that transforms unstructured input into structured output places its core prompts in `prompts/` so ralph-loop can target them independently:

```
handoff/prompts/extract.md          ← ralph-loop target
  handoff/prompts/conventions.md      ← ralph-loop target
grill-me/prompts/interrogate.md     ← future ralph-loop target
fix-pr-reviews/prompts/triage.md    ← future ralph-loop target
```

This convention enables:
- Prompt iteration without touching skill orchestration logic
- Version-controlled prompt diffs over time
- Shared ralph-loop infrastructure across all skills
- Round-trip verification testing (generate output → feed to fresh consumer → measure)

---

## Output & Storage

```
.claude/
  handoffs/
    20260321-143000-auth-service.md   ← Timestamped handoff
    latest.md                          ← Symlink to most recent (integration point)
    log.jsonl                          ← Generation events (passive metrics)
  handoff.config.json                  ← Optional config overrides
```

- Slug derived from git branch name, sanitized to lowercase-alphanumeric-dashes (e.g., `feat/auth-service` → `auth-service`). Falls back to session `slug` field if on main/master.
- `.claude/handoffs/` added to `.gitignore` (ephemeral session artifacts)
- `latest.md` symlink is the API contract for future enrichment tools
- `log.jsonl` logs generation events, one JSON line per handoff:
  `{"ts":"2026-03-21T14:30:00Z","file":"20260321-143000-auth-service.md","tokens":780,"sections":{"decisions":5,"doNotRetry":3,"constraints":4,"nextSteps":8},"sessionDuration":"47m","conventions":3}`
- Timestamped files retained for history review

---

## Launch Mechanism

The skill writes the handoff file and presents:

```
Handoff written to .claude/handoffs/20260321-143000-auth-service.md
  Sections: 5 decisions, 3 do-not-retry, 4 constraints, 8 next steps
  Token estimate: ~780

To start the build session:
  claude --append-system-prompt-file .claude/handoffs/20260321-143000-auth-service.md

Or in a new tmux window:
  tmux new-window "claude --append-system-prompt-file .claude/handoffs/20260321-143000-auth-service.md"
```

`--append-system-prompt-file` injects the handoff as additional system context while preserving CLAUDE.md, hooks, and all session defaults. If this flag is unavailable in the user's CLI version, fallback to: `claude --append-system-prompt "$(cat .claude/handoffs/<file>.md)"` (inline string variant). The skill should test which form works and present the correct command.

The skill does NOT auto-launch. The user copy-pastes the command. This avoids:
- Environment-dependent terminal spawning
- Surprising behavior
- The v0.1 shell injection vulnerabilities from string-interpolated execSync

---

## Security Considerations (Lessons from v0.1 Evaluation)

| Risk | Mitigation |
|------|------------|
| Secret leakage into handoff | Extraction prompt explicitly instructs: "Do NOT include API keys, passwords, connection strings, or secrets. If a decision references a secret, describe the decision without the value." |
| Shell injection via paths | No `execSync` with string interpolation. Preprocessing script receives paths as arguments, not shell-interpolated. |
| Unbounded memory | Preprocessing script checks file size. Files >100MB get tail-truncated to last 60% before processing. |
| Settings.json corruption | Skill doesn't modify settings.json. No hook registration needed — it's a skill, not a hook. |
| macOS grep -P incompatibility | No shell script fallbacks. Python preprocessor handles all parsing. |

---

## What's Deferred to claude-context-guard

| Capability | Rationale |
|------------|-----------|
| UserPromptSubmit hook router | Different trigger mechanism. Handoff is skill-invoked, not hook-invoked. |
| Per-prompt enrichment | Different problem — within-session context, not cross-session. |
| Ambiguity detection | Requires its own scoring/intervention logic. Ship after handoff proves value. |
| Handoff staleness detection | Needs usage data. Log consumption events first, build rules from observed patterns. |
| Cross-session enrichment (enricher reads latest.md) | Requires both handoff and enricher to exist independently. `latest.md` symlink is the passive integration point. |
| CLAUDE.md auto-injection | Let users manually reference handoff until ergonomics are proven. |

---

## Ralph-Loop Refinement Strategy

The extraction prompts are the primary refinement targets. The `prompts/` directory convention enables this across all skills.

### For handoff specifically:

| Target | Pass/Fail Criteria |
|--------|-------------------|
| `prompts/extract.md` | Handoff captures decisions a human reviewer confirms. "Do Not Retry" lists actual failed attempts. Token count 600-1000. |
| `prompts/conventions.md` | Durable conventions have <20% false positive rate. No duplicates with existing CLAUDE.md. |
| `scripts/preprocess.py` | Extract from raw vs preprocessed → same handoff output. Processing time <1s for 100MB files. |
| Round-trip verification | Feed handoff to fresh session → it avoids listed dead ends and follows plan without redundant questions. |

### Reusable pattern (applies to all skills):

Any skill with a `prompts/` directory can use the same ralph-loop infrastructure:
1. Build fixture set from real data
2. Define objective pass/fail criteria
3. Ralph-loop iterates: modify prompt → run against fixtures → evaluate → repeat
4. This should become a first-class reusable tool/skill in the repo

---

## Competitive Landscape

| Existing Solution | What It Does | Gap Handoff Fills |
|-------------------|-------------|-------------------|
| Manual HANDOFF.md | User asks Claude to write summary | Automated, structured, consistent |
| `/compact` | Compresses conversation within session | Lossy, no cross-session transfer |
| `--continue` / `--resume` | Restores full session history | Full context consumed, not fresh |
| claude-context-handoff-skill | Cross-repo context transfer | Different problem (repo A → repo B) |
| Black Dog Labs Protocol | MCP-based structured handoff | Concept/blog, not shipped |
| cli-continues | Cross-tool session transfer | 14 tools, but no extraction/compression |

No existing tool does: **automatic plan-detect → structured extract → fresh-session launch.**

Market validation: 976 HN points on plan/execution separation article. 10+ open GitHub issues on context transfer. Zero official Anthropic responses.

---

## Allowed Tools

```yaml
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
```

No Agent, WebFetch, or WebSearch needed. The skill is self-contained.
