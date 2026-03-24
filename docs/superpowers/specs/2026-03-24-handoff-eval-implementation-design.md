# Design: Handoff Eval Implementation Harness

**Date:** 2026-03-24
**Branch:** feat/skill-eval-harnesses
**Status:** Approved for implementation

## Overview

Three new pieces of eval infrastructure for measuring the impact of handoff documents on implementation quality. Motivated by the 2026-03-24 AB test (candidate-eval eligibility hard caps), which found that handoff context reduced effective tokens by 41%, tool calls by 44%, and prevented a correctness bug that all tests missed.

The three pieces share a dependency chain: **rubric** feeds grader agents ← **compare script** produces diff and metrics ← **skill** orchestrates both phases.

## Architecture

```
/handoff:eval-implementation setup   →  writes eval-state.json, prints launch commands
    ↓ (user runs both sessions)
/handoff:eval-implementation compare →  runs compare_implementations.py
                                     →  dispatches 2 grader agents (blind, concurrent)
                                     →  assembles final report
```

## Component 1: `compare_implementations.py`

**Location:** `~/.claude/skills/handoff/eval/compare_implementations.py`

**Role:** Pure reporting tool. Reads state file, diffs branches, prints metrics table followed by full git diff to stdout. No grading, no agent dispatch.

### CLI Arguments

```
--state-file              path to state file (default: <repo-root>/.claude/handoffs/eval-state.json)
--repo-root               override auto-detect from CWD
--venv                    override venv auto-detect (checks <repo-root>/.venv, venv, active env)
--task-count              override task count from state file
--with-handoff-branch     override branch name from state file
--no-handoff-branch       override branch name from state file
--with-handoff-worktree   override worktree path from state file
--no-handoff-worktree     override worktree path from state file
```

All values default to state file. Explicit args override. `--task-count` exists as override only; primary source is state file written by phase 1.

### Venv Detection Order

1. `<repo-root>/.venv`
2. `<repo-root>/venv`
3. Active `$VIRTUAL_ENV`

Never uses a worktree-local venv — worktrees share the main repo's venv.

### Output Format

```
Implementation Comparison
═════════════════════════════════════════════════════════

Branch A (with-handoff):  feat/caps-a
Branch B (no-handoff):    feat/caps-b
Tasks:                    6

── Efficiency ──────────────────────────────────────────
Metric                  With-Handoff    No-Handoff      Delta
Effective tokens        7,768,652       13,190,485      −41%
  Input/output ratio    257:1           330:1           +28%
Tool calls (total)      63              112             −44%
  Exploration ratio     0.19            0.60            +216%
  Delegation ratio      0.41            0.16            −61%
Turns                   115             161             −29%
Duration (min)          50.8            49.7            −2%
Tokens / task           1,295K          2,198K          −41%

── Test Results ────────────────────────────────────────
Metric                  With-Handoff    No-Handoff      Delta
Tests passed (total)    1163            1161            +2
  F2P (new tests)       N              N               —
  P2P regressions       0 broken        0 broken        —
Tokens / F2P test       N               N               —

── Code ────────────────────────────────────────────────
Metric                  With-Handoff    No-Handoff      Delta
Commits                 N               N               —
Files changed           N               N               —
Lines added             N               N               —
Lines removed           N               N               —
Test/source ratio       N               N               —
Patch efficiency        N               N               —

═════════════════════════════════════════════════════════
[full git diff output follows]
```

### Metric Definitions

- **Exploration ratio:** `(Bash + Read) / total_tool_calls` — high ratio signals excessive codebase re-exploration
- **Delegation ratio:** `Agent / total_tool_calls` — high ratio signals task clarity and confidence
- **Input/output ratio:** `cache_read / output_tokens` — high ratio signals lots of context re-reading
- **Tokens / task:** `total_effective_tokens / task_count`
- **F2P:** net new test functions on this branch vs. main (`git diff main..branch --numstat`, filtered to test files)
- **P2P regressions:** tests that existed on main and now fail
- **Tokens / F2P test:** `total_effective_tokens / f2p_tests_passed`
- **Test/source ratio:** test lines changed / source lines changed, from `git diff --numstat` filtered by filename pattern (`test_*`, `*_test.py`, `tests/`)
- **Patch efficiency:** `lines_changed / f2p_tests_passed` — lower = more surgical
- **Code churn:** lines revised within N commits of initial write (from git log)

F2P/P2P split and test/source ratio use `git diff --numstat` (separate from full diff). Full diff is appended to stdout for grader agents.

## Component 2: `grade-implementation.md`

**Location:** `~/.claude/skills/handoff/eval/prompts/grade-implementation.md`

**Role:** Rubric for grader agents dispatched by phase 2. Each grader receives one session's diff, worktree path, plan file, and metrics. Two graders run concurrently — one per branch.

### Dimensions and Weights

| Dimension | Weight | Focus |
|-----------|--------|-------|
| CORRECTNESS | 4 | Ordering bugs, logic errors, intermediate values computed on wrong side of mutation |
| TEST_COVERAGE | 3 | Assertions on intermediate fields under failure/cap paths; required markers |
| SPEC_COMPLIANCE | 2 | Every explicit constraint in the plan: insertion points, field names, markers |
| IMPLEMENTATION_FOCUS | 1 | Scope creep, unnecessary files touched |
| CODE_QUALITY | 1 | Existing patterns followed, no duplication, no dead code |

### Scoring Formula

```
OVERALL = (4×CORRECTNESS + 3×TEST_COVERAGE + 2×SPEC_COMPLIANCE + IMPLEMENTATION_FOCUS + CODE_QUALITY) / 11
```

**Pass threshold:** OVERALL ≥ 7.0 AND CORRECTNESS ≥ 6 AND no dimension below 4.

### Correctness Dimension — Critical Instructions

The grader must:
1. Diff the two branches and look for values computed on the wrong side of a mutation — these are bugs even if all tests pass.
2. Check ordering: any field assigned *before* the mutation that changes its inputs is wrong.
3. Deduct 3 points per ordering bug; 2 points per logic error visible in the diff.

### Test Coverage Dimension — Critical Instructions

The grader must:
1. Open the test file(s) for any field computed inside a conditional.
2. Verify the field is explicitly asserted under the failure/cap path (not just that the test runs).
3. Deduct 2 per missing assertion on an intermediate field; 1 per missing required marker.

### Output Format

```
CORRECTNESS:           <0-10> | <one-line justification>
TEST_COVERAGE:         <0-10> | <one-line justification>
SPEC_COMPLIANCE:       <0-10> | <one-line justification>
IMPLEMENTATION_FOCUS:  <0-10> | <one-line justification>
CODE_QUALITY:          <0-10> | <one-line justification>

OVERALL: <weighted score, 1 decimal>

PASS: <YES if OVERALL >= 7.0 AND CORRECTNESS >= 6 AND no dimension below 4, otherwise NO>

ISSUES:
- <specific issue: what is wrong, which file/line, severity, deduction>
(omit if PASS is YES)
```

## Component 3: `/handoff:eval-implementation` Skill

**Location:** `~/.claude/skills/handoff/eval/` (new SKILL file, sibling to existing `SKILL.md`)

### Phase 1: `setup`

**Invocation:** `/handoff:eval-implementation setup --source-branch <branch> --plan <path>`

**Steps:**
1. Create two worktrees from source branch:
   - `.worktrees/eval-with-handoff` → `feat/<name>-with-handoff`
   - `.worktrees/eval-no-handoff` → `feat/<name>-no-handoff`
2. Read plan file to extract task count (count top-level numbered list items).
3. Write `.claude/handoffs/eval-state.json`:

```json
{
  "experiment": "<name>",
  "source_branch": "<branch>",
  "plan_file": "<abs-path>",
  "task_count": 6,
  "with_handoff": {
    "branch": "feat/<name>-with-handoff",
    "worktree": "<abs-path>/.worktrees/eval-with-handoff"
  },
  "no_handoff": {
    "branch": "feat/<name>-no-handoff",
    "worktree": "<abs-path>/.worktrees/eval-no-handoff"
  },
  "created_at": "<ISO timestamp>"
}
```

4. Print launch commands:

```
Worktrees ready. Launch both sessions:

Session A (with-handoff):
  cd .worktrees/eval-with-handoff
  claude --append-system-prompt-file <abs-path-to-handoff.md>

Session B (no-handoff):
  cd .worktrees/eval-no-handoff
  claude --append-system-prompt-file <abs-path-to-plan.md>

When both sessions complete, run:
  /handoff:eval-implementation compare
```

### Phase 2: `compare`

**Invocation:** `/handoff:eval-implementation compare`

**Steps:**
1. Read `.claude/handoffs/eval-state.json`.
2. Run `compare_implementations.py --state-file <path>` — capture full stdout.
3. Parse metrics table from stdout.
4. Dispatch two grader agents concurrently (one per branch), each receiving:
   - Full diff (inline, from compare script stdout)
   - Worktree path for targeted file reads
   - Plan file path
   - That branch's metrics (subset of table)
   - Path to `grade-implementation.md`
5. Collect scorecards from both graders.
6. Save to `handoff/tests/output/eval/`:
   - `<experiment>-compare.md` — metrics table
   - `<experiment>-with-handoff-scorecard.md`
   - `<experiment>-no-handoff-scorecard.md`
7. Print final report:

```
Eval Results — <experiment>
═════════════════════════════════════════

                        With-Handoff    No-Handoff
[metrics table]

── Implementation Quality ──────────────
Dimension               With-Handoff    No-Handoff
CORRECTNESS             10/10           6/10
TEST_COVERAGE           9/10            7/10
SPEC_COMPLIANCE         9/10            8/10
IMPLEMENTATION_FOCUS    9/10            9/10
CODE_QUALITY            8/10            8/10
OVERALL                 9.5/10          7.1/10
PASS                    YES             NO

── Issues ──────────────────────────────
[list issues from whichever session failed, labeled by session]

Verdict: [one sentence comparing efficiency + quality outcomes]
```

## File Summary

| File | Location | Status |
|------|----------|--------|
| `compare_implementations.py` | `~/.claude/skills/handoff/eval/` | New |
| `grade-implementation.md` | `~/.claude/skills/handoff/eval/prompts/` | New |
| `eval-implementation` skill | `~/.claude/skills/handoff/eval/` | New |
| `eval-state.json` (runtime) | `<repo>/.claude/handoffs/` | Generated by phase 1 |

No changes to `candidate-eval` or any other project repo. All three files live entirely within `~/.claude/skills/handoff/`.

## Constraints

- Score deductions must document: specific defect, file/line, severity, exact deduction amount. Vague "issues found" is not sufficient.
- Worktrees must still exist when phase 2 runs — graders need them for targeted file reads.
- The compare script never uses a worktree-local venv.
- `grade-implementation.md` graders receive diff + worktree access (A+B approach): diff for ordering bugs, worktree reads for missing assertions.
