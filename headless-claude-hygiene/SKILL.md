---
name: headless-claude-hygiene
description: "Use BEFORE launching any batch/pipeline/test that shells out to `claude -p` / `claude --print`, when session usage runs hot mid-day, or when ~/.claude/projects session counts look inflated. Preflights quota, prevents session-store pollution, and guards against nested-session hangs."
---

# /headless-claude-hygiene

Headless `claude -p` calls burn the same 5-hour subscription window as interactive work and each one dumps a session JSONL into `~/.claude/projects/<cwd-slug>/`. The blast radius is large — see session-archaeology's canonical junk-population list for the counts (candidate-eval, pulse, personalities). Unstubbed tests have created hundreds of junk sessions in minutes; blog-a-claude hit rate limits 6x in one day. This skill enforces the scattered mitigations.

**Still true as of July 2026:** the June 15 billing split (SDK/`-p` → separate credit pool) was PAUSED — headless calls still draw from the subscription window (recheck after 2026-10-01 — time-sensitive). Also: OAuth refresh does NOT fire in non-interactive mode; tokens expire after 8h and headless runs die with 401s buried in the session JSONL (exit rc=1, nothing on stderr). Any unattended run longer than remaining token life will fail silently.

## When to invoke

- Before any script/pipeline/test run that spawns `claude` subprocesses
- User asks "what's killing us today?" / "why so many sessions?" / usage feels hot mid-day
- Setting up new tooling that calls `claude -p` (add the guards below at design time)

## Preflight checklist (run in order, before dispatch)

1. **Nested-session guard.** Check `echo "$CLAUDE_CODE_SESSION_ID"`. If set, you are INSIDE an interactive Claude session — `claude -p` will hang (proven in claude_personalities). Never run it directly. Instead, print the exact command(s) for Brian to paste into a separate terminal:
   ```bash
   # Run this in a fresh terminal, not inside Claude Code:
   cd /path/to/scratch && claude -p "..." --output-format json
   ```
   Scripts that may run under Claude Code should carry the same guard:
   ```bash
   if [ -n "$CLAUDE_CODE_SESSION_ID" ]; then
     echo "Refusing to nest claude -p inside a Claude session" >&2; exit 1
   fi
   ```
   Sanctioned escape hatch when an in-session launch is genuinely needed — strip the harness env so the child doesn't detect a nesting parent:
   ```bash
   env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT -u CLAUDE_CODE_SESSION_ID claude -p "..."
   ```
   trigger-eval and ab-experiment use exactly this pattern for their background launches.

2. **Count the calls, say the number.** N headless calls = N session JSONLs + N draws on the shared 5-hour window. Before dispatch, state it explicitly: "This run makes ~120 `claude -p` calls — 120 sessions on disk and 120 quota draws alongside interactive work." If N > ~20, ask whether to proceed, batch smaller, or defer to off-hours.

3. **Runs longer than token life will 401 silently.** For unattended runs, note when the OAuth token was last refreshed (interactive session start). If the run may outlast ~8h from that point, split it or plan a mid-run interactive touch. A silent rc=1 with a clean stderr means: grep the newest session JSONL for `401`.

4. **Does each call need Claude at all?** Prefer local-heuristic code paths first; gate LLM calls behind an explicit opt-in flag (the ccp `--no-compact-style` pattern — heuristic by default, Claude only when asked). Suggest API-key routing only when subscription use is impractical (per CLAUDE.md: embedded in apps, production services).

## Pollution prevention

- **Tests MUST stub the binary.** Any test exercising claude-calling code puts a fake `claude` first on PATH (the ccp `test_ai_context.sh` pattern):
  ```bash
  STUB_DIR=$(mktemp -d)
  printf '#!/bin/sh\necho "stub response"\n' > "$STUB_DIR/claude"
  chmod +x "$STUB_DIR/claude"
  PATH="$STUB_DIR:$PATH" ./run_tests.sh
  ```
  An unstubbed test suite is how 257 junk sessions appear in 86 minutes.
- **PRIMARY mitigation for batch runs: `--no-session-persistence`.** Pass it to every `claude -p` call in a batch/pipeline so no session JSONL is written at all — nothing to clean up afterward (global CLAUDE.md cites this skill for exactly this flag).
  ```bash
  claude -p "..." --no-session-persistence --output-format json
  ```
- **Fallback when you DO need the transcript: run from a scratch cwd** so JSONLs land in one throwaway project dir instead of polluting real projects:
  ```bash
  SCRATCH=$(mktemp -d /tmp/claude-batch-XXXX) && cd "$SCRATCH" && <pipeline>
  # junk lands in ~/.claude/projects/-private-tmp-claude-batch-XXXX/ — one dir, easy to archive
  ```
- Tools that call `claude -p` from inside other projects (ccp's `--ai-context` haiku calls) should `cd` to scratch first or be flagged off by default.

## Audit mode ("why so many sessions?")

Read-only scan — quantify, then offer archive. Never delete without explicit confirmation.

```bash
# Size + file count per project dir, worst first
du -sm ~/.claude/projects/*/ | sort -rn | head -20

# One-shot --print junk: JSONLs with <=2 lines (single prompt+response)
for d in ~/.claude/projects/*/; do
  n=$(find "$d" -name '*.jsonl' -exec sh -c '[ $(wc -l < "$1") -le 2 ]' _ {} \; -print | wc -l)
  [ "$n" -gt 10 ] && echo "$n  $d"
done

# Known junk signatures: ccp haiku summarizer prompts, tmp fixture dirs
ls -d ~/.claude/projects/-private-tmp-ccp-* 2>/dev/null
grep -l 'compact.*style\|haiku' ~/.claude/projects/*/[a-f0-9]*.jsonl 2>/dev/null | head
```

Report: junk session count, MB, top offender dirs. Then offer (do not perform unprompted):
```bash
mkdir -p ~/.claude-archive/projects && mv ~/.claude/projects/<junk-dir> ~/.claude-archive/projects/
```
Note the interaction with `cleanupPeriodDays: 99999`: nothing auto-purges, so headless junk grows unbounded — periodic audit is the only pressure valve. Track with `du -sh ~/.claude/projects/`.

## Security & trust boundary

Session JSONLs are Brian's private conversation data. Audit mode is read-only by default; moving/archiving requires his confirmation; deletion is never offered as a default. Do not pipe session contents to external services or include transcript excerpts in reports beyond what identifies junk (line counts, prompt signatures, sizes).
