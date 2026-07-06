# skills

Custom [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills for my development workflow. Built for how I work; fork and adapt for yours.

Each skill is a directory with a `SKILL.md` that Claude Code discovers automatically. Invoke with `/skill-name` inside any Claude Code session.

## Skills

### grill-me

Stress-test a plan or design through relentless Socratic questioning. Builds a risk tree, walks it depth-first, and won't move on until every branch is resolved. Dispatches research agents when you say "I don't know" instead of letting you off the hook.

`/grill-me` when you want your design torn apart before production does it for you.

### fix-pr-reviews

Systematically address every review comment on a GitHub PR. Categorizes comments by priority, fixes code, runs tests, resolves threads via GraphQL, and updates the PR description. Nine-phase workflow that handles the tedious loop of review-fix-verify-push.

`/fix-pr-reviews` when a PR has review comments piling up.

### handoff

Extract structured context from a planning session and generate a handoff document for a fresh build session. Captures decisions, negative knowledge ("Do Not Retry"), constraints, and next steps. Uses a JSONL preprocessor and Claude-as-extractor architecture. Auto-saves session transcripts for eval corpus building.

Includes a bundled eval harness (`handoff/eval/`, run manually) that dispatches isolated subagents to grade extraction quality across 8 dimensions.

`/handoff` when a planning session is complete and you want to start building in a clean context window.

### ghostwrite

Write text in your authentic voice using a quantitative voice profile mined from your Claude Code session logs. Two modes: **build** a profile (extracts a corpus, analyzes sentence structure, punctuation, signature phrases, and anti-patterns, writes `voice-profile.md`), or **write** using an existing profile. The bundled extractor refuses to read outside `~/.claude/projects`, refuses to write outside `~/.claude/ghostwrite/`, and redacts likely secrets before writing; the skill treats all extracted session content as untrusted data, never instructions (Security & Trust Boundary hardening added in #6).

`/ghostwrite` when you want a draft that sounds like you wrote it, not like an AI.

### scope-repo

**ARCHIVED** — superseded by superpowers brainstorm→write-plan and grill-me plan dispatch; kept as a reference implementation of trusted-spec-CWD Agent Teams architecture.

Full codebase planning pipeline using Claude Code Agent Teams. Spawns 4-9 analyst agents to scan a repo in parallel, interviews you using their findings, validates scope, and outputs a prioritized `ROADMAP.md` plus GitHub Issues with dependency links. One session, ~20-30 minutes.

`/scope-repo` when you want a structured roadmap for a repo you're about to invest serious time in.

Requires Agent Teams enabled (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in settings.json). Also ships a standalone CLI wrapper (`scope-repo/scopework`) for running outside a session.

### trigger-eval

Skill trigger-reliability harness: does a skill's frontmatter description fire on the prompts it should and stay silent on near-miss prompts it shouldn't? Per skill: a `+`/`-` prompt matrix in `prompts/<skill>.txt`, one capped headless call each, detection by actual `Skill` tool invocation in the transcript. On its maiden run it caught a real over-triggering description *and* its own answer-leak bug (scratch dirs named after the skill under test poison every negative).

`./trigger-eval/run.sh <skill>` when shipping or editing any skill description.

### ab-experiment

Controlled A/B for workflow changes: two identical-plan sessions off the same base differing by exactly one treatment (a handoff doc, a CLAUDE.md variant, a new skill), session-JSONL mining for effective tokens and tool calls, blind rubric grading with anti-inflation deductions, and a committed evidence doc. The methodology behind the measured handoff ROI findings (41-70% win on open-ended plans, +27% overhead on prescriptive ones).

`/ab-experiment` when you want to know whether a change actually helps, not whether it feels like it helps.

### honest-assessment

Anti-inflation audit for agent-produced results: classifies every claimed metric as field-validated / mock-derived / assumed, enforces rubric-first blind grading with named deductions, and runs contamination checks (grading spec outside the graded repo, identical-score red flags). Born from real incidents: mock-derived r² presented as real, twin 9/10 grades hiding a correctness bug, a graded agent reading the grading spec and scoring itself an A+.

`/honest-assessment` after any agent-heavy sprint, before believing the numbers.

### session-archaeology

Mines Claude Code session history (`~/.claude/projects` JSONLs) correctly: filters tool-generated junk sessions, identifies main sessions by largest-file-not-mtime, and cites findings with session id + date + quote. The codified version of every "check your claude logs" retrospective.

`/session-archaeology` for "what have I done with X" and "we've decided this before" questions.

### headless-claude-hygiene

Preflight for anything that shells out to `claude -p`: quota-window gate, `--no-session-persistence` for batches, scratch-cwd fallback, and the nested-session hang guard (`env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT`). Encodes the failure modes of running thousands of headless calls against a subscription.

`/headless-claude-hygiene` before launching any batch, pipeline, or test suite that calls claude.

### tiered-fanout

Dispatch protocol for 3+ parallel coding agents: API-level dependency analysis (not file-level — green-in-isolation ≠ compatible-when-merged), A/B/C/D tier classification (parallel-safe / shared-surface-serial / human-hold / verify-first), pinned models, orchestrator-owned completion, and lead-owned shared-contract commits.

`/tiered-fanout` before spawning anything at a multi-issue epic.

### brain-sleep

Weekly memory consolidation with the pass most memory systems skip: decay/eviction. Distills new session logs into curated memory files (relative→absolute dates, recency-wins contradiction resolution, same-pass index updates), verifies each memory's referenced reality still exists, and moves stale memories to an attic — never deletes. Designed to run scheduled and headless.

`/brain-sleep` weekly, or whenever the memory files feel stale.

### codex-imagegen

Subscription-billed CLI image generation via OpenAI Codex's first-party `$imagegen` (gpt-image-2 on ChatGPT-subscription auth — no API key). Ships the live-tested incantation (`--sandbox workspace-write --skip-git-repo-check`, save to `./`, `</dev/null`, verify the file exists — codex claims success even when the sandbox blocked the save) and the quota rule: images burn the shared pool 3-5x faster than coding turns, so batches get routed to API billing or local Flux instead.

`/codex-imagegen` for one-off game assets, blog images, and UI mockups.

## Install

Symlink individual skills into your Claude Code skills directory:

```bash
git clone https://github.com/brianruggieri/skills.git ~/git/skills

# install one skill
ln -s ~/git/skills/grill-me ~/.claude/skills/grill-me

# install all
for skill in ~/git/skills/*/; do
  [ -f "$skill/SKILL.md" ] && ln -s "$skill" ~/.claude/skills/$(basename "$skill")
done
```

Or copy a skill directory into any project's `.claude/skills/` to share it with collaborators.

## Structure

```
grill-me/
  └── SKILL.md
fix-pr-reviews/
  └── SKILL.md
handoff/
  ├── SKILL.md
  ├── prompts/       # extraction + convention detection prompts
  ├── eval/          # blind eval harness (SKILL.md + grading rubric)
  ├── scripts/       # JSONL preprocessor
  └── tests/         # fixtures for eval
scope-repo/
  ├── SKILL.md
  ├── scopework      # standalone CLI wrapper
  └── install.sh
```

Each skill is self-contained in its directory. The `SKILL.md` has YAML frontmatter (`name`, `description`, `allowed-tools`) and a markdown body with the full protocol Claude follows when the skill is invoked.

## License

MIT
