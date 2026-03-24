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
