# Handoff A/B Test: candidate-eval — Implementation Session (2026-03-24)

Real-world comparison of two Claude Code implementation sessions run back-to-back on the same feature
in isolated git worktrees. Tests whether a handoff document changes implementation quality, not just
exploration efficiency.

**This is the first evidence entry measuring implementation output quality** (vs. 2026-03-22 which
measured exploration quality in a `/grill-me` session).

## Setup

- **Project:** candidate-eval (privacy-first job fit assessment pipeline)
- **Codebase:** ~11,000 LOC Python, 1161 tests, Chrome extension, FastAPI server
- **Feature:** Eligibility hard caps — new `eligibility_evaluator.py` module + grade-to-F cap when binary gates unmet
- **Plan:** `docs/superpowers/plans/2026-03-24-eligibility-hard-caps.md` (6-task TDD plan)
- **Model:** Claude Sonnet 4.6 (default)
- **Branches:** `feat/eligibility-hard-caps-a` (with-handoff), `feat/eligibility-hard-caps-b` (no-handoff)

## Session A: With Handoff

```bash
cd .worktrees/with-handoff
claude --append-system-prompt-file /abs/path/to/.claude/handoffs/20260324-183624-eligibility-hard-caps.md
```

Handoff document: `20260324-183624-eligibility-hard-caps.md`
- 7 decisions, 4 do-not-retry constraints, 5 constraints, 4 next steps, 9 key files
- Key facts transferred: `_evaluate_eligibility()` is inert, `eligibility_passed` is stored but unused,
  exact insertion points in `quick_match.py`, prior session's design choices (separate evaluator module,
  A+C UX surface, no schema field for `blocker_reason`)

### Metrics
- **Duration:** 50.8 min
- **Effective tokens:** 7,768,652 (129 input + 30,118 output + 7,738,405 cache read + 200,440 cache create)
- **Tool calls:** 63 total (Agent: 26, Read: 8, Bash: 4, TaskUpdate: 16, TaskCreate: 6, Skill: 2, ToolSearch: 1)
- **Turns:** 115
- **Tests passed:** 1163 / 0 failed

### Behavior
- Used 26 Agent subagents — delegated implementation tasks immediately, confident about targets
- Only 4 Bash calls and 8 Read calls — minimal codebase re-exploration
- `eligibility_evaluator.py` written correctly on first pass

## Session B: No Handoff

```bash
cd .worktrees/no-handoff
claude --append-system-prompt-file /abs/path/to/docs/superpowers/plans/2026-03-24-eligibility-hard-caps.md
```

No handoff document. Plan only — same 6-task TDD instructions, but no prior session context.

### Metrics
- **Duration:** 49.7 min
- **Effective tokens:** 13,190,485 (183 input + 39,913 output + 13,150,389 cache read + 253,143 cache create)
- **Tool calls:** 112 total (Bash: 31, Read: 36, Agent: 18, TaskUpdate: 12, TaskCreate: 6, Skill: 3, Edit: 4, Glob: 1, ToolSearch: 1)
- **Turns:** 161
- **Tests passed:** 1161 / 0 failed

### Behavior
- Used 31 Bash + 36 Read calls — extensive codebase exploration before each task
- 18 Agent subagents — fewer delegations, more inline work
- `eligibility_evaluator.py` written correctly (converged to identical implementation as Session A)

---

## Efficiency Comparison

| Metric | With Handoff | No Handoff | Delta |
|--------|-------------|------------|-------|
| Duration | 50.8 min | 49.7 min | −2% |
| **Effective tokens** | **7,768,652** | **13,190,485** | **+70%** |
| Cache read | 7,738,405 | 13,150,389 | +70% |
| Output tokens | 30,118 | 39,913 | +32% |
| **Tool calls** | **63** | **112** | **+78%** |
| Bash calls | 4 | 31 | +675% |
| Read calls | 8 | 36 | +350% |
| Agent calls | 26 | 18 | −31% |
| Turns | 115 | 161 | +40% |

Wall-clock time was identical — the bottleneck is generation, not exploration. All efficiency gains
are in tokens (cost) and tool calls (exploration overhead).

---

## Code Quality Comparison

### Test Results

| | With Handoff | No Handoff |
|--|--|--|
| Tests passed | **1163** | 1161 |
| Tests failed | 0 | 0 |

### Scores

| Session | Score | Reasoning |
|---------|-------|-----------|
| with-handoff | **9/10** | Correct implementation, all constraints met, strong test coverage |
| no-handoff | **7/10** | One correctness bug (runtime behavior), one missing test marker |

**Revised scores from original 9/9** — the initial review rated both at 9/10. On closer post-review
diff analysis, two concrete defects were found in the no-handoff branch that warranted a lower score:

#### Defect 1 — Runtime correctness bug (−1.5)

`partial_percentage` computed before the eligibility cap in `quick_match.py`:

```python
# no-handoff (wrong) — partial_percentage reflects pre-cap score
partial_percentage = round(overall_score * 100, 1)   # e.g. 82.0%
unmet_gates = [g for g in eligibility_gates if g.status == "unmet"]
if unmet_gates:
    overall_score = 0.0  # percentage already stored — too late

# with-handoff (correct) — partial_percentage reflects capped score
unmet_gates = [g for g in eligibility_gates if g.status == "unmet"]
if unmet_gates:
    overall_score = 0.0
partial_percentage = round(overall_score * 100, 1)   # correctly 0.0%
```

This produces a visible bug: when eligibility is blocked, the assessment would display a non-zero
partial percentage (e.g., "82% match") even though `overall_grade = "F"`. All tests passed because
no test asserted the value of `partial_percentage` under an unmet gate.

#### Defect 2 — Missing `@pytest.mark.slow` on server test (−0.5)

`test_full_assess_preserves_eligibility_cap` in `test_server.py` was not marked `@pytest.mark.slow`.
The plan explicitly required this. The with-handoff version has the marker; the no-handoff version
does not. The test would run in the fast suite, potentially causing slow CI times or flaky behavior
if the full-assess endpoint requires real async I/O.

### What the Handoff Prevented

The `partial_percentage` ordering bug is exactly the kind of error a "Do Not Retry" / "Constraints"
section prevents: the handoff document specified that the cap must apply before any downstream
computation, and named the exact insertion point. Without that context, the no-handoff session placed
the cap logically (after `_compute_overall_score`) but before the follow-on computation happened to
be refactored — a plausible ordering that turns out to be wrong.

### Shared Strengths (both sessions)
- `eligibility_evaluator.py` — **identical** between branches: frozenset classification, `_classify()`
  + `_resolve()`, `_PCT_PATTERN` regex for travel, `evaluate_gates()` public API
- All 3 pitfalls avoided: no `blocker_reason` field, no `EligibilityGate.evaluate()` method, no inline evaluation in `quick_match.py`
- All primary constraint checks passed

---

## Verdict

| Dimension | With Handoff | No Handoff |
|-----------|-------------|------------|
| Efficiency (tokens) | ✓ 7.77M | ✗ 13.19M (+70%) |
| Efficiency (tool calls) | ✓ 63 | ✗ 112 (+78%) |
| Correctness | ✓ No bugs | ✗ `partial_percentage` ordering bug |
| Test coverage | ✓ 1163 | ✗ 1161 |
| Spec compliance | ✓ Full | ✗ Missing slow marker |
| Score | **9/10** | **7/10** |

The handoff document improved both efficiency AND correctness in this test. The efficiency result
(−70% tokens) matches the 2026-03-22 exploration-session test. The correctness result is new: the
handoff's "Constraints" section specified exact insertion points that prevented a subtle ordering
bug that all tests missed.

---

## Raw Stats (machine-readable)

```json
{
  "experiment": "candidate-eval-implementation-ab-test",
  "type": "implementation",
  "date": "2026-03-24",
  "handoff_file": "20260324-183624-eligibility-hard-caps.md",
  "plan_file": "2026-03-24-eligibility-hard-caps.md",
  "sessions": {
    "with-handoff": {
      "branch": "feat/eligibility-hard-caps-a",
      "duration_min": 50.8,
      "tokens": {
        "input": 129,
        "output": 30118,
        "cache_read": 7738405,
        "cache_create": 200440,
        "total_effective": 7768652
      },
      "tool_calls": {
        "Agent": 26, "Bash": 4, "Edit": 0, "Glob": 0,
        "Read": 8, "Skill": 2, "TaskCreate": 6, "TaskUpdate": 16, "ToolSearch": 1,
        "total": 63
      },
      "turns": 115,
      "tests_passed": 1163,
      "tests_failed": 0,
      "code_review_score": "9/10",
      "bugs_found": []
    },
    "no-handoff": {
      "branch": "feat/eligibility-hard-caps-b",
      "duration_min": 49.7,
      "tokens": {
        "input": 183,
        "output": 39913,
        "cache_read": 13150389,
        "cache_create": 253143,
        "total_effective": 13190485
      },
      "tool_calls": {
        "Agent": 18, "Bash": 31, "Edit": 4, "Glob": 1,
        "Read": 36, "Skill": 3, "TaskCreate": 6, "TaskUpdate": 12, "ToolSearch": 1,
        "total": 112
      },
      "turns": 161,
      "tests_passed": 1161,
      "tests_failed": 0,
      "code_review_score": "7/10",
      "bugs_found": [
        {
          "severity": "correctness",
          "description": "partial_percentage computed before eligibility cap applied",
          "file": "src/claude_candidate/quick_match.py",
          "impact": "Shows non-zero match% when grade is forced to F"
        },
        {
          "severity": "test-infrastructure",
          "description": "test_full_assess_preserves_eligibility_cap missing @pytest.mark.slow",
          "file": "tests/test_server.py",
          "impact": "Slow test runs in fast suite"
        }
      ]
    }
  },
  "deltas": {
    "effective_tokens_pct": -41,
    "tool_calls_pct": -44,
    "turns_pct": -29,
    "duration_pct": -2,
    "test_delta": +2,
    "score_delta": "+2 (9 vs 7)",
    "quality_equivalent": false
  },
  "key_finding": "Handoff reduced effective tokens by 41%, tool calls by 44%, AND prevented a correctness bug in ordering logic. The 2022-03-22 test showed efficiency gains; this test shows quality gains too."
}
```
