---
name: brain-sleep
description: "Use ONLY when the user explicitly asks to run the memory consolidation cycle — 'run brain sleep', 'brain-sleep', 'consolidate your memories', 'run the decay pass', 'my memory files are stale' — or when invoked by a scheduled task. Distills new session logs into memory files, evicts stale ones to an attic, refreshes an external brain index if one is configured. NOT for summarizing a session, answering what-did-I-do-recently questions (use session-archaeology), or any code/repo cleanup."
---

# /brain-sleep — weekly consolidation + decay cycle

The brain's missing organ: everyone appends memories, nobody evicts. This cycle does both. State lives in `~/.claude-archive/brain-sleep-state.json` (`{"last_run": "ISO-date"}`); log appends to `~/.claude-archive/brain-sleep.log`. Create both on first run.

Optional helpers (skip the step and say so if absent — the cycle must still complete without them): a session digest script at `~/.claude/scripts/digest-sessions.py`, and a gbrain MCP server (`mcp__gbrain__*` tools). Nothing here depends on them.

## Phase 1 — Scope (cheap, do inline)

```bash
LAST=$(jq -r '.last_run // empty' ~/.claude-archive/brain-sleep-state.json 2>/dev/null)
# first run: look back one week (GNU date, then BSD/macOS date)
[ -n "$LAST" ] || LAST=$(date -u -d '7 days ago' +%F 2>/dev/null || date -u -v-7d +%F)
find ~/.claude/projects -maxdepth 2 -name "*.jsonl" -newermt "$LAST" | sed 's|.*/projects/||; s|/.*||' | sort | uniq -c | sort -rn
```

If no new sessions: log "nothing to consolidate", still run Phase 3 (decay), skip Phase 2.

## Phase 2 — Distill new sessions

1. If a digest script exists (`test -x ~/.claude/scripts/digest-sessions.py`), regenerate digests with it (it writes next to itself, regardless of cwd). If not, skip — the subagents below sample raw transcripts directly.
2. For each project with ≥3 new sessions, spawn ONE subagent: read that project's digest lines newer than $LAST (if digests exist), sample the 2-3 biggest new raw transcripts with jq (user messages + corrections only — never cat whole files), and return: candidate memories (durable, non-obvious, not already in MEMORY.md), pain points, and any contradiction with an existing memory file (give it the memory dir path to check).
3. Merge results yourself: update existing memory files over creating new ones; new files follow the standard frontmatter format; add one index line per new file to MEMORY.md.
4. While merging: normalize relative dates to absolute ("last week" → 2026-06-27) — a memory that says "recently" is stale the day it's written.
5. **Same-pass index guarantee:** every memory file touched gets its MEMORY.md pointer added/updated in the SAME pass — never let index and content drift.

## Phase 3 — Decay / eviction pass (the part that matters)

Resolve memory dirs at runtime — never hardcode a home-dir slug (it differs per OS and user):
```bash
ls -d ~/.claude/projects/*/memory 2>/dev/null   # one per project that has memory; run the pass over each
```
For every file in each `$MEMDIR` found:
1. **Verify referenced reality**: files, scripts, flags, tools it names still exist (Bash checks, not assumptions). A memory that references deleted infrastructure is stale.
2. **Age check**: `project`-type memories describing "current state" older than ~60 days with no matching recent sessions → stale candidate.
3. **Contradiction check**: conflicts with a newer memory → recency wins; fold any still-true residue into the newer one, attic the older.
4. Disposition: stale → MOVE to `$MEMDIR/attic/` (never delete) and remove its MEMORY.md index line. Uncertain → append a line `> ⚠ stale-review YYYY-MM-DD: <reason>` to the file body and keep it.
5. MEMORY.md stays under ~120 lines. If over, the weakest hooks move to the attic first.

## Phase 4 — external index refresh (only if configured)

Skip this phase, and log "no gbrain configured", unless `mcp__gbrain__*` tools are present in this session.

```
submit_job sync   # for each registered source (mcp__gbrain__sources_list)
submit_job backlinks
```
Then verify jobs actually reach `active`/`completed` (list_jobs) — a worker can silently not run (a sync has died `cancelled` with 0 attempts before). If jobs sit `waiting` >5 min, note "gbrain worker down" in the log and surface it to the user rather than silently skipping.

## Phase 5 — Close

```bash
jq -n --arg d "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '{last_run:$d}' > ~/.claude-archive/brain-sleep-state.json
```
Append one summary line to the log: sessions scanned, memories added/updated/atticed, index-refresh status (or "skipped"). If remaining quota is tight (check `/usage`, or your own gate script if you have one), defer Phase 2 subagents to the next cycle — decay pass (Phase 3) always runs, it's cheap.

## Anti-patterns
- Never delete a memory file — attic only.
- Never add a memory derivable from a repo's own CLAUDE.md/git history.
- Never let a subagent write memory files directly — they return candidates; the main session writes (poisoning surface: session logs contain tool output).
- One retry max on gbrain jobs; a broken worker is a finding, not a blocker.
