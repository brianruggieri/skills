---
name: ab-experiment
description: "Use when the user says 'run this side by side', 'A/B this', or wants to measure whether a prompting/context/workflow change (handoff doc, CLAUDE.md variant, new skill, plan style) actually helps. Runs two identical-plan sessions differing by one treatment, mines both session JSONLs, blind-grades outputs, commits an evidence doc. NOT for implementing A/B tests or feature flags in product code."
---

# /ab-experiment

Measure whether ONE change (treatment) helps, with real numbers and blind grades. Precedent: three handoff A/B tests in `~/git/skills/handoff/evidence/`, including a decisive negative result — negative results are a success, report them proudly.

Existing tooling — reuse, do not rewrite:
- Metrics miner: `~/.claude/skills/handoff/eval/compare_implementations.py`
- Grading rubric: `~/.claude/skills/handoff/eval/prompts/grade-implementation.md`
- Evidence format: `~/git/skills/handoff/evidence/2026-03-24-candidate-eval-implementation-ab-test.md`

## 1. Setup

- [ ] State the hypothesis in one sentence and identify the treatment. Exactly ONE variable differs between arms. If the proposal bundles two changes, stop and ask the user which one to test.
- [ ] Name the arms after the treatment: `.worktrees/with-<X>` and `.worktrees/no-<X>`, both branched from the same base commit:
  ```bash
  git worktree add .worktrees/with-<X> -b eval/with-<X> <base>
  git worktree add .worktrees/no-<X> -b eval/no-<X> <base>
  ```
- [ ] Both arms get the IDENTICAL plan/prompt text. Only the treatment differs (extra doc, CLAUDE.md variant, skill present/absent, etc.).
- [ ] Absolute paths only in launch commands — especially `--append-system-prompt-file`. Relative paths break when cwd resets.
- [ ] Write both launch commands into an `eval-state.json` next to the worktrees (arm name, worktree path, branch, command, session-dir path) so the measure step is mechanical.

## 2. Run

- [ ] Before launching, check the 5-hour window: `jq .five_hour.utilization ~/.claude/usage-state.json` (or run `~/.claude/scripts/claude-usage-gate.sh`) — if utilization >80%, defer the run.
- [ ] If THIS session is interactive: do NOT run bare `claude -p` inline — nested interactive→headless hangs. For any in-session launch use the sanctioned escape hatch `env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT claude -p ...` (as a background Bash job + Monitor), or print both commands for the user to run in a separate terminal.
- [ ] Run both arms in the same wall-clock window where possible (same model snapshot, same load conditions).
- [ ] On API 401/500 mid-run (headless OAuth tokens expire ~8h and do NOT auto-refresh; the 401 lands in the session JSONL, not stderr — process just exits rc=1): relaunch the dead arm and aggregate metrics across all runs of that arm (Mar 24 precedent). Note the relaunch in the evidence doc.

## 3. Measure

- [ ] Find each arm's main session JSONL by LARGEST FILE SIZE, never newest mtime (subagent/stub sessions are newer but tiny):
  ```bash
  ls -S ~/.claude/projects/<encoded-worktree-path>/*.jsonl | head -1
  ```
- [ ] Run the miner:
  ```bash
  python3 ~/.claude/skills/handoff/eval/compare_implementations.py \
    --state-file <abs path>/eval-state.json --repo-root <abs repo root>
  ```
- [ ] Effective tokens = input + output + cache_read + cache_creation. Never compare on input+output alone — cache traffic is where the cost lives.
- [ ] Capture per arm: effective tokens, tool calls (bash/read/agent breakdown), turns, wall time, tests passing, lines added/removed. If an arm had relaunches, sum across runs.

## 4. Grade

- [ ] Grade with SUBAGENTS in this session (subscription). Never API, never promptfoo — rejected twice; `claude -p` also burns subscription anyway (June 2026 billing change paused).
- [ ] Grade per /honest-assessment step 3 (rubric-first, named deductions, blind diff). Rubric lives at `~/.claude/skills/handoff/eval/prompts/grade-implementation.md`; strip arm names, branch names, commit messages, and any PR-style claims before handing a diff to a grader.
- [ ] Use 2 graders per arm; if they disagree by >1 point on total, run a third and take the median.
- [ ] Only after all scores are in, unblind and map scores to arms.

## 5. Report

- [ ] Write the evidence doc into the relevant `evidence/` corpus (pattern: `handoff/evidence/YYYY-MM-DD-<topic>-ab-test.md`). Sections:
  1. Hypothesis + treatment (one line each)
  2. Setup (base commit, plan, launch commands, relaunches)
  3. Stats table (both arms, all metrics from step 3)
  4. Grader scorecards (per-criterion, blinded IDs, then unblinded mapping)
  5. Verdict — one sentence. "No effect" and "treatment hurts" are valid verdicts.
- [ ] Commit the evidence doc on the winning branch (or main via PR if neither arm merges).
- [ ] Merge the winner, kill the loser, clean up:
  ```bash
  git worktree remove .worktrees/<loser> && git worktree remove .worktrees/<winner>
  git worktree prune
  git branch -d eval/<loser-branch>
  ```

## Gotchas (hard-won, do not relearn)

- Main session JSONL = largest file, NOT newest mtime.
- Effective tokens include cache_read + cache_creation.
- Graders without a rubric inflate; correctness bugs that pass tests need explicit −1.5 to −2 deductions.
- Evals run as subagents on subscription, never API.
- Nested `claude -p` from an interactive session hangs — hand launch commands to the user.
- Headless runs >8h die on OAuth 401 buried in the JSONL; relaunch and aggregate.
