## Summary
Evaluated the v0.1 claude-handoff npm package (found completely non-functional against real Claude Code data), redesigned it from scratch as a Claude Code skill, wrote a reviewed spec and implementation plan, and built the skill with 4 files. The `/handoff` skill is implemented but extraction prompts have not been refined via ralph-loop yet.

## Decisions
- **Distribution format:** Claude Code skill (SKILL.md in repo) over standalone npm package. Skills need no build step, no binary packaging, no hook registration — a single markdown file that works immediately.
- **Extraction engine:** Claude's own reasoning over regex heuristics. v0.1's 500 lines of regex parsers broke on real Claude output formatting; using Claude to read transcripts produces higher-quality extraction with zero pattern-matching fragility.
- **Preprocessor:** Python script via Bash over Node/jq. Handles the real JSONL schema (nested content arrays, embedded tool_use/tool_result) in under 0.2 seconds for 61MB files.
- **Thinking blocks:** Include for last 60% of session, strip from first 40%. Late-session thinking contains decision crystallization, uncertainty signals for [FRAGILE] flagging, and rejected approaches (negative knowledge). Early-session thinking is exploratory noise.
- **Prompt architecture:** Extraction prompts in separate `prompts/` directory, not embedded in SKILL.md. Enables ralph-loop iteration without touching orchestration logic. This becomes a reusable convention across all skills (grill-me, fix-pr-reviews, etc.).
- **Knowledge routing:** Three buckets — ephemeral (handoff doc), project-durable (CLAUDE.md additions with per-item user approval), user-durable (memory updates). Planning sessions are the richest source of durable knowledge that currently gets lost.
- **Launch mechanism:** `claude --append-system-prompt-file` with inline string fallback. No auto-launch — user copy-pastes the command to avoid surprising behavior and shell injection.

## Do Not Retry
- **v0.1 JSONL schema** — assumed `type: "human"` (real: `"user"`), standalone `tool_use`/`tool_result` entries (real: nested in message content arrays), `type: "summary"` metadata entry (doesn't exist), `sessions/` subdirectory (doesn't exist). Every parser function returned empty results on real data.
- **v0.1 session file discovery** — searched `~/.claude/projects/<hash>/sessions/*.jsonl`. The `sessions/` subdirectory does not exist. Real sessions are at `~/.claude/projects/<encoded-cwd>/*.jsonl` directly.
- **v0.1 hook registration format** — used a JSON array with an `"event"` field. Real hooks use an object keyed by event name with nested `hooks` arrays. Timeout in milliseconds when real API uses seconds.
- **`claude --prompt-file` flag** — does not exist. Use `--append-system-prompt-file` or `--append-system-prompt`.
- **Regex heuristic extraction** — plan detection, decision matching, and constraint extraction via regex patterns. Brittle against Claude's variable output formatting. 500 lines that produced noisy results even on synthetic test data.
- **`execSync` with string interpolation** — v0.1 launcher had shell injection via cwd/path with quotes in iTerm/tmux osascript commands.

## Constraints
- No auto-launching new sessions — user must explicitly copy-paste the launch command
- No CLAUDE.md modifications without per-item user approval (present each suggestion individually)
- Extraction prompt must include anti-hallucination guardrail: "Only extract what was explicitly discussed, do not infer or fabricate"
- Secret redaction: extraction prompt explicitly prohibits API keys, passwords, connection strings in output
- Handoff files written to `.claude/handoffs/` (gitignored) — ephemeral session artifacts, not source code
- `latest.md` symlink is the passive integration point for future context-guard enrichment tools
- The `prompts/` directory convention is reusable infrastructure — build ralph-loop tooling that works across all skills in the repo

## Next Steps
1. Run ralph-loop on `prompts/extract.md` against real session fixtures — this is the primary quality lever for handoff accuracy
2. Test `/handoff` in a fresh Claude Code session (skill was created mid-session and couldn't be loaded; needs session restart)
3. Install the skill globally so it works outside the skills repo
4. Add diverse test fixtures (short sessions, paste-heavy sessions, sessions with no clear plan)
5. Build reusable ralph-loop prompt refinement infrastructure as a first-class skill/tool
6. Begin claude-context-guard spec for the per-prompt enrichment half of the context problem

## Key Files
- `handoff/SKILL.md` — main skill orchestrator, 6-phase workflow
- `handoff/prompts/extract.md` — extraction prompt (ralph-loop target, highest-priority refinement)
- `handoff/prompts/conventions.md` — convention/preference detection prompt
- `handoff/scripts/preprocess.py` — JSONL preprocessor (handles real Claude Code session schema)
- `handoff/tests/fixtures/real-planning-session.md` — first ralph-loop fixture (this session's transcript)
- `docs/superpowers/specs/2026-03-21-handoff-skill-design.md` — full v0.2 design spec
- `docs/superpowers/plans/2026-03-21-handoff-skill.md` — implementation plan
