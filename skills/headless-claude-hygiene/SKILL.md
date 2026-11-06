---
name: headless-claude-hygiene
description: "Use BEFORE launching any batch, pipeline, or test suite that shells out to `claude -p`/`claude --print`, when the user says 'session usage is running hot', or when ~/.claude/projects fills with junk sessions from automated runs. Preflights quota, prevents session-store pollution, guards nested-session hangs. NOT for running a single interactive claude prompt, and NOT for general shell/script performance questions."
---

# /headless-claude-hygiene

Headless `claude -p` calls burn the same 5-hour subscription window as interactive work and each one dumps a session JSONL into `~/.claude/projects/<cwd-slug>/`. The blast radius is large — see session-archaeology's junk-population list for examples from one real corpus: thousands of headless eval sessions, hundreds of test-suite sessions, a blog pipeline that hit rate limits six times in one day. This skill enforces the scattered mitigations.

**Verify the billing model before relying on it.** Every time this was checked (most recently July 2026), headless `claude -p` calls drew from the same subscription window as interactive work; an announced split into a separate SDK credit pool was paused. Do not assume either way — check the current pricing docs or `/usage` at the start of any large batch. Independent of billing: OAuth refresh does NOT fire in non-interactive mode; tokens expire after ~8h and headless runs die with 401s buried in the session JSONL (exit rc=1, nothing on stderr). Any unattended run longer than remaining token life will fail silently.

## When to invoke

- Before any script/pipeline/test run that spawns `claude` subprocesses
- User asks "what's killing us today?" / "why so many sessions?" / usage feels hot mid-day
- Setting up new tooling that calls `claude -p` (add the guards below at design time)

## Preflight checklist (run in order, before dispatch)

1. **Nested-session guard.** Check `echo "$CLAUDE_CODE_SESSION_ID"`. If set, you are INSIDE an interactive Claude session — `claude -p` will hang (observed repeatedly in a benchmark harness). Never run it directly. Instead, print the exact command(s) for the user to paste into a separate terminal:
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

4. **Does each call need Claude at all?** Prefer local-heuristic code paths first; gate LLM calls behind an explicit opt-in flag (heuristic by default, Claude only when asked). Suggest API-key routing only when subscription use is impractical (embedded in apps, production services).

## Pollution prevention

- **Tests MUST stub the binary.** Any test exercising claude-calling code puts a fake `claude` first on PATH:
  ```bash
  STUB_DIR=$(mktemp -d)
  printf '#!/bin/sh\necho "stub response"\n' > "$STUB_DIR/claude"
  chmod +x "$STUB_DIR/claude"
  PATH="$STUB_DIR:$PATH" ./run_tests.sh
  ```
  An unstubbed test suite is how 257 junk sessions appeared in 86 minutes in one real project.
- **PRIMARY mitigation for batch runs: `--no-session-persistence`.** Pass it to every `claude -p` call in a batch/pipeline so no session JSONL is written at all — nothing to clean up afterward.
  ```bash
  claude -p "..." --no-session-persistence --output-format json
  ```
- **Fallback when you DO need the transcript: run from a scratch cwd** so JSONLs land in one throwaway project dir instead of polluting real projects:
  ```bash
  SCRATCH=$(mktemp -d /tmp/claude-batch-XXXX) && cd "$SCRATCH" && <pipeline>
  # junk lands in ~/.claude/projects/-private-tmp-claude-batch-XXXX/ — one dir, easy to archive
  ```
- Tools that call `claude -p` from inside other projects (e.g. a commit-summarizer's haiku calls) should `cd` to scratch first or be flagged off by default.

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

# Known junk signatures: tmp fixture dirs, repeated template prompts from your own tools
ls -d ~/.claude/projects/-private-tmp-* ~/.claude/projects/-tmp-* 2>/dev/null
# substitute the fixture prompt(s) your tooling sends:
grep -l 'Summarize this developer task' ~/.claude/projects/*/[a-f0-9]*.jsonl 2>/dev/null | head
```

Report: junk session count, MB, top offender dirs. Then offer (do not perform unprompted):
```bash
mkdir -p ~/.claude-archive/projects && mv ~/.claude/projects/<junk-dir> ~/.claude-archive/projects/
```
If you raised `cleanupPeriodDays` to keep history (default is 30 days), nothing auto-purges, so headless junk grows unbounded — periodic audit is the only pressure valve. Track with `du -sh ~/.claude/projects/`.

## Security & trust boundary

Session JSONLs are the user's private conversation data. Audit mode is read-only by default; moving/archiving requires the user's confirmation; deletion is never offered as a default. Do not pipe session contents to external services or include transcript excerpts in reports beyond what identifies junk (line counts, prompt signatures, sizes).
