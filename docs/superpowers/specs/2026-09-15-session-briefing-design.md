# Session Briefing — design

Date: 2026-09-15. Status: approved in brainstorm, awaiting implementation plan.

## Problem

A fresh Claude Code session holds a large, partly documented context (CLAUDE.md
hierarchy, auto-memory index, skills catalog, hook output) but never tells the
user what it holds. Nothing native or third-party renders a human-readable
"here is what I know about you, this project, and where we left off" before
work begins. Surveyed 16 tools (claude-mem, Basic Memory, Letta proxy,
statusline projects, ccusage, handoff tools); each covers one slice. Orca has
no session-lifecycle hook. Claude Code cannot produce an assistant turn without
a user prompt, and SessionStart `additionalContext` is not shown to the user.

## Goal

At session start, the agent's first turn is a ≤250-word greeting that
separates what it was *given* (its actual startup context) from what was
*looked up* (project and history state), with zero cost to the working agent
beyond a few hundred tokens.

## Non-goals

- gbrain queries (MCP currently unreliable).
- Global session scans (16k JSONLs; project-scoped only).
- An Orca render surface. Transcript only, until proven too long.
- Plan-file (`~/.claude/plans/`) inclusion: not loaded at startup, untied to a project.
- `--add-dir` and outputStyle handling beyond recording the setting value.

## Architecture

Three units in `skills/briefing/`, installed by symlink like sibling skills.

```
packet.sh   ──► ~/.claude/briefings/<slug>/packet.md
summarize.sh ─► ~/.claude/briefings/<slug>/<hash>.md   (cache)
SKILL.md    ──► /briefing prints the cached greeting verbatim
```

A SessionStart hook (matcher `startup|resume`) runs `packet.sh` synchronously
and `summarize.sh` detached. Hosts deliver the first prompt `/briefing`
(terminal alias, Orca `--prompt`, or the user types it).

## Unit 1: packet.sh

Reads SessionStart JSON on stdin. Deterministic, no network, <1 s. Writes
seven sections, each byte-capped, total ≤48 KB. Every section is labelled
`given` (in a fresh agent's context per Claude Code docs) or `looked-up`
(added by us).

| # | Section | Source | Label |
|---|---------|--------|-------|
| 1 | Session facts | date, cwd, matcher, model, session_id, host (`claude-desktop` via `CLAUDE_CODE_ENTRYPOINT`, `orca` via `ORCA_PANE_KEY`, else `terminal`) | given |
| 2 | Identity & rules | managed policy CLAUDE.md if present; `~/.claude/CLAUDE.md`; project `CLAUDE.md`, `.claude/CLAUDE.md`, `CLAUDE.local.md`; `@path` imports expanded ≤4 hops relative to the importing file, backticked refs ignored; `~/.claude/rules/` and `.claude/rules/` unconditional rules in full, path-scoped rules by name + `paths:` | given |
| 3 | Memory | `MEMORY.md` from `~/.claude/projects/<slug>/memory/`, cut at 200 lines or 25 KB; topic filenames only. Slug from `git rev-parse --show-toplevel` (worktrees share), cwd outside git. Verify dir exists | given |
| 4 | Config digest | user + project + local settings merged: model, effort, outputStyle if set, hook events carrying a custom command (names only), enabled plugins; MCP server names from `~/.claude.json` and project `.mcp.json`; project `.claude/agents` and `.claude/skills` names; total skill count plus names of user-authored skills | given |
| 5 | Project state | branch, ahead/behind, dirty count, last 5 commits oneline, worktree count; `orca worktree current --json` with 2 s timeout | looked-up |
| 6 | Recent sessions | 3 newest top-level JSONLs in the project dir, excluding current session and `subagents/`; per session: mtime, `custom-title`, `last-prompt` (≤200 chars), unfinished items from `~/.claude/todos/<session>*.json` | looked-up |
| 7 | Open threads | newest `.claude/*` file matching handoff, context-save, SIDEQUESTS (first 40 lines); newest spec/plan filename under `docs/superpowers/` | looked-up |

**Scrub.** Applied to the whole packet before write: Anthropic, OpenAI,
GitHub, AWS, Slack token patterns; `key|token|secret|password` followed by
`=` or `:` and a value; bearer headers. Replaced with `[REDACTED]`. Env vars
are never read. `obsidian-claude-daily`'s sanitizer is the reference regex set.

## Unit 2: summarize.sh

1. Hash sections 2–7 (section 1 changes every launch).
2. Cache hit at `<slug>/<hash>.md` → exit 0.
3. Miss → one headless call, output ≤250 words, written with a header line:
   generated-at, backend, packet hash, packet bytes, elapsed, cost if reported.
4. Backend by `BRIEFING_BACKEND`: `claude` (Haiku, default) or `codex` (Luna).

**Prompt template** (`prompt.md`): six blocks — who you are, rules that bind
me, project now, last time, open threads, what I don't know. Each block
carries its given/looked-up label. No claim not present in the packet.

**Recursion guard.** The headless call is a Claude Code session; the
SessionStart hook would fire inside it. Guards: hook exits 0 immediately when
`BRIEFING_NESTED=1`; the call uses `--system-prompt` (replacing the default),
tools disabled, scratch cwd, no session persistence, pinned model, one turn.
Follows `headless-claude-hygiene`.

**Failure.** 60 s timeout. On failure the cache file holds a single error line;
`/briefing` falls back to sections 5–7 raw (no model needed).

## Unit 3: /briefing skill

- Default: wait ≤30 s for the cache file, print verbatim as the first turn.
- `--refresh`: rerun packet + summarize synchronously.
- `--raw`: print the packet.
- `--self`: Arm A. The active agent reads the packet and writes the greeting
  itself. This flag is the A/B switch.

## Hook

Added to `~/.claude/settings.json` SessionStart, matcher `startup|resume`,
alongside the existing patch-superpowers hook. On cache hit it injects the
greeting as `additionalContext` with one instruction: present verbatim when
the first message is `/briefing` or a bare greeting. On miss it injects
"briefing is generating; /briefing will present it." Never blocks.

## Delivery per host

| Host | First turn |
|------|-----------|
| Terminal | `claude "/briefing"` alias, or typed |
| Orca | `orca worktree create --agent claude --prompt "/briefing"`; `orca terminal create --command 'claude "/briefing"'`; orca-config quick-command |
| Claude desktop | user types `/briefing` or any greeting (no launch-prompt control) |

## Tests (one each, no framework)

1. `packet.sh` self-check: plant a fake token in a fixture CLAUDE.md, assert
   `[REDACTED]`, all seven section headers present, size under cap.
2. Nesting check: run `summarize.sh` with the hook installed, assert exactly
   one summarizer process.
3. Fidelity diff: fresh headless agent lists every fact it holds about the
   user and project with source; diff against sections 2–4. Any one-sided
   fact is a packet bug. Rerun on CLI version change (assembly layer drifts).

## A/B (after build)

`/ab-experiment`, arms `/briefing` vs `/briefing --self`. Binary rubric graded
by Codex (cross-family): every claim traceable to packet; current branch
named; last session named; ≤250 words; states what it does not know.
Metrics: working-agent context tokens at turn 1, wall time to greeting.

## Known-surface notes (Sept 2026 docs)

- Documented at startup: CLAUDE.md hierarchy + imports, unconditional rules,
  MEMORY.md 200 lines/25 KB, skill frontmatter, MCP tool names (schemas
  deferred), plugins, `.claude/agents`, SessionStart hook output.
- Closed: system prompt text, system-reminder wrapping, ordering, hook
  output truncation (10 k chars contested).
- `/context` is the only real token breakdown and is interactive-only.
- `CLAUDE_CODE_SESSION_ID` is exported to hooks under Claude desktop; the
  hook JSON carries `session_id` regardless.
