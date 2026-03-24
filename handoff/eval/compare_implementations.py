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
