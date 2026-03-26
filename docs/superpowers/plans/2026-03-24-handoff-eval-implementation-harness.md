# Handoff Eval Implementation Harness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build three files — a Python metrics comparison script, an implementation grading rubric, and a two-phase orchestration skill — that together let you run A/B experiments comparing Claude sessions with and without handoff context.

**Architecture:** `compare_implementations.py` reads a state file and auto-extracts session metrics from Claude Code's session JSONL, then produces a metrics table + git diff. The skill's phase 1 sets up worktrees and writes the state file; phase 2 runs the script and dispatches two blind grader agents using `grade-implementation.md` injected inline.

**Tech Stack:** Python 3.11+ (stdlib only: `argparse`, `json`, `subprocess`, `pathlib`, `re`), pytest, git CLI, Claude Code session JSONL format.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `handoff/eval/compare_implementations.py` | Create | CLI script: reads state + JSONL, computes metrics, prints table + diff |
| `handoff/eval/tests/__init__.py` | Create | Makes tests a package |
| `handoff/eval/tests/test_compare.py` | Create | Unit tests for pure functions in compare script |
| `handoff/eval/prompts/grade-implementation.md` | Create | Grading rubric injected into grader agent prompts |
| `handoff/eval-implementation/SKILL.md` | Create | Two-phase skill: `setup` creates worktrees; `compare` runs script + graders |

All paths are relative to the repo root (`~/git/skills/`). These files are also the installed skill files — the repo is the source of truth for `~/.claude/skills/handoff/`.

---

## Task 1: Rubric — `grade-implementation.md`

No tests — this is a markdown document. Verify it matches the spec exactly before committing.

**Files:**
- Create: `handoff/eval/prompts/grade-implementation.md`

- [ ] **Step 1: Create the rubric file**

```markdown
# Implementation Grader

You are grading one implementation session. You have: the diff between this branch
and main, the worktree path for targeted file reads, the plan file path, and this
session's efficiency metrics.

Your job is to score this implementation across five dimensions.

---

## Grading Dimensions

### 1. CORRECTNESS (weight: 4)

Examine the diff for values computed on the wrong side of a mutation — these are bugs
even if all tests pass.

- Check ordering: any field assigned *before* the mutation that changes its inputs is
  wrong (e.g., `percentage = score * 100` before `score = 0.0` when the spec requires
  0% after the cap).
- Deduct 3 points per ordering bug; 2 points per logic error visible in the diff.

### 2. TEST_COVERAGE (weight: 3)

Open the test file(s) for any field computed inside a conditional — use the worktree
path to read them.

- Verify the field is explicitly asserted under the failure/cap path (not just that the
  test runs — check the assert statement value).
- Deduct 2 per missing assertion on an intermediate field under a cap/error path.
- Deduct 1 per missing required test marker (e.g., `@pytest.mark.slow`).

### 3. SPEC_COMPLIANCE (weight: 2)

Cross-reference the plan file. Every explicit constraint must be met: insertion points,
field names, no-schema rules, marker requirements.

- Deduct 1.5 per violated constraint.

### 4. IMPLEMENTATION_FOCUS (weight: 1)

- Significant scope creep (changes to files not mentioned in plan): −2
- Minor scope creep (cosmetic edits in unrelated files): −1
- Unnecessary files touched (beyond plan's specified insertion points): −1 per file

### 5. CODE_QUALITY (weight: 1)

- Clear violation of existing patterns (naming, abstraction level, duplicated logic): −2
- Minor violations (small inconsistency, dead import): −0.5 per instance, max −2 total

---

## Scoring Formula

```
OVERALL = (4×CORRECTNESS + 3×TEST_COVERAGE + 2×SPEC_COMPLIANCE
           + IMPLEMENTATION_FOCUS + CODE_QUALITY) / 11
```

**Pass threshold:** OVERALL ≥ 7.0 AND CORRECTNESS ≥ 6 AND no dimension below 4.

---

## Output Format

Produce EXACTLY this format:

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

Do NOT explain your reasoning beyond the one-line justifications.
Score deductions must document: specific defect, file/line, severity, exact deduction amount.
```
```

- [ ] **Step 2: Verify against spec**

Open `docs/superpowers/specs/2026-03-24-handoff-eval-implementation-design.md` and confirm:
- All 5 dimensions present with correct weights
- Scoring formula matches exactly
- Pass threshold: OVERALL ≥ 7.0 AND CORRECTNESS ≥ 6 AND no dimension below 4
- Deduction amounts match spec

- [ ] **Step 3: Commit**

```bash
git add handoff/eval/prompts/grade-implementation.md
git commit -m "Add grade-implementation.md rubric"
```

---

## Task 2: Compare Script — Pure Functions + Tests (TDD)

Build and test the pure computation functions before adding git/subprocess calls.

**Files:**
- Create: `handoff/eval/tests/__init__.py`
- Create: `handoff/eval/tests/test_compare.py`
- Create: `handoff/eval/compare_implementations.py` (partial — pure functions only)

- [ ] **Step 1: Create test file with failing tests**

Create `handoff/eval/tests/__init__.py` (empty).

Create `handoff/eval/tests/test_compare.py`:

```python
"""Unit tests for compare_implementations.py pure functions."""
import json
import pytest
from pathlib import Path

# Will import from the script once it exists
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from compare_implementations import (
    compute_derived_metrics,
    classify_numstat_line,
    load_state,
    parse_metrics_from_stdout,
)


class TestComputeDerivedMetrics:
    def test_exploration_ratio(self):
        raw = {"bash": 31, "read": 36, "agent": 18, "total_tool_calls": 112}
        m = compute_derived_metrics(raw)
        assert round(m["exploration_ratio"], 2) == round((31 + 36) / 112, 2)

    def test_delegation_ratio(self):
        raw = {"bash": 4, "read": 8, "agent": 26, "total_tool_calls": 63}
        m = compute_derived_metrics(raw)
        assert round(m["delegation_ratio"], 2) == round(26 / 63, 2)

    def test_input_output_ratio(self):
        raw = {"cache_read": 7_738_405, "output_tokens": 30_118, "total_tool_calls": 63}
        m = compute_derived_metrics(raw)
        assert round(m["input_output_ratio"], 0) == round(7_738_405 / 30_118, 0)

    def test_tokens_per_task(self):
        raw = {"effective_tokens": 7_768_652, "task_count": 6, "total_tool_calls": 63}
        m = compute_derived_metrics(raw)
        assert m["tokens_per_task"] == 7_768_652 // 6

    def test_zero_tool_calls_returns_zero_ratios(self):
        raw = {"bash": 0, "read": 0, "agent": 0, "total_tool_calls": 0}
        m = compute_derived_metrics(raw)
        assert m["exploration_ratio"] == 0.0
        assert m["delegation_ratio"] == 0.0

    def test_patch_efficiency(self):
        raw = {"lines_added": 80, "lines_removed": 20, "f2p_count": 5, "total_tool_calls": 10}
        m = compute_derived_metrics(raw)
        assert m["patch_efficiency"] == (80 + 20) / 5

    def test_patch_efficiency_zero_f2p(self):
        raw = {"lines_added": 80, "lines_removed": 20, "f2p_count": 0, "total_tool_calls": 10}
        m = compute_derived_metrics(raw)
        assert m["patch_efficiency"] is None

    def test_tokens_per_f2p(self):
        raw = {"effective_tokens": 7_768_652, "f2p_count": 4, "total_tool_calls": 63}
        m = compute_derived_metrics(raw)
        assert m["tokens_per_f2p"] == 7_768_652 // 4

    def test_tokens_per_f2p_zero_f2p(self):
        raw = {"effective_tokens": 7_768_652, "f2p_count": 0, "total_tool_calls": 63}
        m = compute_derived_metrics(raw)
        assert m["tokens_per_f2p"] is None


class TestClassifyNumstatLine:
    def test_test_file_by_prefix(self):
        assert classify_numstat_line("10\t2\tsrc/tests/test_foo.py") == "test"

    def test_test_file_in_tests_dir(self):
        assert classify_numstat_line("5\t1\ttests/test_bar.py") == "test"

    def test_test_file_suffix(self):
        assert classify_numstat_line("3\t0\tsrc/foo_test.py") == "test"

    def test_source_file(self):
        assert classify_numstat_line("20\t5\tsrc/module/handler.py") == "source"

    def test_non_python_file(self):
        assert classify_numstat_line("1\t0\tREADME.md") == "other"

    def test_malformed_line_returns_other(self):
        assert classify_numstat_line("not a numstat line") == "other"


class TestLoadState:
    def test_loads_valid_state(self, tmp_path):
        state = {
            "experiment": "my-feature",
            "task_count": 6,
            "plan_file": "/abs/path/plan.md",
            "handoff_file": "/abs/path/handoff.md",
            "with_handoff": {"branch": "feat/my-feature-with-handoff", "worktree": "/abs/wt-a"},
            "no_handoff": {"branch": "feat/my-feature-no-handoff", "worktree": "/abs/wt-b"},
        }
        f = tmp_path / "eval-state.json"
        f.write_text(json.dumps(state))
        loaded = load_state(str(f))
        assert loaded["experiment"] == "my-feature"
        assert loaded["task_count"] == 6

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(SystemExit):
            load_state(str(tmp_path / "nonexistent.json"))

    def test_missing_required_key_raises(self, tmp_path):
        f = tmp_path / "eval-state.json"
        f.write_text(json.dumps({"experiment": "x"}))  # missing with_handoff etc.
        with pytest.raises(SystemExit):
            load_state(str(f))


class TestParseMetricsFromStdout:
    def test_splits_on_sentinel(self):
        stdout = "metrics content\n---DIFF---\ndiff content"
        table, diff = parse_metrics_from_stdout(stdout)
        assert table == "metrics content\n"
        assert diff == "\ndiff content"

    def test_no_sentinel_returns_all_as_table(self):
        stdout = "metrics only, no diff"
        table, diff = parse_metrics_from_stdout(stdout)
        assert table == stdout
        assert diff == ""
```

- [ ] **Step 2: Run tests to verify they all fail**

```bash
cd ~/git/skills && python -m pytest handoff/eval/tests/test_compare.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'compare_implementations'`

- [ ] **Step 3: Create `compare_implementations.py` with pure functions only**

Create `handoff/eval/compare_implementations.py`:

```python
#!/usr/bin/env python3
"""
Compare two parallel implementation sessions (with-handoff vs no-handoff).

Reads eval-state.json, extracts metrics from Claude Code session JSONL,
diffs branches, and prints a comparison table followed by ---DIFF--- and
the full git diff.

Usage:
  python compare_implementations.py [--state-file PATH] [--repo-root PATH]
                                     [--venv PATH] [--task-count N]
                                     [--with-handoff-branch BRANCH]
                                     [--no-handoff-branch BRANCH]
                                     [--with-handoff-worktree PATH]
                                     [--no-handoff-worktree PATH]
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Pure functions (unit-tested)
# ---------------------------------------------------------------------------

def compute_derived_metrics(raw: dict) -> dict:
    """Compute ratio metrics from raw counts. All inputs default to 0 if absent."""
    total = raw.get("total_tool_calls", 0)
    bash = raw.get("bash", 0)
    read = raw.get("read", 0)
    agent = raw.get("agent", 0)
    cache_read = raw.get("cache_read", 0)
    output_tokens = raw.get("output_tokens", 0)
    effective_tokens = raw.get("effective_tokens", 0)
    task_count = raw.get("task_count", 0)
    lines_added = raw.get("lines_added", 0)
    lines_removed = raw.get("lines_removed", 0)
    f2p_count = raw.get("f2p_count", 0)

    return {
        "exploration_ratio": round((bash + read) / total, 2) if total else 0.0,
        "delegation_ratio": round(agent / total, 2) if total else 0.0,
        "input_output_ratio": round(cache_read / output_tokens) if output_tokens else 0,
        "tokens_per_task": effective_tokens // task_count if task_count else None,
        "tokens_per_f2p": effective_tokens // f2p_count if f2p_count else None,
        "patch_efficiency": (lines_added + lines_removed) / f2p_count if f2p_count else None,
    }


def classify_numstat_line(line: str) -> str:
    """
    Classify a `git diff --numstat` line as 'test', 'source', or 'other'.

    Line format: "<added>\t<removed>\t<path>"
    Test files: match test_*.py, *_test.py, or any .py file under a tests/ directory.
    """
    parts = line.split("\t")
    if len(parts) != 3:
        return "other"
    path = parts[2]
    if not path.endswith(".py"):
        return "other"
    name = Path(path).name
    dirs = Path(path).parts
    if name.startswith("test_") or name.endswith("_test.py"):
        return "test"
    if any(d in ("tests", "test") for d in dirs[:-1]):
        return "test"
    return "source"


def load_state(path: str) -> dict:
    """Load and validate eval-state.json. Exits with message on error."""
    p = Path(path)
    if not p.exists():
        _die(f"State file not found: {path}\nRun `/handoff:eval-implementation setup` first.")
    try:
        state = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        _die(f"State file is not valid JSON: {e}")

    required = ["experiment", "task_count", "plan_file", "with_handoff", "no_handoff"]
    missing = [k for k in required if k not in state]
    if missing:
        _die(f"State file missing required keys: {missing}")
    return state


def parse_metrics_from_stdout(stdout: str) -> tuple[str, str]:
    """Split script output on ---DIFF--- sentinel. Returns (table, diff)."""
    sentinel = "---DIFF---"
    if sentinel in stdout:
        idx = stdout.index(sentinel)
        return stdout[:idx], stdout[idx + len(sentinel):]
    return stdout, ""


def _die(msg: str):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)
```

- [ ] **Step 4: Run tests to verify pure functions pass**

```bash
cd ~/git/skills && python -m pytest handoff/eval/tests/test_compare.py -v
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add handoff/eval/compare_implementations.py handoff/eval/tests/__init__.py handoff/eval/tests/test_compare.py
git commit -m "Add compare_implementations.py pure functions + tests"
```

---

## Task 3: Compare Script — JSONL Session Metrics Extraction

Add the function that reads Claude Code's session JSONL to extract token/tool call metrics automatically.

**Files:**
- Modify: `handoff/eval/compare_implementations.py` (add `extract_session_metrics`)
- Modify: `handoff/eval/tests/test_compare.py` (add JSONL tests)

- [ ] **Step 1: Write failing tests for `extract_session_metrics`**

Add to `test_compare.py`:

```python
from compare_implementations import extract_session_metrics


class TestExtractSessionMetrics:
    def test_counts_tool_calls_by_name(self, tmp_path):
        # Build a minimal JSONL with two tool_use blocks
        entries = [
            {"type": "assistant", "timestamp": "2026-01-01T00:00:00Z",
             "message": {
                 "usage": {"input_tokens": 10, "output_tokens": 5,
                           "cache_read_input_tokens": 100, "cache_creation_input_tokens": 20},
                 "content": [
                     {"type": "tool_use", "name": "Bash"},
                     {"type": "tool_use", "name": "Read"},
                 ]
             }},
            {"type": "assistant", "timestamp": "2026-01-01T00:01:00Z",
             "message": {
                 "usage": {"input_tokens": 5, "output_tokens": 3,
                           "cache_read_input_tokens": 50, "cache_creation_input_tokens": 0},
                 "content": [
                     {"type": "tool_use", "name": "Bash"},
                 ]
             }},
        ]
        jsonl = tmp_path / "session.jsonl"
        jsonl.write_text("\n".join(json.dumps(e) for e in entries))

        m = extract_session_metrics(str(jsonl))
        assert m["tool_calls"]["Bash"] == 2
        assert m["tool_calls"]["Read"] == 1
        assert m["total_tool_calls"] == 3
        assert m["turns"] == 2

    def test_sums_tokens(self, tmp_path):
        entries = [
            {"type": "assistant", "timestamp": "2026-01-01T00:00:00Z",
             "message": {
                 "usage": {"input_tokens": 100, "output_tokens": 50,
                           "cache_read_input_tokens": 1000, "cache_creation_input_tokens": 200},
                 "content": []
             }},
        ]
        jsonl = tmp_path / "session.jsonl"
        jsonl.write_text(json.dumps(entries[0]))

        m = extract_session_metrics(str(jsonl))
        assert m["input_tokens"] == 100
        assert m["output_tokens"] == 50
        assert m["cache_read"] == 1000
        assert m["cache_create"] == 200
        assert m["effective_tokens"] == 100 + 50 + 1000 + 200

    def test_computes_duration_seconds(self, tmp_path):
        entries = [
            {"type": "user", "timestamp": "2026-01-01T00:00:00Z", "message": {"content": "go"}},
            {"type": "assistant", "timestamp": "2026-01-01T01:00:00Z",
             "message": {"usage": {"input_tokens": 1, "output_tokens": 1,
                                   "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
                         "content": []}},
        ]
        jsonl = tmp_path / "session.jsonl"
        jsonl.write_text("\n".join(json.dumps(e) for e in entries))

        m = extract_session_metrics(str(jsonl))
        assert m["duration_min"] == pytest.approx(60.0, abs=0.1)

    def test_missing_file_returns_empty(self):
        m = extract_session_metrics("/nonexistent/path/session.jsonl")
        assert m == {}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/git/skills && python -m pytest handoff/eval/tests/test_compare.py::TestExtractSessionMetrics -v 2>&1 | head -20
```

Expected: `ImportError` (function doesn't exist yet).

- [ ] **Step 3: Implement `extract_session_metrics` and JSONL auto-detection**

Add to `compare_implementations.py` after the pure functions section:

```python
# ---------------------------------------------------------------------------
# JSONL session metrics extraction
# ---------------------------------------------------------------------------

def extract_session_metrics(jsonl_path: str) -> dict:
    """
    Parse a Claude Code session JSONL and return aggregated metrics.
    Returns {} if the file is missing or unreadable.
    """
    p = Path(jsonl_path)
    if not p.exists():
        return {}

    tool_calls: dict[str, int] = {}
    total_input = total_output = total_cache_read = total_cache_create = 0
    turns = 0
    timestamps: list[str] = []

    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ts = entry.get("timestamp")
                if ts:
                    timestamps.append(ts)

                if entry.get("type") != "assistant":
                    continue

                msg = entry.get("message", {})
                usage = msg.get("usage", {})
                total_input += usage.get("input_tokens", 0)
                total_output += usage.get("output_tokens", 0)
                total_cache_read += usage.get("cache_read_input_tokens", 0)
                total_cache_create += usage.get("cache_creation_input_tokens", 0)
                turns += 1

                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            name = block.get("name", "unknown")
                            tool_calls[name] = tool_calls.get(name, 0) + 1
    except OSError:
        return {}

    duration_min = _compute_duration_min(timestamps)
    total_tc = sum(tool_calls.values())

    return {
        "input_tokens": total_input,
        "output_tokens": total_output,
        "cache_read": total_cache_read,
        "cache_create": total_cache_create,
        "effective_tokens": total_input + total_output + total_cache_read + total_cache_create,
        "tool_calls": tool_calls,
        "total_tool_calls": total_tc,
        "turns": turns,
        "duration_min": duration_min,
        "bash": tool_calls.get("Bash", 0),
        "read": tool_calls.get("Read", 0),
        "agent": tool_calls.get("Agent", 0),
    }


def _compute_duration_min(timestamps: list[str]) -> float | None:
    """Return session duration in minutes from first to last timestamp."""
    if len(timestamps) < 2:
        return None
    from datetime import datetime, timezone
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    try:
        t0 = datetime.strptime(timestamps[0], fmt).replace(tzinfo=timezone.utc)
        t1 = datetime.strptime(timestamps[-1], fmt).replace(tzinfo=timezone.utc)
        return round((t1 - t0).total_seconds() / 60, 1)
    except ValueError:
        return None


def find_session_jsonl_for_worktree(worktree_path: str) -> str | None:
    """
    Find the most recent Claude Code session JSONL for a given worktree path.
    Uses the same encoding as preprocess.py: path.replace('/', '-').replace('.', '-')
    """
    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.is_dir():
        return None

    encoded = worktree_path.replace("/", "-").replace(".", "-")
    project_dir = projects_dir / encoded
    if not project_dir.is_dir():
        return None

    best_path, best_mtime = None, 0.0
    for f in project_dir.glob("*.jsonl"):
        if f.is_file():
            mt = f.stat().st_mtime
            if mt > best_mtime:
                best_mtime = mt
                best_path = str(f)
    return best_path
```

- [ ] **Step 4: Run JSONL tests**

```bash
cd ~/git/skills && python -m pytest handoff/eval/tests/test_compare.py::TestExtractSessionMetrics -v
```

Expected: All 4 tests pass.

- [ ] **Step 5: Run full test suite**

```bash
cd ~/git/skills && python -m pytest handoff/eval/tests/test_compare.py -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add handoff/eval/compare_implementations.py handoff/eval/tests/test_compare.py
git commit -m "Add JSONL session metrics extraction to compare script"
```

---

## Task 4: Compare Script — Git Metrics + Output Formatting

Add git/pytest integration and the main() entry point with full output formatting.

**Files:**
- Modify: `handoff/eval/compare_implementations.py` (add git functions + main)

- [ ] **Step 1: Add git metric functions**

Add to `compare_implementations.py`:

```python
# ---------------------------------------------------------------------------
# Git and pytest metrics
# ---------------------------------------------------------------------------

def run(cmd: list[str], cwd: str | None = None) -> str:
    """Run a subprocess command, return stdout. Returns '' on error."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=60)
        return r.stdout if r.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def detect_venv(repo_root: str) -> str | None:
    """Find venv: checks .venv, venv, $VIRTUAL_ENV in that order."""
    import os
    for name in (".venv", "venv"):
        candidate = Path(repo_root) / name / "bin" / "python"
        if candidate.exists():
            return str(candidate)
    env_python = os.environ.get("VIRTUAL_ENV")
    if env_python:
        candidate = Path(env_python) / "bin" / "python"
        if candidate.exists():
            return str(candidate)
    return None


def compute_git_metrics(branch: str, worktree: str, repo_root: str) -> dict:
    """Compute lines added/removed, files changed, commit count from git."""
    # Lines added/removed and files changed
    numstat = run(["git", "diff", "--numstat", f"main..{branch}"], cwd=repo_root)
    lines_added = lines_removed = files_changed = 0
    test_lines = source_lines = 0
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        try:
            added, removed = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        lines_added += added
        lines_removed += removed
        files_changed += 1
        kind = classify_numstat_line(line)
        if kind == "test":
            test_lines += added + removed
        elif kind == "source":
            source_lines += added + removed

    test_source_ratio = round(test_lines / source_lines, 2) if source_lines else None

    # Commit count
    log = run(["git", "log", "--oneline", f"main..{branch}"], cwd=repo_root)
    commit_count = len([l for l in log.splitlines() if l.strip()])

    return {
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "files_changed": files_changed,
        "commit_count": commit_count,
        "test_source_ratio": test_source_ratio,
    }


def compute_f2p_p2p(branch: str, worktree: str, python_bin: str | None) -> dict:
    """
    Compute F2P (new test functions) and P2P (regressions) counts.

    F2P: count new test function definitions added vs main.
    P2P: run pytest in the worktree and count failures (requires worktree to exist).
    """
    if not Path(worktree).is_dir():
        return {"f2p_count": None, "p2p_regressions": None, "tests_total": None}

    # F2P: count added `def test_` lines in test files
    numstat_output = run(
        ["git", "diff", "--unified=0", f"main..{branch}", "--", "*/test_*.py", "*_test.py"],
        cwd=worktree
    )
    f2p_count = sum(
        1 for line in numstat_output.splitlines()
        if line.startswith("+") and re.match(r"^\+\s*def test_", line)
    )

    # P2P: run pytest, count failures
    if python_bin:
        result = subprocess.run(
            [python_bin, "-m", "pytest", "--tb=no", "-q"],
            capture_output=True, text=True, cwd=worktree, timeout=300
        )
        output = result.stdout + result.stderr
        # Parse "X passed, Y failed" from pytest summary line
        m = re.search(r"(\d+) passed", output)
        tests_passed = int(m.group(1)) if m else None
        m = re.search(r"(\d+) failed", output)
        p2p_regressions = int(m.group(1)) if m else 0
        m = re.search(r"(\d+) passed", output)
        tests_total = tests_passed
    else:
        p2p_regressions = None
        tests_total = None

    return {
        "f2p_count": f2p_count,
        "p2p_regressions": p2p_regressions,
        "tests_total": tests_total,
    }
```

- [ ] **Step 2: Add output formatter**

Add to `compare_implementations.py`:

```python
# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def _fmt(val, suffix="", na="[not recorded]") -> str:
    if val is None:
        return na
    return f"{val:,}{suffix}" if isinstance(val, int) else f"{val}{suffix}"


def _delta(a, b, pct=True) -> str:
    if a is None or b is None:
        return "—"
    if pct and b != 0:
        d = round((a - b) / b * 100)
        sign = "−" if d < 0 else "+"
        return f"{sign}{abs(d)}%"
    d = a - b
    sign = "+" if d > 0 else ("−" if d < 0 else "")
    return f"{sign}{abs(d)}" if d != 0 else "—"


def format_table(ma: dict, mb: dict) -> str:
    """Format the metrics comparison table. ma=with-handoff, mb=no-handoff."""
    da = compute_derived_metrics(ma)
    db = compute_derived_metrics(mb)

    def row(label, a, b, w=22, pct=True):
        fa, fb = _fmt(a), _fmt(b)
        fd = _delta(a, b, pct=pct)
        return f"{label:<{w}}  {fa:<14}  {fb:<14}  {fd}"

    lines = [
        "Implementation Comparison",
        "═" * 57,
        "",
        f"Branch A (with-handoff):  {ma.get('branch', '?')}",
        f"Branch B (no-handoff):    {mb.get('branch', '?')}",
        f"Tasks:                    {ma.get('task_count', '?')}",
        "",
        "── Efficiency " + "─" * 43,
        f"{'Metric':<22}  {'With-Handoff':<14}  {'No-Handoff':<14}  Delta",
        row("Effective tokens",   ma.get("effective_tokens"),  mb.get("effective_tokens")),
        row("  Input/output ratio", da.get("input_output_ratio"), db.get("input_output_ratio"), pct=False),
        row("Tool calls (total)", ma.get("total_tool_calls"),  mb.get("total_tool_calls")),
        row("  Exploration ratio", da.get("exploration_ratio"), db.get("exploration_ratio"), pct=False),
        row("  Delegation ratio",  da.get("delegation_ratio"),  db.get("delegation_ratio"),  pct=False),
        row("Turns",              ma.get("turns"),              mb.get("turns")),
        row("Duration (min)",     ma.get("duration_min"),       mb.get("duration_min"),       pct=False),
        row("Tokens / task",      da.get("tokens_per_task"),    db.get("tokens_per_task")),
        "",
        "── Test Results " + "─" * 41,
        f"{'Metric':<22}  {'With-Handoff':<14}  {'No-Handoff':<14}  Delta",
        row("Tests passed",       ma.get("tests_total"),        mb.get("tests_total"),        pct=False),
        row("  F2P (new tests)",  ma.get("f2p_count"),          mb.get("f2p_count"),          pct=False),
        row("  P2P regressions",  ma.get("p2p_regressions"),    mb.get("p2p_regressions"),    pct=False),
        row("Tokens / F2P test",  da.get("tokens_per_f2p"),     db.get("tokens_per_f2p")),
        "",
        "── Code " + "─" * 49,
        f"{'Metric':<22}  {'With-Handoff':<14}  {'No-Handoff':<14}  Delta",
        row("Commits",            ma.get("commit_count"),       mb.get("commit_count"),       pct=False),
        row("Files changed",      ma.get("files_changed"),      mb.get("files_changed"),      pct=False),
        row("Lines added",        ma.get("lines_added"),        mb.get("lines_added"),        pct=False),
        row("Lines removed",      ma.get("lines_removed"),      mb.get("lines_removed"),      pct=False),
        row("Test/source ratio",  ma.get("test_source_ratio"),  mb.get("test_source_ratio"),  pct=False),
        row("Patch efficiency",   da.get("patch_efficiency"),   db.get("patch_efficiency"),   pct=False),
        "",
        "═" * 57,
    ]
    return "\n".join(lines)
```

- [ ] **Step 3: Add `main()` entry point**

Add to `compare_implementations.py`:

```python
# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Compare two implementation sessions.")
    parser.add_argument("--state-file")
    parser.add_argument("--repo-root")
    parser.add_argument("--venv")
    parser.add_argument("--task-count", type=int)
    parser.add_argument("--with-handoff-branch")
    parser.add_argument("--no-handoff-branch")
    parser.add_argument("--with-handoff-worktree")
    parser.add_argument("--no-handoff-worktree")
    args = parser.parse_args()

    # Resolve repo root
    repo_root = args.repo_root or run(["git", "rev-parse", "--show-toplevel"]).strip() or "."

    # Locate state file
    state_file = args.state_file or str(Path(repo_root) / ".claude" / "handoffs" / "eval-state.json")
    state = load_state(state_file)

    # Build session configs, CLI args override state file
    def cfg(key):
        return state.get(key, {})

    wh_branch   = args.with_handoff_branch   or cfg("with_handoff").get("branch", "")
    nh_branch   = args.no_handoff_branch     or cfg("no_handoff").get("branch", "")
    wh_worktree = args.with_handoff_worktree or cfg("with_handoff").get("worktree", "")
    nh_worktree = args.no_handoff_worktree   or cfg("no_handoff").get("worktree", "")
    task_count  = args.task_count            or state.get("task_count", 0)

    # Venv
    python_bin = args.venv or detect_venv(repo_root)

    # Extract session metrics from JSONL
    wh_jsonl = find_session_jsonl_for_worktree(wh_worktree)
    nh_jsonl = find_session_jsonl_for_worktree(nh_worktree)
    ma = extract_session_metrics(wh_jsonl) if wh_jsonl else {}
    mb = extract_session_metrics(nh_jsonl) if nh_jsonl else {}

    # Add git metrics
    if wh_branch:
        ma.update(compute_git_metrics(wh_branch, wh_worktree, repo_root))
        ma.update(compute_f2p_p2p(wh_branch, wh_worktree, python_bin))
    if nh_branch:
        mb.update(compute_git_metrics(nh_branch, nh_worktree, repo_root))
        mb.update(compute_f2p_p2p(nh_branch, nh_worktree, python_bin))

    # Attach metadata
    ma["branch"] = wh_branch
    mb["branch"] = nh_branch
    ma["task_count"] = mb["task_count"] = task_count

    # Print table
    print(format_table(ma, mb))

    # Sentinel + full diff
    print("---DIFF---")
    diff = run(["git", "diff", f"{wh_branch}...{nh_branch}"], cwd=repo_root)
    print(diff)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Verify CLI works**

```bash
cd ~/git/skills && python handoff/eval/compare_implementations.py --help
```

Expected: Prints usage with all documented args, no errors.

- [ ] **Step 5: Run full test suite**

```bash
cd ~/git/skills && python -m pytest handoff/eval/tests/test_compare.py -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add handoff/eval/compare_implementations.py
git commit -m "Add git metrics, output formatting, and CLI main() to compare script"
```

---

## Task 5: Skill — `eval-implementation/SKILL.md`

Markdown document only — no tests. Verify carefully against spec.

**Files:**
- Create: `handoff/eval-implementation/SKILL.md`

- [ ] **Step 1: Create the skill file**

Create `handoff/eval-implementation/SKILL.md`:

````markdown
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
   COMPARE="$(dirname "$(realpath "$0")")/../eval/compare_implementations.py"
   ```
   Run it and capture stdout:
   ```bash
   python "$COMPARE" --state-file .claude/handoffs/eval-state.json
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
````

- [ ] **Step 2: Verify against spec**

Open `docs/superpowers/specs/2026-03-24-handoff-eval-implementation-design.md` and confirm:
- Phase 1 arguments: `--source-branch`, `--plan`, `--handoff`
- Name derivation rule is present
- State file schema matches spec exactly (including `handoff_file`)
- Phase 2 reads grade-implementation.md and injects inline (not passes a path)
- Phase 2 error handling for missing state file and missing worktrees
- Output directory: `~/.claude/skills/handoff/tests/output/eval/`

- [ ] **Step 3: Commit**

```bash
git add handoff/eval-implementation/SKILL.md
git commit -m "Add eval-implementation skill (two-phase A/B experiment orchestrator)"
```

---

## Task 6: Smoke Test

Verify all three files are present and the compare script runs cleanly.

- [ ] **Step 1: Verify files exist**

```bash
ls handoff/eval/compare_implementations.py \
   handoff/eval/prompts/grade-implementation.md \
   handoff/eval-implementation/SKILL.md \
   handoff/eval/tests/test_compare.py
```

Expected: All four files listed, no "No such file" errors.

- [ ] **Step 2: Run full test suite**

```bash
cd ~/git/skills && python -m pytest handoff/eval/tests/ -v
```

Expected: All tests pass.

- [ ] **Step 3: Verify `--help` works**

```bash
python handoff/eval/compare_implementations.py --help
```

Expected: Prints help with `--state-file`, `--repo-root`, `--venv`, `--task-count`, `--with-handoff-branch`, `--no-handoff-branch`, `--with-handoff-worktree`, `--no-handoff-worktree`.

- [ ] **Step 4: Verify script is importable with no side effects**

```bash
python -c "import sys; sys.path.insert(0, 'handoff/eval'); import compare_implementations; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Final commit if anything was missed**

```bash
git status
```

If clean: done. If any stray files: add and commit them.
