---
name: honest-assessment
description: "Use after a subagent-heavy build sprint, before reporting benchmark/eval results, or when Brian asks 'have we made progress or added bullshit to a pile?' / 'is this honestly better?'. Audits every claimed metric as field-validated vs mock-derived vs assumed, with anti-inflation grading rules. No flattery — 'small / unfinished / thin wrapper' is a welcome finding."
---

# /honest-assessment

Audit every metric, grade, and progress claim in the current project against evidence. Trust the CODE and the RUNS, not the docs. Do not flatter.

## Step 1 — Collect claims

Gather every number and quality claim from the last sprint's outputs:

```bash
git log --oneline -20
git diff HEAD~10 --stat
grep -rniE '([0-9]+(\.[0-9]+)?%|r² ?= ?|r2 ?= ?|score|accuracy|reduction|improvement|faster|[0-9]+/[0-9]+)' \
	README.md docs/ .claude/ reports/ 2>/dev/null | grep -v node_modules
```

Also scan recent commit messages, PR bodies, and any report/summary files agents produced. Every number found goes into the audit table — no exceptions for "obvious" ones.

## Step 2 — Classify each claim

For every claim, assign exactly one class by tracing it to its origin:

- **field-validated** — ran against real inputs. Requires a citation: the command, the run log path, or reproducible output. If you cannot re-run or point to the run artifact, it is NOT field-validated.
- **mock-derived** — computed from fixtures, synthetic data, or mocked dependencies. Must be labeled as such everywhere it appears. Never present as measured. (Lesson: a metrics project's r²=0.8648 and "68% FP reduction" were mock-derived but presented as real.)
- **assumed/extrapolated** — estimated, projected, or copied from a spec/plan. Flag it.

Then explicitly list **what has NEVER run on real data**. Green mocks hid real privacy leaks in a published plugin project — a passing suite over fixtures proves nothing about production inputs.

Spot-check at least 2 field-validated claims by actually re-running the cited command. If it doesn't reproduce, reclassify as unvalidated.

## Step 3 — Grading anti-inflation rules

When grading work (yours or a subagent's), or auditing grades already given:

1. **Written rubric first.** No rubric → the grade is invalid; write one, regrade.
2. **Correctness bugs that pass the test suite deduct −1.5 to −2** on a 10-point scale. Tests passing is not correctness.
3. **Grade the blind diff, not spec-checklist compliance.** Read the actual code changes with PR descriptions, commit messages, and agent self-reports stripped out — reviewer bias from "bug-free" framing in metadata is empirically strong enough to hit 100% miss rates.
4. **Identical scores across compared branches are a red flag.** Re-examine both with fresh eyes; a real A/B comparison almost never ties. (Lesson: an A/B eval's graders gave both branches 9/10 while one had a real correctness bug.)
5. **Comparisons must be token/effort-matched.** "Multi-agent version scored higher" means nothing if it burned 5x the budget.

## Step 4 — Contamination check

- The grading spec, rubric, and harness must live **outside any repo or directory the graded agent can read**. If the graded agent could have read the rubric, the grade is contaminated — regrade blind. (Lesson: a graded agent run read the grading spec and scored a fake A+ 96.5%.)
- **Verify batch/subagent completion by counting outputs**, not by trusting "done" claims:

```bash
# expected N outputs — count what actually exists
ls output-dir/ | wc -l
grep -c '"status": "complete"' batch-results.jsonl
```

(Lesson: Haiku vision batches died silently while reporting success.) Any mismatch between claimed and counted completions goes in the table as a finding.

- Check that no agent self-report was copied verbatim into a README or summary without independent verification.

## Step 5 — Output

Produce exactly this, in the response (do not write a report file unless asked):

**1. Claim audit table:**

| Claim | Class | Evidence |
|-------|-------|----------|
| "68% FP reduction" | mock-derived | fixtures only — never ran on real prompts |
| "r²=0.8648" | mock-derived | synthetic eval set, run not reproducible |
| "all 40 batches complete" | unvalidated | counted 33 output files, 7 missing |
| "tests pass" | field-validated | `npm test` 2026-07-04, 112/112 |

Evidence column is either a concrete citation or the word **unvalidated**. No third option.

**2. Never-ran-on-real-data list.** Bulleted, blunt.

**3. Validation-first next steps.** Ordered list where every item is a validation action (run X on real input Y, re-grade Z blind), not a feature. Building more on unvalidated claims is adding to the pile.

**Tone:** matter-of-fact. State findings like "the eval harness is a thin wrapper and has never seen real data" without hedging or softening. Do not manufacture numbers to fill gaps — "unmeasured" is the honest answer. If the sprint added no validated progress, say so in the first sentence.
