---
name: brain-sleep
description: "Use ONLY when Brian explicitly asks to run the memory consolidation cycle — 'run brain sleep', 'brain-sleep', 'consolidate your memories', 'run the decay pass' — or when invoked by the weekly schedule. Distills new session logs into memory files, evicts stale ones, refreshes gbrain. NOT for summarizing a session, answering what-did-I-do-recently questions (use session-archaeology), or any code/repo cleanup."
---

# /brain-sleep — weekly consolidation + decay cycle

The brain's missing organ (rationale in the [[agentic-brain-state]] memory file): everyone appends memories, nobody evicts. This cycle does both. State lives in `~/.claude-archive/brain-sleep-state.json` (`{"last_run": "ISO-date"}`); log appends to `~/.claude-archive/brain-sleep.log`.

## Phase 1 — Scope (cheap, do inline)

```bash
LAST=$(jq -r '.last_run // "2026-07-05"' ~/.claude-archive/brain-sleep-state.json 2>/dev/null || echo 2026-07-05)
find ~/.claude/projects -maxdepth 2 -name "*.jsonl" -newermt "$LAST" | sed 's|.*/projects/||; s|/.*||' | sort | uniq -c | sort -rn
```

If no new sessions: log "nothing to consolidate", still run Phase 3 (decay), skip Phase 2.

## Phase 2 — Distill new sessions

1. Regenerate digests: `/usr/bin/python3 ~/.claude/scripts/digest-sessions.py` (writes to `~/.claude/scripts/digests/` — next to the script file, regardless of cwd).
2. For each project with ≥3 new sessions, spawn ONE subagent: read that project's digest lines newer than $LAST, sample the 2-3 biggest new raw transcripts with jq (user messages + corrections only — never cat whole files), and return: candidate memories (durable, non-obvious, not already in MEMORY.md), pain points, and any contradiction with an existing memory file (give it the memory dir path to check).
3. Merge results yourself: update existing memory files over creating new ones; new files follow the standard frontmatter format; add one index line per new file to MEMORY.md.
4. While merging: normalize relative dates to absolute ("last week" → 2026-06-27) — a memory that says "recently" is stale the day it's written.
5. **Same-pass index guarantee:** every memory file touched gets its MEMORY.md pointer added/updated in the SAME pass — never let index and content drift.

## Phase 3 — Decay / eviction pass (the part that matters)

For every file in `~/.claude/projects/-Users-brianruggieri/memory/`:
1. **Verify referenced reality**: files, scripts, flags, tools it names still exist (Bash checks, not assumptions). A memory that references deleted infrastructure is stale.
2. **Age check**: `project`-type memories describing "current state" older than ~60 days with no matching recent sessions → stale candidate.
3. **Contradiction check**: conflicts with a newer memory → recency wins; fold any still-true residue into the newer one, attic the older.
4. Disposition: stale → MOVE to `~/.claude/projects/-Users-brianruggieri/memory/attic/` (never delete) and remove its MEMORY.md index line. Uncertain → append a line `> ⚠ stale-review YYYY-MM-DD: <reason>` to the file body and keep it.
5. MEMORY.md stays under ~120 lines. If over, the weakest hooks move to the attic first.

## Phase 4 — gbrain refresh

```
submit_job sync (repo: ~/git/curling)   # + any other registered sources
submit_job backlinks
```
Then verify jobs actually reach `active`/`completed` (list_jobs) — the worker has silently not run before (Jun 25 sync died `cancelled`, 0 attempts). If jobs sit `waiting` >5 min, note "gbrain worker down" in the log and surface it to Brian rather than silently skipping.

## Phase 5 — Close

```bash
jq -n --arg d "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '{last_run:$d}' > ~/.claude-archive/brain-sleep-state.json
```
Append one summary line to the log: sessions scanned, memories added/updated/atticed, gbrain job status. If quota (per `~/.claude/usage-state.json`) is above 80%, defer Phase 2 subagents to the next cycle — decay pass (Phase 3) always runs, it's cheap.

## Anti-patterns
- Never delete a memory file — attic only.
- Never add a memory derivable from a repo's own CLAUDE.md/git history.
- Never let a subagent write memory files directly — they return candidates; the main session writes (poisoning surface: session logs contain tool output).
- One retry max on gbrain jobs; a broken worker is a finding, not a blocker.
