# Handoff A/B Test: skills — Eval Harness Implementation (2026-03-24)

Meta-experiment: dogfooding the handoff evaluation methodology on its own implementation.
Both sessions implemented the same three-file eval infrastructure from the same plan.

**This is the first evidence entry measuring the effect of handoff context on a
*prescriptive* plan** (vs. the 2026-03-24 candidate-eval test, which used an
open-ended TDD plan that allowed ordering choices).

## Setup

- **Project:** skills (this repo — `~/.claude/skills/`)
- **Codebase:** ~2,500 LOC Python/Markdown, handoff skill infrastructure
- **Feature:** Three-file eval harness — `compare_implementations.py`, `grade-implementation.md`, `eval-implementation/SKILL.md`
- **Plan:** `docs/superpowers/plans/2026-03-24-handoff-eval-implementation-harness.md` (6-task TDD plan)
- **Model:** Claude Sonnet 4.6 (default)
- **Branches:** `feat/eval-harness-with-handoff` (with-handoff), `feat/eval-harness-no-handoff` (no-handoff)

The plan was deliberately prescriptive: every task included exact file paths, complete
function signatures, full unit test code, and exact expected output strings. No ordering
ambiguity existed. This was by design — the plan was written in the same session that
produced the handoff.

## Session A: With Handoff

Handoff document: `20260324-224856-skill-eval-harnesses.md`
- 7 decisions (two-phase invocation, state file, grader inputs, JSONL auto-extraction, etc.)
- 4 do-not-retry constraints (rubric injection inline, task_count from state, separate numstat/diff, no spec-only grading)
- 5 constraints (score deduction specificity, worktrees must persist, no worktree venv, inline rubric, task_count primary source)
- Key context transferred: `---DIFF---` sentinel, `tokens_per_f2p` derived metric, blind grader agent design, JSONL encoding pattern

### Metrics
- **Effective tokens:** 83,357
- **Tool calls:** 76 total
- **Turns:** ~90
- **Tests passed:** all green (24 tests)
- **Duration:** ~50 min

### Code Review Score: 9.9/10 PASS

```
CORRECTNESS:           10/10 | No ordering bugs; all functions correct
TEST_COVERAGE:          10/10 | All intermediate fields asserted; required markers present
SPEC_COMPLIANCE:         9/10 | Minor: one sentinel split used str.split vs partition (functionally correct)
IMPLEMENTATION_FOCUS:   10/10 | Only specified files touched
CODE_QUALITY:            10/10 | Consistent patterns, no dead code
OVERALL: 9.9
PASS: YES
```

## Session B: No Handoff

Plan only — same 6-task TDD instructions, no prior session context.

### Metrics
- **Effective tokens:** 65,520
- **Tool calls:** 77 total
- **Turns:** ~85
- **Tests passed:** all green (24 tests)
- **Duration:** ~45 min

Note: Session B experienced an API 500 error mid-run (after tasks 1–2 were committed),
requiring a re-launch. Second run completed tasks 3–6. Total metrics aggregated across
both runs.

### Code Review Score: 9.8/10 PASS

```
CORRECTNESS:           10/10 | No logic errors; implementation functionally correct
TEST_COVERAGE:          10/10 | Full coverage; all paths tested
SPEC_COMPLIANCE:         9/10 | Same minor sentinel split variant as Session A
IMPLEMENTATION_FOCUS:   10/10 | Only specified files touched
CODE_QUALITY:            9/10 | Type annotations downgraded (str instead of str | None)
OVERALL: 9.8
PASS: YES
```

**Note on type annotation issue:** Session B downgraded several type annotations from
`str | None` to `str` for functions that CAN return `None` — technically incorrect
regardless of Python version. The grader rated this as a "compatibility choice" rather
than a correctness defect. This is a rubric gap: the CORRECTNESS dimension should include
a type safety check ("for functions with a `return None` path, verify annotation
includes `None` or `Optional`").

---

## Efficiency Comparison

| Metric | With Handoff | No Handoff | Delta |
|--------|-------------|------------|-------|
| Duration | ~50 min | ~45 min | +11% |
| **Effective tokens** | **83,357** | **65,520** | **+27%** |
| **Tool calls** | **76** | **77** | −1% |
| Tests passed | 24 | 24 | 0 |

**Result: handoff overhead exceeded handoff benefit.** Session A (with-handoff) used
27% MORE tokens than Session B (no-handoff). Tool call count was nearly identical.
Quality was near-identical (9.9 vs 9.8).

---

## Code Quality Comparison

### Scores

| Session | Score | Notes |
|---------|-------|-------|
| with-handoff | **9.9/10** | Clean implementation matching spec exactly |
| no-handoff | **9.8/10** | Functionally identical; type annotation downgrade |

**Neither session had correctness bugs.** Both converged to near-identical
implementations. The prescriptive plan provided complete code for every task,
leaving no implementation decisions to be made.

### Why No Quality Benefit?

In the 2026-03-24 candidate-eval test, the handoff prevented an ordering bug because:
1. The plan had an open-ended insertion point ("add cap logic in quick_match.py")
2. The handoff specified the exact location and ordering constraint

In this test, the plan provided complete function implementations. There was no
ordering decision for the handoff to constrain.

### Why Reversed Efficiency?

The handoff document injected ~3,500 tokens of context into every request via
`--append-system-prompt-file`. For a plan that already encoded all insertion points,
constraints, and code, this was pure overhead. The no-handoff session had no
re-exploration penalty because the plan gave it everything it needed.

---

## Meta-Finding: Handoff ROI Scales with Plan Ambiguity

| Plan Type | Handoff Benefit |
|-----------|----------------|
| Open-ended insertion points, no prescribed code | HIGH — prevents ordering bugs, eliminates re-exploration |
| Prescriptive (exact file+line+code) | NEGATIVE — injection overhead > benefit |
| Somewhere in between | TBD |

The 2026-03-24 candidate-eval test used a TDD plan with task-level guidance; the
handoff's "Constraints" section was the authoritative source for insertion points.
This test used a plan that was essentially a diff — the handoff was redundant.

**Implication for the eval skill:** Phase 1 (`setup`) should detect plan prescriptiveness
and warn if the plan already encodes all insertion points. High prescriptiveness suggests
the handoff is unlikely to add value, and the experiment may not produce a meaningful
signal.

---

## Rubric Gap Identified

The `grade-implementation.md` rubric does not have a type safety check. The Session B
type annotation downgrade (`str` instead of `str | None` for functions that can return
`None`) is technically incorrect, but the grader scored it 9/10 CODE_QUALITY with a
note about "compatibility choice."

**Proposed addition to CORRECTNESS dimension:**
> For any function with a `return None` path, verify the annotation includes `None`
> or `Optional[T]`. A bare `str` annotation on a function that returns `None` in some
> branch is incorrect regardless of Python version. Deduct 1 point per affected
> function (max −3).

---

## Verdict

| Dimension | With Handoff | No Handoff |
|-----------|-------------|------------|
| Efficiency (tokens) | ✗ 83,357 (+27%) | ✓ 65,520 |
| Efficiency (tool calls) | ✓ 76 | ✓ 77 |
| Correctness | ✓ No bugs | ✓ No bugs |
| Type annotations | ✓ Correct | ✗ Minor downgrade |
| Score | **9.9/10** | **9.8/10** |

For prescriptive plans with complete code, handoff context provides no efficiency
benefit and a marginal quality benefit that doesn't justify the injection overhead.
Handoff ROI is concentrated in plans with open-ended insertion points.

---

## Raw Stats (machine-readable)

```json
{
  "experiment": "eval-harness-meta-ab-test",
  "type": "implementation",
  "date": "2026-03-24",
  "handoff_file": "20260324-224856-skill-eval-harnesses.md",
  "plan_file": "2026-03-24-handoff-eval-implementation-harness.md",
  "plan_prescriptiveness": "high",
  "sessions": {
    "with-handoff": {
      "branch": "feat/eval-harness-with-handoff",
      "duration_min": 50,
      "tokens": {
        "total_effective": 83357
      },
      "tool_calls": {
        "total": 76
      },
      "turns": 90,
      "tests_passed": 24,
      "tests_failed": 0,
      "code_review_score": "9.9/10",
      "bugs_found": []
    },
    "no-handoff": {
      "branch": "feat/eval-harness-no-handoff",
      "duration_min": 45,
      "tokens": {
        "total_effective": 65520
      },
      "tool_calls": {
        "total": 77
      },
      "turns": 85,
      "tests_passed": 24,
      "tests_failed": 0,
      "code_review_score": "9.8/10",
      "bugs_found": [
        {
          "severity": "minor-typing",
          "description": "Type annotations downgraded: str | None -> str for None-returning functions",
          "impact": "Technically incorrect; missed by grader as compatibility choice"
        }
      ]
    }
  },
  "deltas": {
    "effective_tokens_pct": +27,
    "tool_calls_pct": -1,
    "duration_pct": +11,
    "test_delta": 0,
    "score_delta": "+0.1 (9.9 vs 9.8)",
    "quality_equivalent": true
  },
  "key_finding": "Prescriptive plan with complete code eliminated handoff efficiency benefit entirely. Token overhead from injection (+27%) exceeded any exploration savings. Quality near-identical. Handoff ROI scales with plan ambiguity, not plan length."
}
```
