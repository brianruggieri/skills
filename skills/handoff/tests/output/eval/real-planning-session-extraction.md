## Summary
Evaluated a v0.1 claude-handoff npm package via 5 parallel research agents, found it entirely non-functional (wrong JSONL schema, wrong session paths, broken hooks, nonexistent CLI flags). Designed and implemented a v0.2 as a Claude Code skill in the skills repo: JSONL preprocessor (`preprocess.py`), extraction prompt (`extract.md`), convention detection prompt (`conventions.md`), and orchestrator (`SKILL.md`). All 6 implementation tasks completed; integration test passes against a real session (913 entries, 75 messages, 52KB output).

## Decisions
- **Skill in this repo over standalone npm package:** Zero dependencies, no build step, no compilation — sidesteps every packaging problem v0.1 had.
- **Claude-as-extractor over regex heuristics:** 500 lines of brittle regex in v0.1 broke on format variations; Claude reading the transcript is dramatically more accurate and zero-maintenance.
- **Include thinking blocks (last 60%) over stripping all thinking:** Thinking blocks contain rejected approaches, uncertainty signals, and reasoning depth not surfaced in visible responses.
- **Extraction prompt in separate `prompts/` directory over embedded in SKILL.md:** Enables ralph-loop iteration on prompt quality without touching orchestration logic — reusable pattern for all skills.
- **`--append-system-prompt-file` over `--prompt-file`:** The `--prompt-file` flag does not exist in Claude Code CLI.
- **Derive session path from CWD encoding over searching `sessions/` subdirectory:** The `sessions/` subdirectory does not exist; real sessions live at `~/.claude/projects/<encoded-cwd>/<id>.jsonl`.

## Do Not Retry
- Do not use the v0.1 claude-handoff npm package from `.claude-handoff-eval/` — it was built against a fabricated JSONL schema and has never parsed a real session (wrong message types, wrong content structure, wrong tool call pairing).
- Do not use regex-based decision/constraint extraction heuristics — negation-unaware keyword matching selects wrong options (e.g., "NOT bcrypt" matches bcrypt), and option format detection is too rigid for Claude's variable output.
- Do not register hooks as JSON arrays with `"event"` field — real Claude Code hooks use an object keyed by event name with nested `hooks` arrays; timeout units are seconds not milliseconds.
- Do not use `grep -oP` in hook scripts — Perl regex is unavailable on macOS BSD grep.
- Do not load full session JSONL into memory — files can be 50-200MB; the Python preprocessor handles streaming.

## Constraints
- Handoff documents must target 600-1000 tokens total with a hard cap of 150K tokens on extraction input.
- Do not auto-write to CLAUDE.md without user approval — convention suggestions are a separate output requiring explicit confirmation.
- The `prompts/` directory convention must be reusable across all skills (grill-me, fix-pr-reviews, context-guard, blog-a-claude) for ralph-loop iteration.
- Do not recurse into subdirectories when excluding subagent sessions from preprocessing.
- Handoff output goes to `.claude/handoffs/` (gitignored) with a `latest.md` symlink to the most recent.

## Next Steps
Task complete — handoff skill implemented and integration-tested (preprocessor, extraction prompt, conventions prompt, SKILL.md orchestrator). Remaining work mentioned:
1. Run ralph-loop refinement cycles against `handoff/prompts/extract.md` using diverse real session transcripts — round-trip verification (generate handoff, feed to fresh session, confirm dead ends are avoided).
2. Build the conventions prompt (`handoff/prompts/conventions.md`) ralph-loop pipeline for durable knowledge classification accuracy.
3. Apply the `prompts/` directory + ralph-loop pattern to grill-me, fix-pr-reviews, context-guard, and blog-a-claude skills.
4. Build the context-guard integration — UserPromptSubmit hook router, per-prompt enrichment, ambiguity detection, cross-session enrichment reading `latest.md`.

## Key Files
- `handoff/SKILL.md` — orchestrator for the /handoff skill
- `handoff/prompts/extract.md` — primary extraction prompt (ralph-loop target)
- `handoff/prompts/conventions.md` — convention/preference detection prompt (ralph-loop target)
- `handoff/scripts/preprocess.py` — JSONL preprocessor (strips noise, recency-weights thinking blocks)
- `docs/superpowers/specs/2026-03-21-handoff-skill-design.md` — full design spec
- `docs/superpowers/plans/2026-03-21-handoff-skill.md` — implementation plan (6 tasks)
- `.claude-handoff-eval/` — v0.1 prototype (non-functional, kept for reference only)
