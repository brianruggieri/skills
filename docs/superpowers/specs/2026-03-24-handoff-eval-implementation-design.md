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
    ↓ (user runs both sessions manually)
/handoff:eval-implementation compare →  runs compare_implementations.py
                                     →  dispatches 2 grader agents (blind, concurrent)
                                     →  assembles final report
```

## Component 1: `compare_implementations.py`

**Location:** `~/.claude/skills/handoff/eval/compare_implementations.py`

**Role:** Pure reporting tool. Reads state file, diffs branches, prints metrics table followed by a sentinel line and full git diff to stdout. No grading, no agent dispatch. Can be run standalone outside the skill.

### CLI Arguments

```
--state-file              path to state file (default: <repo-root>/.claude/handoffs/eval-state.json)
--repo-root               override auto-detect from CWD
--venv                    override venv auto-detect (checks <repo-root>/.venv, venv, active env)
--task-count              override task count from state file (for manual correction only —
                          phase 1 always writes task_count to the state file; this arg
                          exists only as an escape hatch, not a primary input)
--with-handoff-branch     override branch name from state file
--no-handoff-branch       override branch name from state file
--with-handoff-worktree   override worktree path from state file
--no-handoff-worktree     override worktree path from state file
```

All values default to state file. Explicit args override.

### Venv Detection Order

1. `<repo-root>/.venv`
2. `<repo-root>/venv`
3. Active `$VIRTUAL_ENV`

Never uses a worktree-local venv — worktrees share the main repo's venv.

### Output Format

The script prints the metrics table, then a sentinel line `---DIFF---`, then the full git diff. The skill uses the sentinel to split metrics from diff when capturing stdout.

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
  F2P (new tests)       <computed>      <computed>      —
  P2P regressions       0 broken        0 broken        —
Tokens / F2P test       <computed>      <computed>      —

── Code ────────────────────────────────────────────────
Metric                  With-Handoff    No-Handoff      Delta
Commits                 <computed>      <computed>      —
Files changed           <computed>      <computed>      —
Lines added             <computed>      <computed>      —
Lines removed           <computed>      <computed>      —
Test/source ratio       <computed>      <computed>      —
Patch efficiency        <computed>      <computed>      —

═════════════════════════════════════════════════════════
---DIFF---
<full git diff output>
```

All `<computed>` fields are required and populated from git and pytest at runtime. If a worktree path is missing or invalid, those rows print `[worktree not found]`.

### Metric Definitions

- **Exploration ratio:** `(Bash + Read) / total_tool_calls` — high ratio signals excessive codebase re-exploration
- **Delegation ratio:** `Agent / total_tool_calls` — high ratio signals task clarity and confidence
- **Input/output ratio:** `cache_read / output_tokens` — high ratio signals lots of context re-reading
- **Tokens / task:** `total_effective_tokens / task_count` (task_count from state file)
- **F2P:** net new test functions on this branch vs. main — computed via `git diff main..<branch> --numstat`, filtered to test files (`test_*.py`, `*_test.py`, files under `tests/`)
- **P2P regressions:** tests that existed on main and now fail (run pytest on each branch against the shared test suite)
- **Tokens / F2P test:** `total_effective_tokens / f2p_count`
- **Test/source ratio:** test lines changed / source lines changed, from `git diff --numstat` filtered by filename; computed separately from the full diff using `git diff --numstat main..<branch>`
- **Patch efficiency:** `(lines_added + lines_removed) / f2p_count` — lower = more surgical
- **Code churn (not yet implemented):** intended definition is "lines revised within two weeks of initial write" (from `git log --follow -p`). The current `compare_implementations.py` does not compute or display this metric.

Note: Some `<computed>` fields in the compare script's JSON output may legitimately be missing/`null` (for example, when worktrees or virtual environments are unavailable). Downstream consumers must treat these metrics as optional rather than required.

F2P/P2P split and test/source ratio use `git diff --numstat` (separate command from full diff). Full diff is printed after `---DIFF---` sentinel.

## Component 2: `grade-implementation.md`

**Location:** `~/.claude/skills/handoff/eval/prompts/grade-implementation.md`

**Role:** Rubric injected inline into grader agent prompts by the skill. Each grader receives: the diff between this branch and main, the worktree path for targeted file reads, the plan file path, and this branch's metrics. Two graders run concurrently — one per branch — each grading independently.

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
1. Examine this branch's diff against main for values computed on the wrong side of a mutation — these are bugs even if all tests pass.
2. Check ordering: any field assigned *before* the mutation that changes its inputs is wrong (e.g., `percentage = score * 100` before `score = 0.0` when the spec requires 0% after the cap).
3. Deduct 3 points per ordering bug; 2 points per logic error visible in the diff.

### Test Coverage Dimension — Critical Instructions

The grader must:
1. Open the test file(s) for any field computed inside a conditional — use the worktree path for this read.
2. Verify the field is explicitly asserted under the failure/cap path (not just that the test runs — check the assert statement value).
3. Deduct 2 per missing assertion on an intermediate field under a cap/error path; 1 per missing required marker (e.g., `@pytest.mark.slow`).

### Implementation Focus Dimension — Deduction Guide

- Significant scope creep (changes to files not mentioned in the plan, unrelated to the feature): −2
- Minor scope creep (cosmetic edits or formatting in unrelated files): −1
- Unnecessary files touched (plan specifies insertion points; extra files modified without justification): −1 per file

### Code Quality Dimension — Deduction Guide

- Clear violation of existing patterns (different naming convention, wrong abstraction level, duplicated logic): −2
- Minor violations (small inconsistency, single dead import): −0.5 per instance, max −2 total

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
- <specific issue: what is wrong, which file/line, severity, exact deduction>
(omit ISSUES block entirely if PASS is YES)
```

## Component 3: `/handoff:eval-implementation` Skill

**Location:** `~/.claude/skills/handoff/eval-implementation/SKILL.md`

This is a peer skill to `eval/` (which contains `eval-extract`), not nested inside it.

### Phase 1: `setup`

**Invocation:** `/handoff:eval-implementation setup --source-branch <branch> --plan <path> --handoff <path>`

**Arguments:**
- `--source-branch` — the branch both worktrees are created from (required)
- `--plan` — absolute path to the implementation plan file (required; also used to extract task count)
- `--handoff` — absolute path to the handoff document for Session A (required)

**`<name>` derivation:** Strip the `feat/` prefix from `--source-branch`. E.g., `feat/eligibility-hard-caps` → `eligibility-hard-caps`. If the branch does not start with `feat/`, use the full branch name.

**Steps:**
1. Create two worktrees from source branch:
   - `.worktrees/eval-with-handoff` → branch `feat/<name>-with-handoff`
   - `.worktrees/eval-no-handoff` → branch `feat/<name>-no-handoff`
2. Read plan file to extract task count: count lines matching `^\d+\.` with no leading whitespace (top-level numbered list items only — nested numbered sub-lists are indented and excluded).
3. Write `.claude/handoffs/eval-state.json`:

```json
{
  "experiment": "<name>",
  "source_branch": "<branch>",
  "plan_file": "<abs-path>",
  "handoff_file": "<abs-path>",
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

Session A (with-handoff) — receives handoff document + plan:
  cd .worktrees/eval-with-handoff
  claude --append-system-prompt-file <abs-path-to-handoff.md>

  Note: the handoff document is expected to contain or reference the plan.
  If it does not, pass both files:
  claude --append-system-prompt-file <handoff.md> --append-system-prompt-file <plan.md>

Session B (no-handoff) — receives plan only, no handoff context:
  cd .worktrees/eval-no-handoff
  claude --append-system-prompt-file <abs-path-to-plan.md>

When both sessions complete, run:
  /handoff:eval-implementation compare
```

### Phase 2: `compare`

**Invocation:** `/handoff:eval-implementation compare`

**Error handling:** If `.claude/handoffs/eval-state.json` is missing, print a clear error and stop. If either `worktree` path in the state file is not a valid directory, print a warning and proceed — those sessions' Code section metrics will show `[worktree not found]`, but graders can still run using the diff alone.

**Steps:**
1. Read `.claude/handoffs/eval-state.json`.
2. Run `compare_implementations.py --state-file <path>` — capture full stdout.
3. Split stdout on `---DIFF---` sentinel: everything before = metrics table; everything after = full diff.
4. Read `grade-implementation.md` content from `~/.claude/skills/handoff/eval/prompts/grade-implementation.md` — inject inline into each grader prompt (do not pass a path; the grader reads no files except worktree files).
5. Dispatch two grader agents concurrently (one per branch), each receiving inline in their prompt:
   - The full diff (from step 3)
   - The worktree path for targeted file reads
   - The plan file path
   - That branch's metrics (parsed from metrics table)
   - The full rubric content (from step 4)
6. Collect scorecards from both graders.
7. Save to `~/.claude/skills/handoff/tests/output/eval/`:
   - `<experiment>-compare.md` — metrics table
   - `<experiment>-with-handoff-scorecard.md`
   - `<experiment>-no-handoff-scorecard.md`
8. Print final report:

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

── Issues (no-handoff) ─────────────────
[issues from failing session's scorecard, prefixed with session name]
(if both sessions pass, this section reads "None")

Verdict: [one sentence comparing efficiency + quality outcomes]
```

If a passing session has no ISSUES block in its scorecard, the Issues section for that session is omitted from the report (or shows "None" if both pass).

## File Summary

| File | Location | Status |
|------|----------|--------|
| `compare_implementations.py` | `~/.claude/skills/handoff/eval/` | New |
| `grade-implementation.md` | `~/.claude/skills/handoff/eval/prompts/` | New |
| `SKILL.md` (eval-implementation) | `~/.claude/skills/handoff/eval-implementation/` | New |
| `eval-state.json` (runtime) | `<target-repo>/.claude/handoffs/` | Generated by phase 1 |

No changes to `candidate-eval` or any other project repo. All three skill files live entirely within `~/.claude/skills/handoff/`.

## Constraints

- Score deductions must document: specific defect, file/line, severity, exact deduction amount. Vague "issues found" is not sufficient.
- Worktrees must still exist when phase 2 runs — graders need them for targeted file reads. If missing, Code metrics show `[worktree not found]` and graders proceed on diff alone.
- The compare script never uses a worktree-local venv.
- `grade-implementation.md` content is injected inline by the skill into grader prompts — graders do not resolve file paths themselves.
- `task_count` is always written to the state file by phase 1 (read from the plan). `--task-count` CLI arg is a manual override only, not a required input.
