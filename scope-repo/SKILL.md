---
name: scope-repo
description: Unified codebase planning — spawns 4-9 analyst agents to scan a repo in parallel, interviews the maintainer using real findings, validates scope, and outputs a prioritized ROADMAP.md plus GitHub Issues. Requires Agent Teams enabled.
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash
  - Agent
  - AskUserQuestion
  - WebSearch
  - WebFetch
---

# scopework v3 — Unified Codebase Planning

Single-session pipeline: cold repo to actionable roadmap. Four phases — Reconnaissance, Interview, Scope Validation, Output — all in one Claude Code session. Analysts spawned in Phase 1 stay alive and are resumed in Phases 2-3. Supports cached briefings to skip reconnaissance.

## Prerequisites

- Claude Code CLI with Agent Teams enabled: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in settings.json env
- Opus 4.6 model access
- Run from inside a git repo
- `gh` CLI authenticated (optional — needed for GitHub Issues output)

## Session Setup

When invoked, determine session context:

1. Set `SESSION_DIR` to a temp workspace: `/tmp/plan-session-<timestamp>/`
2. Create subdirectories: `briefings/`, `interview/`, `output/`
3. Set `REPO_ROOT` to the git repo root
4. Set `REPO_NAME` to the repo directory name
5. Check if `gh` CLI is available

Ask the user:
- "Do you have prior briefings to reuse? (path or 'no' for fresh analysis)"
- "Enable quick win execution? (trivial fixes before planning)"
- "Create GitHub Issues at the end? (requires gh CLI)"

## Session Workspace

```
{SESSION_DIR}/
├── briefings/          # Phase 1: analyst briefings
├── interview/
│   └── decisions.md    # Phase 2: tracked decisions + work items
└── output/
    └── ROADMAP.md      # Phase 4: final plan
```

---

## Phase 1: Reconnaissance (parallel analysts, 2-5 min)

### Briefings Shortcut

If the user provides a briefings directory:
- **Skip analyst spawning entirely.** Read all existing briefings from the provided directory.
- Copy briefings to `{SESSION_DIR}/briefings/` for the session record.
- Tell user: "Using prior analysis. Skipping reconnaissance."
- **Important:** Analysts are NOT available for resume in Phase 2/3 when using cached briefings. Work from the briefings alone — no live follow-up queries.

If no briefings provided, run Phase 1 as normal (spawn analysts).

### Pre-Spawn Inspection

Before spawning any analysts, the lead MUST inspect the repo (~30 sec):

1. Read `package.json` or equivalent manifest — what does this project do?
2. Check for AI/LLM indicators: `@anthropic-ai/sdk`, `openai`, prompt files, model calls → add **prompt-analyst**
3. Check for generated output: `output/`, `dist/`, `build/`, rendered content → add **output-analyst**
4. Check for API/service indicators: route definitions, endpoint handlers, OpenAPI specs → add **api-analyst**
5. Check for data pipelines: ETL scripts, data transforms, schema migrations → add **data-analyst**
6. Check for UI/client layer: React/Vue/Svelte components, CSS files, HTML templates → add **ux-analyst**

Spawn ALL core analysts in parallel, plus any domain analysts the inspection warrants.

### Lead Agent (you)

- Perform pre-spawn inspection before spawning analysts
- Never start the interview until ALL briefing files exist
- Answer from briefings when possible — only resume analysts for fresh analysis
- Track every decision in `{SESSION_DIR}/interview/decisions.md` during the interview
- If a teammate query takes >30 sec, note as "needs verification" and move on

### Core Analysts (always spawn)

**arch-analyst** — Architecture, module boundaries, dependency graph, coupling hotspots.
Startup: Analyze directory tree, package configs, import graphs, module boundaries. Identify coupling hotspots. For sub-projects/examples: map their dependencies on the main codebase. Write to `{SESSION_DIR}/briefings/architecture.md`.

**quality-analyst** — Test coverage, CI/CD, code quality, lint configuration.
Startup: Analyze test directories, CI configs, coverage reports. Identify untested critical paths, missing integration tests. Write to `{SESSION_DIR}/briefings/quality.md`.

**dx-analyst** — Developer experience, documentation, onboarding, tooling.
Startup: Read README, CONTRIBUTING, onboarding docs, dev scripts. Evaluate time-to-first-contribution friction. For sub-projects/examples: assess completeness and readiness. Write to `{SESSION_DIR}/briefings/developer-experience.md`.

**debt-analyst** — Technical debt, deprecated patterns, dependency health, code churn.
Startup: Scan for TODOs/FIXMEs/HACKs, deprecated APIs, pinned old deps, dead code. Check git log for high-churn files. Write to `{SESSION_DIR}/briefings/tech-debt.md`.

### Domain Analysts (spawn based on inspection)

**prompt-analyst** — When repo uses AI/LLM APIs, system prompts, or prompt templates.
Find all prompt files, map prompt chains, evaluate structure quality and configurability. Write to `{SESSION_DIR}/briefings/prompt-engineering.md`.

**output-analyst** — When repo generates content, artifacts, or transformed output.
Read actual generated output. Evaluate quality, accuracy, structure, tone consistency. Write to `{SESSION_DIR}/briefings/output-quality.md`.

**api-analyst** — When repo exposes HTTP/gRPC/WebSocket APIs.
Map all endpoints, assess naming consistency, error handling, auth, versioning. Write to `{SESSION_DIR}/briefings/api-design.md`.

**data-analyst** — When repo has ETL pipelines, data transforms, or schema migrations.
Map data flows, assess schema design, migration patterns, data validation. Write to `{SESSION_DIR}/briefings/data-pipeline.md`.

**ux-analyst** — When repo has a client/UI layer (React, Vue, Svelte, HTML/CSS frontend).
Assess visual quality, interaction patterns, component architecture, CSS organization, responsive design, accessibility basics. Evaluate whether the UI achieves its stated goals. For repos with replay/demo/showcase features: assess the visual experience from a user's perspective. Write to `{SESSION_DIR}/briefings/ux-design.md`.

### All Analysts: Shared Rules

- On follow-up queries: re-read your briefing before answering. Respond with structured findings, not freeform prose.
- Write fallback: if the Write tool is denied, output the complete briefing as your response text so the lead can write it. Do not retry.

### Briefing Format

All briefings MUST use this structure. Keep each under 3000 words.

```markdown
# {Area} Briefing — {repo-name}
Generated: {timestamp}

## One-Line Summary
{Single sentence: the most important finding}

## Key Metrics
- {metric}: {value}
(quantify: file counts, line counts, dependency counts, coverage %)

## Top Findings (ranked by impact, max 5)
1. **{finding}** — {1-2 sentence explanation with specific files/modules}

## Risk Zones
{modules, files, or patterns posing highest risk for future work}

## Quick Wins
{low-effort, high-value improvements doable in a day}

## Open Questions for the Maintainer
{2-3 questions where analyst needs human context}
```

### Follow-Up Query Response Format

```
QUERY: {restate what was asked}
CONFIDENCE: high | medium | low
FINDINGS:
- {specific finding with file/line references}
RISK ASSESSMENT: {if applicable}
SUGGESTED FOLLOW-UP QUESTION: {optional}
```

---

## Phase 1.5: Quick Win Execution (optional, 5-15 min)

Only runs when the user opted in. Runs after reconnaissance, before the interview.

1. Read all briefings and identify items that are: (a) under 30 minutes of work, (b) zero risk of breaking anything, (c) clearly beneficial (pin deps, delete dead code, fix typos, add missing config).
2. Present the list: "I found {N} quick wins I can execute right now before the interview: [list]. Should I do them?"
3. If user approves, execute each quick win (actual code changes — this is the ONE exception to the "no source modifications" rule).
4. Run tests after each change to confirm no regressions.
5. Commit changes if tests pass (ask user first).
6. Update mental model — these items are now done, not planned.

If user declines or quick wins not enabled, skip to Phase 2.

---

## Phase 2: Interview (lead + analysts on-call, 10-20 min)

The interview is the product. Five phases, up to 15 questions, with unlimited follow-ups for clarity.

### Phase 2a: Current Pain & Near-Term Goals (2 questions)
- "What's blocking you most right now?"
- "What do you need to ship in the next 1-3 releases?"

### Phase 2b: Findings-Driven Negotiation (3-5 questions)

Every question MUST cite a specific briefing finding.

- Present finding, explain impact, ask for decision: "The analysis shows {finding with file refs}. This affects {impact}. Address now, defer, or irrelevant?"
- Surface conflicts between briefings: "Architecture says X, but debt analysis shows Y — which is the real story?"
- Pressure-test priorities: "If we do that, {tradeoff}. Still worth it?"
- Never accept "both" — force a rank: "I need you to pick one. If you could only ship one this week, which?"

**Priority ordering for questions.** When selecting which findings to present:
1. Product/output quality issues (from domain analysts) — present first
2. User-facing concerns (DX, onboarding, documentation gaps) — present second
3. Structural/architectural issues (god files, coupling) — present ONLY if user raises them or they directly block a stated priority. Do not lead with "your processor.ts is too big" unless the user's goals require changing it.

**Discovery branching.** When the user reveals a significant new capability, architectural direction, or product pivot during the interview:
1. Pause the normal interview flow.
2. Say: "That's a significant direction — let me spend 2-3 focused questions designing this with you before we continue."
3. Conduct a mini design session: what does it need to do? what are the architectural options? what's the build-vs-buy tradeoff?
4. Resume the normal interview flow with the new capability factored into remaining questions.
5. These branching questions count toward the 15-question cap but the lead should reallocate budget from later phases if needed.

### Phase 2c: Design Decision Resolution (2-4 questions)

When a briefing finding implies a design choice, present options and get an answer NOW.

Format: "I see two approaches: (A) [option] — [tradeoff]. (B) [option] — [tradeoff]. Which fits your situation?"

Track every decision. These go into the plan as RESOLVED, not "open questions."

### Phase 2d: Work Item Co-Creation & Sequencing (2-3 questions)

As priorities emerge, propose concrete work items in real-time:
- "That's a work item: '{title}'. I'm calling it WI-{XX}. It depends on WI-{YY}. Sound right?"
- User can adjust scope, rename, or push back. The list is co-created.
- After all items identified, propose execution waves and ask user to confirm/adjust:
  "Here's how I'd sequence this: Wave 1 is [items]. Wave 2 is [items]. Does this order match your instinct?"

### Phase 2e: Reality Check (1 question)

Summarize: resolved decisions, work items, proposed sequence.
"Does this match? Anything wrong or missing?"

### Interview Rules

**Question budget:** Maximum 15 questions across all phases. Follow-ups (up to 3 per question) do NOT count toward the cap.

**Mandatory follow-ups.** The lead MUST follow up when:
- User gives vague answer → "I need you to pick one. If you could only ship one this week, which?"
- Answer contradicts a briefing → "You said X, but analysis shows Y. Help me reconcile that."
- User introduces new topic → resume relevant analyst for live query, then weave in the finding
- User says "I don't know" → "Let me give you the tradeoff: [options]. Even a provisional answer helps."

**Think out loud.** Share reasoning so the user gives better answers:
- "I'm asking about the processor because three of your priorities touch it. Getting sequencing right here is the difference between 5 days and 15."

**Every question must cite a specific finding.** No generic questions. Don't ask what briefings already answer — state the finding, ask for the decision.

**Track decisions** in `{SESSION_DIR}/interview/decisions.md` as you go.

### Live Follow-Up Queries

When the user raises a topic briefings don't cover:

1. Tell user: "Let me check on that."
2. Resume the relevant analyst with a targeted query.
3. While waiting, continue on a different topic or acknowledge the pause.
4. When response arrives, weave it in naturally — don't dump raw analyst output.
5. If >30 sec, note as "needs verification" and move on.

**Note:** Live follow-ups are unavailable when running from cached briefings. Work from briefing content only.

---

## Phase 3: Scope Validation (analysts resume, 2-3 min)

After the interview, the lead has a work item list. Instead of spawning breakdown agents:

1. Group work items by which analyst's domain they fall in.
2. Resume each relevant analyst with: "Here are the work items in your domain: [list with scope fields]. For each, confirm: (1) files correct? (2) dependencies correct? (3) any surprises? (4) is there a better way to achieve this item's goal that you'd recommend based on what you saw in the codebase?"
3. Analyst responds in <500 words with CORRECTIONS ONLY.
4. Lead incorporates corrections into work items.

**Note:** When running from cached briefings (no live analysts), the lead performs scope validation directly by re-reading relevant briefing sections and applying the same four checks.

### Scope Validation Response Format

```
ITEMS REVIEWED: WI-XX, WI-YY, WI-ZZ
CORRECTIONS:
- WI-XX: scope should also include {file} — it imports from {module}
- WI-YY: dependency on WI-XX is wrong — these are actually independent
ALL CORRECT: WI-ZZ
SURPRISES: {anything not in briefings the lead should know}
BETTER APPROACH: {WI-XX: suggest alternative if you have one, otherwise "none"}
```

---

## Phase 4: Output (lead, 3-5 min)

### Output 1: ROADMAP.md

Write to `{SESSION_DIR}/output/ROADMAP.md` and copy to repo root. The ROADMAP.md should be self-contained enough to serve as a kickoff prompt. Do NOT generate a separate kickoff document. The roadmap's Work Items section with scope, dependencies, and success criteria IS the execution spec.

```markdown
# Plan: {repo-name}
Generated: {date}

## Executive Summary
{3-4 sentences: current state, target state, constraints}

## Current State Assessment
### Architecture
{from arch-analyst, filtered by relevance to stated goals}
### Code Quality
{from quality-analyst, filtered}
### Developer Experience
{from dx-analyst, filtered}
### Technical Debt
{from debt-analyst, filtered}
{include domain analyst sections only if spawned}

## Priorities
1. **{priority}** — {user's rationale, in their words}

## Resolved Design Decisions
### Decision 1: {title}
- Context: {why this arose}
- Chosen: {option} — {rationale}
- Rejected: {option} — {why not}

## Work Items

### WI-01: {title}
- **Phase**: {roadmap phase} | **Type**: {refactor/feature/testing/cleanup/infra/docs}
- **Scope**: {specific files and directories}
- **Depends on**: {WI-XX} or nothing | **Blocks**: {WI-XX} or nothing
- **Design decision**: {resolved decision ref or N/A}
- **Success criteria**: {measurable}

## Execution Waves

### Wave 1: {name}
- **Items**: WI-XX, WI-YY
- **Unblocked by**: nothing (starting conditions)
- **Enables**: Wave 2

### Wave 2: {name}
- **Items**: WI-XX, WI-YY
- **Unblocked by**: {items from Wave 1}
- **Enables**: Wave 3

## Deferred
{things the user said "not now" to, with reasoning}

## Kickoff
To execute this plan:
```bash
claude --prompt "Read ROADMAP.md and execute Wave 1. Items {list} are independent — use parallel subagents."
```
```

### Output 2: GitHub Issues

Before creating issues, ask: "Create {N} issues in {repo}? [y/n]"

If user confirms:
- Each WI becomes one issue. Title: `WI-{XX}: {title}`
- Body includes: scope, dependencies ("Blocked by #{N}"), success criteria, resolved design decision
- Labels: `wave-{N}` + type (`refactor`, `feature`, `testing`, `cleanup`, `infra`, `docs`)
- Milestones: one per execution wave (create if needed)

If `gh` unavailable or user declines:
- Write `PLAN.md` to repo root with same content in markdown format

---

## Communication Norms

- **Lead → Analyst**: Direct message for follow-up queries. Include full context.
- **Analyst → Lead**: Structured response using Follow-Up or Scope Validation format.
- **Analyst → Analyst**: Never.
- **Broadcasts**: Lead only, for phase transitions.

## Critical Rules (All Agents)

1. **Do NOT modify source files** — except during Phase 1.5 Quick Win Execution when explicitly approved by the user. Analysis and planning only otherwise. Only write to `{SESSION_DIR}/` and repo-root output files.
2. **Do NOT use the API.** Everything through Claude Code CLI on subscription.
3. **Read real code.** Every claim must be grounded in actual files. Do not hallucinate paths or contents.
4. **Be specific.** File paths, function names, dependency versions. No generic statements.
5. **Analysts: if Write denied, output content as text.** The lead writes it on your behalf.

## Anti-patterns — do NOT do these

- Starting the interview before all briefings are written
- Asking generic questions not grounded in analyst findings
- Accepting vague answers without follow-up
- Modifying source code outside of Phase 1.5
- Creating issues without user confirmation
- Skipping scope validation
- Dumping raw analyst output to the user instead of synthesizing it
