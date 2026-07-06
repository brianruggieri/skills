## Summary
This session evaluated a non-functional v0.1 prototype of a `claude-handoff` CLI tool, determined it was built against a fabricated JSONL schema and could never process real session files, then designed a replacement architecture as a Claude Code skill. The session concluded with a complete implementation plan written, reviewed, and executed via subagent-driven development — producing a working skill at `handoff/SKILL.md` with a passing integration test.

## Decisions
- **Distribution format:** Claude Code skill in this repo over standalone npm package or skill+companion package. Skills require no build step, no binary packaging, and no npm publishing — every packaging problem that broke v0.1 is eliminated.
- **Extraction engine:** Claude-as-extractor over regex heuristics. Claude reads the condensed transcript and extracts decisions/constraints/plan directly; this replaces 500 lines of brittle regex that broke on format variations.
- **Session file discovery:** Derive path from `$PWD` CWD encoding (`/` and `.` replaced with `-`) and pick the most recently modified JSONL in `~/.claude/projects/<encoded-cwd>/`. Uses `transcript_path` from hook input when available — eliminates the need for path guessing entirely.
- **Thinking block inclusion:** Include thinking blocks from the last 60% of the session, strip them from the first 40%. Late-session thinking captures decision crystallization and uncertainty signals; early thinking is exploratory noise.
- **Prompt file structure:** Extraction prompt lives in `prompts/extract.md`, not embedded in `SKILL.md`, so ralph-loop can iterate it independently without touching orchestration logic. [FRAGILE]
- **Handoff document format:** Six sections — Summary, Decisions, Do Not Retry, Constraints, Next Steps, Key Files — targeting 600–1000 tokens. "Do Not Retry" chosen over "Negative Knowledge" as the section name for imperative clarity.
- **Durable knowledge routing:** Convention suggestions go to a separate output appended after the handoff, prompting user approval before writing to CLAUDE.md. Not embedded in the handoff document to preserve token budget.
- **Hook registration format:** Object keyed by event name with nested `hooks` arrays; timeout in seconds. The v0.1 array-with-`"event"`-field format is silently ignored by Claude Code.
- **Launch mechanism:** `claude --append-system-prompt-file <path>` (with `--append-system-prompt` inline variant as fallback) over `--prompt-file`, which does not exist.

## Do Not Retry
- **v0.1 JSONL parser** — built against fabricated schema (`"type": "human"`, flat tool_use entries). Real schema uses `"type": "user"`, nested `message.content` arrays, and `tool_use_id`-matched tool results. All 26 passing tests validated against synthetic fixtures only; tool produced zero output on real data.
- **Session file discovery via `sessions/` subdirectory** — `~/.claude/projects/<hash>/sessions/*.jsonl` path does not exist. Real session files are directly at `~/.claude/projects/<encoded-cwd>/*.jsonl`.
- **Hook registration as JSON array with `"event"` field** — this format is silently ignored. Real format is an object keyed by event name.
- **`claude --prompt-file <path>` launch command** — flag does not exist and will fail immediately.
- **Pointing `package.json` bin at a `.ts` file without a build step** — `npx` fails with a syntax error on the first `import`.
- **Parallel tool call result pairing by index offset** (`entries[i+1]`) — Claude routinely batches multiple tool calls, producing non-adjacent results. ~50% of file contents silently lost with offset-based pairing; match by `tool_use_id` instead.
- **Decision extractor without negation awareness** — "definitely NOT bcrypt, go with argon2" matches `bcrypt` on first keyword hit and returns it as the chosen option.
- **`grep -oP` in hook scripts on macOS** — Perl regex unavailable in BSD grep; silent failure means hook never triggers.
- **Standalone npm package path for v1** — requires build, compilation, packaging, publishing, and `init` command. All of these were broken in v0.1 and add no value given the skill architecture.

## Constraints
- Handoff document must stay at 600–1000 tokens; durable convention suggestions are a separate output block, not added to the handoff.
- Do not auto-write to CLAUDE.md without user approval — present suggestions with a `[y/n/edit]` prompt.
- Do not recurse into subdirectories when locating the session JSONL (subagent sessions create their own files and must be excluded).
- Apply a 150K token hard cap on extraction input; truncate from the oldest user messages first if exceeded.
- Output files go to `.claude/handoffs/` (gitignored); do not write handoffs to the repo root or `docs/`.
- The `prompts/` directory convention (iterable prompt files separate from orchestration logic) applies as a reusable pattern across all skills in the repo — establish it here first.

## Next Steps
1. Verify the integration test output against a real session invocation — Task 5 passed preprocessing but the end-to-end `/handoff` invocation hasn't been user-confirmed yet.
2. Run ralph-loop against `handoff/prompts/extract.md` using 5–10 real session transcripts to refine extraction quality — this is the primary accuracy lever and was explicitly called out as a post-implementation priority.
3. Apply the `prompts/` directory convention to `grill-me` and `fix-pr-reviews` by adding `prompts/interrogate.md` and `prompts/triage.md` respectively — these are the next highest-value ralph-loop targets identified in the session.
4. Integrate `handoff/latest.md` symlink into `claude-context-guard` as the cross-session enrichment source once that skill is built — deferred from this skill's scope by design.

## Key Files
- `handoff/SKILL.md` — orchestration logic for the `/handoff` invocation; stable entry point
- `handoff/prompts/extract.md` — extraction prompt fed to Claude; primary ralph-loop iteration target
- `handoff/prompts/conventions.md` — convention/preference detection prompt; secondary ralph-loop target
- `handoff/scripts/preprocess.py` — JSONL preprocessor; handles real schema, recency weighting, noise stripping
- `handoff/tests/fixtures/real-planning-session.md` — preprocessed real session used for integration testing
- `docs/superpowers/specs/2026-03-21-handoff-skill-design.md` — full design spec; authoritative reference for any ambiguity
- `docs/superpowers/plans/2026-03-21-handoff-skill.md` — implementation plan with 6 tasks; all tasks marked complete
