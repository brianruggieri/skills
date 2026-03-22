---
name: eval-extract
description: Blind evaluation of the handoff extraction prompt against test fixtures. Dispatches fresh agents for extraction and grading to eliminate author bias.
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Agent
---

# Eval: Handoff Extraction

Run blind evaluation of `handoff/prompts/extract.md` against test fixtures.

## Process

### Phase 1: Discover Fixtures

Find fixtures from two sources:

1. **Curated fixtures** (committed): `handoff/tests/fixtures/*.md`
2. **Real transcripts** (captured by `/handoff`): `.claude/handoffs/*.transcript.md`

```bash
ls handoff/tests/fixtures/*.md .claude/handoffs/*.transcript.md 2>/dev/null
```

If no fixtures found in either location, tell the user and stop.

### Phase 2: Load Prompts

Read this file (path relative to repo root):
1. `handoff/eval/prompts/grade.md` — the grading rubric (needed for Phase 6 scorecard parsing)

Note: `handoff/prompts/extract.md` is read by the extractor agents directly — the orchestrator does not need it.

Resolve absolute paths for agent prompts:
```bash
EXTRACT_PROMPT="$(pwd)/handoff/prompts/extract.md"
GRADE_PROMPT="$(pwd)/handoff/eval/prompts/grade.md"
```

### Phase 3: Extract (Blind Agents — All Concurrent)

Dispatch **all** extractor agents concurrently — one per fixture, each with `subagent_type: "general-purpose"`. Each agent is blind: no access to reference outputs, prior extractions, or the grading rubric.

**Agent prompt:**
```
You are performing a blind handoff extraction evaluation. Your ONLY job is to read
a session transcript and apply an extraction prompt to produce a handoff document.

STEP 1: Read the extraction prompt from {EXTRACT_PROMPT}
STEP 2: Read the session transcript from {absolute path to fixture file}
STEP 3: Apply the extraction prompt to the transcript. Produce ONLY the extracted
         handoff document as your final output. No preamble, no explanation.

Do NOT read any other files.
```

Collect each agent's output. These are the extraction results.

### Phase 4: Grade (Blind Agents — All Concurrent)

Once all extractions complete, dispatch **all** grader agents concurrently — one per extraction, each with `subagent_type: "general-purpose"`. Each grader is blind: no access to reference outputs or prior scorecards.

**Agent prompt:**
```
You are grading a handoff extraction. You have access to the grading rubric,
the original transcript, and the extraction output to grade.

STEP 1: Read the grading rubric from {GRADE_PROMPT}
STEP 2: Read the original transcript from {absolute path to fixture file}
STEP 3: Apply the grading rubric to the extraction output below. Produce ONLY
         the scorecard in the exact format specified by the rubric.

<extraction-output>
{the extraction result from Phase 3}
</extraction-output>

Do NOT read any other files.
```

Collect each grader's output. These are the scorecards.

### Phase 5: Save Results

For each fixture, write the results to `handoff/tests/output/eval/`:

```bash
mkdir -p handoff/tests/output/eval
```

Write two files per fixture:
- `{fixture-name}-extraction.md` — the blind extraction output
- `{fixture-name}-scorecard.md` — the grading scorecard

### Phase 6: Present Summary

Parse each scorecard and display a summary table. Extract dimension names and scores from the grader output — do not hardcode dimensions (grade.md is the source of truth).

```
Eval Results — handoff/prompts/extract.md
═══════════════════════════════════════════

Fixture: {name}
  {dimension}: {score}/10  (for each dimension from the scorecard)
  OVERALL:     {score}/10
  PASS:        {YES/NO}

{repeat for each fixture}

Summary: {N}/{total} fixtures passed
```

If any fixture failed, list the ISSUES from its scorecard.

## Notes

- **Comparing across prompt versions:** To A/B test a prompt change, run this eval before and after the change. Compare the scorecards side by side.
- **Subscription-powered.** This eval runs via Claude Code subagents (subscription), not API calls. No API keys needed.
