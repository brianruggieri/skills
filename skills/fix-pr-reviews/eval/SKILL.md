---
name: eval-triage
description: Blind evaluation of the fix-pr-reviews triage prompt against test fixtures. Dispatches fresh agents for triage and grading to eliminate author bias.
allowed-tools: Read Write Bash Glob Agent
---

# Eval: PR Comment Triage

Run blind evaluation of `skills/fix-pr-reviews/prompts/triage.md` against test fixtures.

All repo-relative paths below assume the repo root as CWD (the skill lives at
`skills/fix-pr-reviews/`).

## Process

### Phase 1: Discover Fixtures

Find fixtures from:

1. **Curated fixtures** (committed): `skills/fix-pr-reviews/tests/fixtures/*.md`

```bash
bash -O nullglob -c '
  files=(skills/fix-pr-reviews/tests/fixtures/*.md)
  if ((${#files[@]} == 0)); then
    echo "No fixtures found in skills/fix-pr-reviews/tests/fixtures"
    exit 1
  fi
  printf "%s\n" "${files[@]}"
'
```

If no fixtures found, tell the user and stop.

### Phase 2: Load Prompts

Resolve absolute paths for agent prompts:
```bash
TRIAGE_PROMPT="$(pwd)/skills/fix-pr-reviews/prompts/triage.md"
GRADE_PROMPT="$(pwd)/skills/fix-pr-reviews/eval/prompts/grade.md"
```

### Phase 3: Triage (Blind Agents — All Concurrent)

Dispatch **all** triage agents concurrently — one per fixture, each with `subagent_type: "general-purpose"`. Each agent is blind: no access to reference outputs, prior triages, or the grading rubric.

**Agent prompt:**
```
You are performing a blind PR comment triage evaluation. Your ONLY job is to read
a PR fixture (comments + source code) and apply a triage prompt to categorize each
review comment.

STEP 1: Read the triage prompt from {TRIAGE_PROMPT}
STEP 2: Read the PR fixture from {absolute path to fixture file}
STEP 3: Apply the triage prompt to the fixture. Produce ONLY the triage output
         in the exact format specified by the triage prompt. No preamble, no explanation.

Do NOT read any other files.
```

Collect each agent's output. These are the triage results.

### Phase 4: Grade (Blind Agents — All Concurrent)

Once all triages complete, dispatch **all** grader agents concurrently — one per triage, each with `subagent_type: "general-purpose"`. Each grader is blind: no access to reference outputs or prior scorecards.

**Agent prompt:**
```
You are grading a PR comment triage. You have access to the grading rubric,
the original PR fixture, and the triage output to grade.

STEP 1: Read the grading rubric from {GRADE_PROMPT}
STEP 2: Read the original PR fixture from {absolute path to fixture file}
STEP 3: Apply the grading rubric to the triage output below. Produce ONLY
         the scorecard in the exact format specified by the rubric.

<triage-output>
{the triage result from Phase 3}
</triage-output>

Do NOT read any other files.
```

Collect each grader's output. These are the scorecards.

### Phase 5: Save Results

For each fixture, write the results to `skills/fix-pr-reviews/tests/output/eval/`:

```bash
mkdir -p skills/fix-pr-reviews/tests/output/eval
```

Write two files per fixture:
- `{fixture-name}-triage.md` — the blind triage output
- `{fixture-name}-scorecard.md` — the grading scorecard

### Phase 6: Present Summary

Parse each scorecard and display a summary table.

```
Eval Results — skills/fix-pr-reviews/prompts/triage.md
═══════════════════════════════════════════════════
Fixture: {name}
  {dimension}: {score}/10  (for each dimension from the scorecard)
  OVERALL:     {score}/10
  PASS:        {YES/NO}

{repeat for each fixture}

Summary: {N}/{total} fixtures passed
```

If any fixture failed, list the ISSUES from its scorecard.

## Notes

- **Subscription-powered.** This eval runs via Claude Code subagents (subscription), not API calls.
- **Comparing prompt versions:** Run eval before and after a change to `triage.md`. Compare scorecards side by side.
