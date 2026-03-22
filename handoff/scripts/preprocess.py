#!/usr/bin/env python3
"""
Preprocess a Claude Code session JSONL for handoff extraction.

Locates the current session's JSONL, extracts conversation text and thinking
blocks, strips noise (progress, tool_results, system entries), enforces size
budget, and writes condensed output.

Usage: python3 preprocess.py [--output /path/to/output.md]
       Prints to stdout if --output is not specified.
"""

import json
import os
import sys
import subprocess
from pathlib import Path

# Size budget constants
MAX_OUTPUT_CHARS = 600_000  # ~150K tokens
MAX_USER_MSG_CHARS = 2000   # Truncate huge user messages
TRUNCATE_KEEP_CHARS = 200   # Keep first/last N chars when truncating


def find_session_jsonl() -> str:
    home = Path.home()
    projects_dir = home / ".claude" / "projects"

    if not projects_dir.is_dir():
        die("~/.claude/projects/ not found. Is Claude Code installed?")

    git_root = get_git_root()
    if git_root:
        encoded = encode_path(git_root)
        result = find_latest_jsonl(projects_dir / encoded)
        if result:
            return result

    cwd = os.getcwd()
    if cwd != git_root:
        encoded = encode_path(cwd)
        result = find_latest_jsonl(projects_dir / encoded)
        if result:
            return result

    import time
    best_path, best_mtime = None, 0
    for proj_dir in projects_dir.iterdir():
        if not proj_dir.is_dir():
            continue
        for f in proj_dir.glob("*.jsonl"):
            if f.is_file() and not f.is_symlink():
                mt = f.stat().st_mtime
                if mt > best_mtime and (time.time() - mt) < 10:
                    best_mtime = mt
                    best_path = str(f)

    if best_path:
        return best_path

    die("Could not find session JSONL. Try running from within a git repository.")


def encode_path(path: str) -> str:
    return path.replace("/", "-").replace(".", "-")


def get_git_root() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def find_latest_jsonl(project_dir: Path) -> str | None:
    if not project_dir.is_dir():
        return None
    best_path, best_mtime = None, 0
    for f in project_dir.glob("*.jsonl"):
        if f.is_file() and not f.is_symlink():
            mt = f.stat().st_mtime
            if mt > best_mtime:
                best_mtime = mt
                best_path = str(f)
    return best_path


def die(msg: str):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def extract_conversation(jsonl_path: str) -> dict:
    messages = []
    thinking_blocks = []
    file_paths = set()
    session_id = ""
    slug = ""
    git_branch = ""
    total_entries = 0
    entry_index = 0

    with open(jsonl_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            total_entries += 1
            entry_type = entry.get("type")
            timestamp = entry.get("timestamp", "")

            if not session_id and entry.get("sessionId"):
                session_id = entry["sessionId"]
            if not slug and entry.get("slug"):
                slug = entry["slug"]
            if not git_branch and entry.get("gitBranch"):
                git_branch = entry["gitBranch"]

            if entry_type == "user":
                text = extract_user_text(entry)
                if text:
                    messages.append({
                        "role": "user",
                        "text": text,
                        "index": entry_index,
                        "timestamp": timestamp,
                    })

            elif entry_type == "assistant":
                content = entry.get("message", {}).get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        btype = block.get("type")
                        if btype == "text" and block.get("text"):
                            messages.append({
                                "role": "assistant",
                                "text": block["text"],
                                "index": entry_index,
                                "timestamp": timestamp,
                            })
                        elif btype == "thinking" and block.get("thinking"):
                            thinking_blocks.append({
                                "text": block["thinking"],
                                "index": entry_index,
                                "timestamp": timestamp,
                            })
                        elif btype == "tool_use":
                            paths = extract_file_paths_from_tool(block)
                            file_paths.update(paths)

            entry_index += 1

    return {
        "messages": messages,
        "thinking": thinking_blocks,
        "file_paths": sorted(file_paths),
        "session_id": session_id,
        "slug": slug,
        "git_branch": git_branch,
        "total_entries": total_entries,
    }


def extract_user_text(entry: dict) -> str:
    content = entry.get("message", {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
        return "\n".join(texts)
    return ""


def extract_file_paths_from_tool(block: dict) -> list[str]:
    name = block.get("name", "")
    inp = block.get("input", {})
    paths = []
    if name in ("Read", "Write", "Edit") and inp.get("file_path"):
        paths.append(inp["file_path"])
    elif name == "Glob" and inp.get("pattern"):
        if inp.get("path"):
            paths.append(inp["path"])
    return paths


def apply_recency_weighting(data: dict) -> str:
    messages = data["messages"]
    thinking = data["thinking"]
    total = data["total_entries"]

    cutoff_index = int(total * 0.4)

    thinking_map = {}
    for t in thinking:
        if t["index"] >= cutoff_index:
            thinking_map.setdefault(t["index"], []).append(t["text"])

    parts = []

    parts.append("# Session Transcript (preprocessed for handoff)")
    parts.append(f"Session: {data['session_id']}")
    parts.append(f"Branch: {data['git_branch']}")
    parts.append(f"Total entries: {data['total_entries']}")
    parts.append(f"Messages extracted: {len(messages)}")
    parts.append("")

    if data["file_paths"]:
        parts.append("## Files Referenced")
        for fp in data["file_paths"]:
            parts.append(f"- `{fp}`")
        parts.append("")

    parts.append("## Conversation")
    parts.append("")

    for msg in messages:
        role_label = "USER" if msg["role"] == "user" else "CLAUDE"
        text = msg["text"]

        if msg["role"] == "user" and len(text) > MAX_USER_MSG_CHARS:
            omitted = len(text) - (TRUNCATE_KEEP_CHARS * 2)
            text = (
                text[:TRUNCATE_KEEP_CHARS]
                + f"\n[truncated — {omitted} chars omitted]\n"
                + text[-TRUNCATE_KEEP_CHARS:]
            )

        parts.append(f"### {role_label}")
        parts.append(text)
        parts.append("")

        if msg["index"] in thinking_map and msg["role"] == "assistant":
            for thought in thinking_map[msg["index"]]:
                if len(thought) > 3000:
                    thought = thought[:1500] + "\n[thinking truncated]\n" + thought[-1500:]
                parts.append("<claude-thinking>")
                parts.append(thought)
                parts.append("</claude-thinking>")
                parts.append("")

    output = "\n".join(parts)

    if len(output) > MAX_OUTPUT_CHARS:
        keep_count = max(int(len(messages) * 0.4), 5)
        messages_trimmed = messages[-keep_count:]

        parts_trimmed = parts[:10]
        parts_trimmed.append("[Earlier conversation truncated for size budget]")
        parts_trimmed.append("")

        for msg in messages_trimmed:
            role_label = "USER" if msg["role"] == "user" else "CLAUDE"
            text = msg["text"]
            if msg["role"] == "user" and len(text) > MAX_USER_MSG_CHARS:
                omitted = len(text) - (TRUNCATE_KEEP_CHARS * 2)
                text = (
                    text[:TRUNCATE_KEEP_CHARS]
                    + f"\n[truncated — {omitted} chars omitted]\n"
                    + text[-TRUNCATE_KEEP_CHARS:]
                )
            parts_trimmed.append(f"### {role_label}")
            parts_trimmed.append(text)
            parts_trimmed.append("")
            if msg["index"] in thinking_map and msg["role"] == "assistant":
                for thought in thinking_map[msg["index"]]:
                    if len(thought) > 3000:
                        thought = thought[:1500] + "\n[thinking truncated]\n" + thought[-1500:]
                    parts_trimmed.append("<claude-thinking>")
                    parts_trimmed.append(thought)
                    parts_trimmed.append("</claude-thinking>")
                    parts_trimmed.append("")

        output = "\n".join(parts_trimmed)

    return output


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Preprocess Claude Code session JSONL for handoff")
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    parser.add_argument("--file", "-f", help="Path to specific JSONL file (default: auto-detect)")
    args = parser.parse_args()

    if args.file:
        jsonl_path = args.file
        if not os.path.isfile(jsonl_path):
            die(f"File not found: {jsonl_path}")
    else:
        jsonl_path = find_session_jsonl()

    file_size = os.path.getsize(jsonl_path)
    if file_size > 100_000_000:
        print(f"WARNING: Large session file ({file_size // 1_000_000}MB). "
              f"Processing may take a moment.", file=sys.stderr)

    data = extract_conversation(jsonl_path)
    output = apply_recency_weighting(data)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Preprocessed transcript written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
