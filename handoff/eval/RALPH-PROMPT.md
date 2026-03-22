# Ralph Loop: Handoff Extraction Prompt Refinement

You are iterating on `handoff/prompts/extract.md` to improve handoff extraction quality. Each iteration you run a blind evaluation, analyze failures, fix the prompt, and re-evaluate.

## Success Criteria

All 4 fixtures must PASS (overall >= 7.0, no dimension below 4):
- `handoff/tests/fixtures/minimal-bugfix.md`
- `handoff/tests/fixtures/paste-heavy-debug.md`
- `handoff/tests/fixtures/exploratory-no-plan.md`
- `handoff/tests/fixtures/real-planning-session.md`

When all 4 pass, output `<promise>ALL FIXTURES PASS</promise>` and stop.

## Iteration Steps

### Step 1: Check Prior Results

Read all scorecards in `handoff/tests/output/eval/*-scorecard.md`. If all 4 exist and all show `PASS: YES`, output the promise and stop.

### Step 2: Run Blind Eval

For each fixture, dispatch TWO agents sequentially:

**Extractor agent** (blind — no access to rubric, prior outputs, or scorecards):
```
You are performing a blind handoff extraction evaluation. Your ONLY job is to read
a session transcript and apply an extraction prompt to produce a handoff document.

STEP 1: Read the extraction prompt from {absolute path to handoff/prompts/extract.md}
STEP 2: Read the session transcript from {absolute path to fixture}
         (read the full file in chunks if needed)
STEP 3: Apply the extraction prompt to the transcript. Produce ONLY the extracted
         handoff document as your final output. No preamble, no explanation.

Do NOT read any other files. Do NOT look at reference outputs or prior extractions.
```

**Grader agent** (blind — no access to prior scorecards):
```
You are grading a handoff extraction. You have access to the grading rubric,
the original transcript, and the extraction output to grade.

STEP 1: Read the grading rubric from {absolute path to handoff/eval/prompts/grade.md}
STEP 2: Read the original transcript from {absolute path to fixture}
         (read the full file in chunks if needed)
STEP 3: Apply the grading rubric to the extraction output below. Produce ONLY
         the scorecard in the exact format specified by the rubric.

<extraction-output>
{the extraction result from the extractor agent}
</extraction-output>

Do NOT read any other files.
```

Run all 4 extractor agents in parallel. Then run all 4 grader agents in parallel.

Save results to `handoff/tests/output/eval/{fixture-name}-extraction.md` and `{fixture-name}-scorecard.md`.

### Step 3: Analyze Failures

For each fixture that got `PASS: NO`:
1. Read the scorecard ISSUES list
2. Read the extraction output to see the specific problem
3. Read `handoff/prompts/extract.md` to find the root cause in the prompt

### Step 4: Fix the Prompt

Edit `handoff/prompts/extract.md` to address the root causes. Rules:
- Make minimal, targeted changes — do not rewrite the entire prompt
- Each change must address a specific scored dimension that failed
- Do not weaken existing rules — add clarification or new rules
- Do not modify fixtures or the grading rubric (`handoff/eval/prompts/grade.md`)

### Step 5: Verify

After fixing, go back to Step 2 and re-run the full eval to verify the fix didn't regress other fixtures.

## Constraints

- NEVER modify test fixtures in `handoff/tests/fixtures/`
- NEVER modify the grading rubric in `handoff/eval/prompts/grade.md`
- ONLY modify `handoff/prompts/extract.md`
- Use subagents (Agent tool) for extraction and grading — they must be blind
- Keep changes to extract.md minimal and targeted
