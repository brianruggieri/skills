---
name: eval-implementation
description: Two-phase skill for running A/B implementation experiments. Phase 1 creates worktrees and prints launch commands. Phase 2 runs compare_implementations.py, dispatches blind graders, and prints the final report.
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Agent
---

# Eval: Implementation A/B Test

Run a controlled experiment comparing two implementation sessions — one with a handoff document, one with the plan only.

## Invocation

```
/handoff:eval-implementation setup --source-branch <branch> --plan <abs-path> --handoff <abs-path>
/handoff:eval-implementation compare
```

---

## Phase 1: `setup`

### Arguments

- `--source-branch` — branch both worktrees are created from (required)
- `--plan` — absolute path to the implementation plan file (required)
- `--handoff` — absolute path to the handoff document for Session A (required)

### Name Derivation

Strip `feat/` prefix from `--source-branch`. E.g., `feat/eligibility-hard-caps` → `eligibility-hard-caps`. If the branch does not start with `feat/`, use the full branch name.

### Steps

1. Create two worktrees from source branch:
   ```bash
   git worktree add .worktrees/eval-with-handoff -b feat/<name>-with-handoff <source-branch>
   git worktree add .worktrees/eval-no-handoff   -b feat/<name>-no-handoff   <source-branch>
   ```

2. Read plan file to extract task count: count lines matching `^\d+\.` with no leading whitespace.

3. Write `.claude/handoffs/eval-state.json`:
   ```json
   {
     "experiment": "<name>",
     "source_branch": "<branch>",
     "plan_file": "<abs-path>",
     "handoff_file": "<abs-path>",
     "task_count": <N>,
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

---

## Phase 2: `compare`

### Error Handling

- If `.claude/handoffs/eval-state.json` is missing: print error and stop.
- If either worktree path in the state file is not a valid directory: print warning, proceed — Code section metrics show `[worktree not found]`, graders run on diff only.

### Steps

1. Read `.claude/handoffs/eval-state.json`.

2. Locate `compare_implementations.py`:
   ```bash
   STATE_FILE=".claude/handoffs/eval-state.json"
   REPO_ROOT="$(cd "$(dirname "$STATE_FILE")/../.." && pwd)"
   COMPARE="$REPO_ROOT/handoff/eval/compare_implementations.py"
   ```
   Run it and capture stdout:
   ```bash
   python "$COMPARE" --state-file "$STATE_FILE"
   ```

3. Split stdout on `---DIFF---` sentinel: everything before = metrics table; everything after = full diff.

4. Read `grade-implementation.md` from `~/.claude/skills/handoff/eval/prompts/grade-implementation.md`. Inject its full content inline into each grader agent's prompt.

5. Dispatch two grader agents **concurrently** — one per branch. Each agent prompt contains:

   ```
   You are grading an implementation session. Use ONLY the materials provided below.
   Do NOT read any files except those under the worktree path listed.

   RUBRIC:
   <full content of grade-implementation.md>

   BRANCH: <branch-name>
   WORKTREE PATH: <worktree-abs-path>
   PLAN FILE: <plan-abs-path>

   EFFICIENCY METRICS FOR THIS SESSION:
   <subset of metrics table for this branch>

   DIFF (this branch vs main):
   <full diff>

   Grade this implementation using the rubric above. Read test files from the
   worktree path as needed to verify intermediate field assertions.
   Produce ONLY the scorecard in the exact format specified by the rubric.
   ```

6. Collect scorecards from both graders.

7. Save to `~/.claude/skills/handoff/tests/output/eval/`:
   - `<experiment>-compare.md` — metrics table
   - `<experiment>-with-handoff-scorecard.md`
   - `<experiment>-no-handoff-scorecard.md`

8. Print final report:

   ```
   Eval Results — <experiment>
   ═════════════════════════════════════════

   <metrics table>

   ── Implementation Quality ──────────────
   Dimension               With-Handoff    No-Handoff
   CORRECTNESS             <score>/10      <score>/10
   TEST_COVERAGE           <score>/10      <score>/10
   SPEC_COMPLIANCE         <score>/10      <score>/10
   IMPLEMENTATION_FOCUS    <score>/10      <score>/10
   CODE_QUALITY            <score>/10      <score>/10
   OVERALL                 <score>/10      <score>/10
   PASS                    YES/NO          YES/NO

   ── Issues ──────────────────────────────
   <issues from failing session(s), prefixed with session name>
   (if both sessions pass, shows "None")

   Verdict: <one sentence comparing efficiency + quality outcomes>
   ```
