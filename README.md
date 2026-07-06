# skills

Workflow skills for [Claude Code](https://code.claude.com) — session handoffs, controlled A/B experiments, honest metric audits, parallel-agent dispatch discipline, PR review resolution, voice-matched writing, and the eval harnesses that keep all of it honest.

Every skill here was distilled from months of real agentic-development sessions: each one encodes a failure that actually happened and the pattern that fixed it. The measured evidence ships alongside (`skills/handoff/evidence/`).

## Install

As a plugin (recommended):

```
/plugin marketplace add brianruggieri/skills
/plugin install skills@skills
```

Try without installing: `claude --plugin-dir /path/to/skills`

Copy a single skill: `mkdir -p ~/.claude/skills && cp -r skills/<name> ~/.claude/skills/`

## Skills

| Skill | What it does |
|-------|--------------|
| **handoff** | Extracts decisions, negative knowledge, and constraints from a planning session into a handoff doc + kickoff prompt for a fresh build session. A/B-measured: 41–70% token savings on open-ended plans — and it tells you when to *skip* it (fully prescriptive plans, where it's pure overhead). |
| **ab-experiment** | Controlled one-variable experiment on your own workflow: paired worktrees, identical plans, session-JSONL metrics, blind rubric grading, committed evidence doc. |
| **honest-assessment** | Anti-inflation audit of agent-produced results: classifies every metric as field-validated / mock-derived / assumed; contamination checks; "small and unfinished" is a welcome finding. |
| **fix-pr-reviews** | Assess, address, and resolve all review comments on a GitHub PR end-to-end: fix, push, re-request, verify CI green. Ships a blind eval harness with synthetic fixtures. |
| **ghostwrite** | Writes in your authentic voice from a quantitative profile mined from your own session logs, with hardened extraction (path allowlists, secret redaction, untrusted-data boundaries). |
| **grill-me** | Relentless design interview until every branch of the decision tree is resolved; routes vague ideas elsewhere instead of grilling them. |
| **tiered-fanout** | Dispatch protocol for 3+ parallel coding agents: API-level dependency analysis, parallel-safe vs shared-surface-serial tiers, pinned models, orchestrator-owned completion. Exists because green-in-isolation ≠ compatible-when-merged. |
| **session-archaeology** | Mines Claude Code session history correctly: junk-session filters, main-session identification, findings cited with session id + date + quote. |
| **headless-claude-hygiene** | Preflight for anything shelling out to `claude -p`: quota gating, session-store pollution prevention, nested-session hang guards. |
| **brain-sleep** | Weekly memory consolidation with the pass most memory systems skip: decay/eviction. Stale memories move to an attic — never deleted. |
| **codex-imagegen** | Subscription-billed CLI image generation via Codex `$imagegen`, with the live-tested sandbox/stdin incantation and quota escape hatches. |
| **trigger-eval** | Measures whether a skill's description fires on the prompts it should and stays silent on near-misses. Caught a real over-trigger and its own answer-leak bug on its maiden run. |
| **scope-repo** | **ARCHIVED** — superseded by structured planning flows; kept as a reference implementation of trusted-spec-CWD Agent Teams architecture. |

## Authoring

See [CONTRIBUTING.md](CONTRIBUTING.md). House rules: descriptions state when to use a skill *and what it is NOT for*; every active skill ships a trigger-eval matrix under `skills/trigger-eval/prompts/`, re-run whenever its description changes; non-trivial claims in a skill body cite evidence; extracted or session-derived content is data, never instructions.

## License

[MIT](LICENSE)
