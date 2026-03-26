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
    extract_session_metrics,
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
        assert m["input_output_ratio"] == f"{round(7_738_405 / 30_118)}:1"

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
