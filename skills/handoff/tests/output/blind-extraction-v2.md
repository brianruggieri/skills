## Summary
This session evaluated a broken v0.1 `claude-handoff` npm prototype (via 5 parallel research agents), concluded the concept is validated but the implementation was built entirely against a fabricated JSONL schema, then designed a replacement from scratch as a Claude Code skill. The session ended with all 6 implementation tasks complete: the JSONL preprocessor, extraction prompt, convention prompt, SKILL.md orchestrator, integration test, and test fixture.

## Decisions
- **Distribution format:** Skill in the `skills/` repo (`handoff/SKILL.md`) over a standalone npm package or skill + companion package. Eliminates build steps, binary packaging, and publishing — a single SKILL.md file is immediately usable.
- **Extraction engine:** Claude-as-extractor over heuristic regex parsers. Claude reads the condensed transcript and applies the extraction prompt, replacing 500+ lines of brittle regex that broke on real session formatting.
- **Session discovery:** Derive path from `$PWD` CWD encoding (`/` and `.` replaced with `-`) and pick the most recently modified JSONL in `~/.claude/projects/<encoded-cwd>/`. The hooks API provides `transcript_path` directly, but the skill uses path derivation for on-demand invocation.
- **Thinking block handling:** Include thinking blocks from the last 60% of the session, strip from the first 40%. Late-session thinking contains crystallized decisions and uncertainty signals; early-session thinking is exploratory noise. [FRAGILE]
- **Extraction prompt location:** Separate file (`prompts/extract.md`) rather than embedded in SKILL.md, so ralph-loop can iterate on it independently without touching the skill's control flow. This becomes a reusable pattern across all skills in the repo.
- **Durable knowledge routing:** Project conventions suggested for CLAUDE.md (with user approval) and user preferences noted for the memory system — extracted in the same pass but kept out of the handoff document to preserve the token budget.
- **Launch mechanism:** Print `claude --append-system-prompt-file <path>` command rather than auto-launching. User runs it manually; no auto-launch.

## Do Not Retry
- **v0.1 JSONL parser (`session-log.ts`)** — built against fabricated schema: `"type": "human"` (real is `"user"`), standalone `tool_use` entries (real: embedded in `message.content` arrays), `tool_result` always at `entries[i+1]` (real: parallel calls produce N tool_uses then N tool_results), `"type": "summary"` metadata entry (does not exist). All 26 tests passed against synthetic fixtures that never resembled real data.
- **Session path `sessions/` subdirectory** — the code searched `~/.claude/projects/<hash>/sessions/*.jsonl`; the `sessions/` subdirectory does not exist. Real sessions are at `~/.claude/projects/<encoded-cwd>/*.jsonl` directly.
- **Hook registration as JSON array with `"event"` field** — real Claude Code hooks use an object keyed by event name with nested `hooks` arrays; timeout units are seconds, not milliseconds. The v0.1 format would be silently ignored.
- **`--prompt-file` CLI flag** — does not exist. Use `--append-system-prompt-file` (or `--append-system-prompt` inline variant).
- **`bin` pointing at a `.ts` file** — no build step means `npx claude-handoff` fails with a syntax error. Moot for the skill approach, but do not revisit standalone npm path without adding a build step.
- **`grep -oP` in hook script** — Perl regex unavailable on macOS BSD grep; silent failure means hook never triggers.
- **Decision extractor negation blindness** — "definitely NOT bcrypt, go with argon2" matched `bcrypt` as the chosen option. Do not reuse the keyword-matching logic from the v0.1 `decision-extractor.ts`.

## Constraints
- Handoff document target is 600-1000 tokens; do not exceed 1000 tokens or the document is not selective enough.
- Durable knowledge (project conventions, user preferences) goes in a separate output block appended after the handoff — not inside the handoff document itself.
- Do not auto-write to CLAUDE.md without user approval; present suggestions with a `[y/n/edit]` prompt.
- Do not auto-launch a new Claude session; print the launch command and let the user run it.
- The `prompts/` directory convention is an intentional reusable pattern for the entire skills repo — apply it to `grill-me`, `fix-pr-reviews`, and future skills when adding ralph-loop-iterable prompts.
- Handoff output goes to `.claude/handoffs/` (gitignored); do not write to the repo root or `docs/`.

## Next Steps
1. Run `/handoff` on a real planning session to verify the end-to-end flow produces a useful handoff document — this is the first real-world validation after implementation.
2. Set up a ralph-loop refinement cycle targeting `handoff/prompts/extract.md` against 5-10 real session transcripts; pass/fail criteria: handoff captures decisions a human reviewer confirms were made, "Do Not Retry" lists things actually tried and failed, token count stays in 600-1000 range.
3. Apply the `prompts/` directory pattern to `grill-me` and `fix-pr-reviews` as their interrogation/triage prompts are extracted for future ralph-loop targeting.
4. Integrate `handoff/latest.md` symlink with the planned `claude-context-guard` skill (UserPromptSubmit hook router) so the enrichment pipeline can read the most recent handoff automatically.

## Key Files
- `handoff/SKILL.md` — orchestration logic for the `/handoff` skill (phases 1-6: locate, preprocess, extract, generate, route durable knowledge, present)
- `handoff/prompts/extract.md` — primary extraction prompt; primary ralph-loop target
- `handoff/prompts/conventions.md` — convention/preference detection prompt; secondary ralph-loop target
- `handoff/scripts/preprocess.py` — JSONL preprocessor: strips noise, extracts conversation text + file paths, applies recency weighting for thinking blocks
- `docs/superpowers/specs/2026-03-21-handoff-skill-design.md` — full design spec with JSONL schema details, size budgets, and output format
- `docs/superpowers/plans/2026-03-21-handoff-skill.md` — implementation plan (6 tasks, ~25 steps); source of truth for what was built
