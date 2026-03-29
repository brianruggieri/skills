#!/usr/bin/env python3
"""Extract human-written prompts from Claude Code session logs.

Reads all .jsonl session files, filters out code, system messages,
tool outputs, and pasted content, producing a clean corpus of the
user's actual writing voice.

Usage:
    python3 extract-corpus.py [--output /tmp/voice-corpus.txt] [--sessions-dir ~/.claude/projects]
"""

import argparse
import glob
import json
import os
import re
import sys


def is_voice(t: str) -> bool:
	"""Return True only if this looks like a human actually typing."""
	if len(t) > 2000 or len(t) < 12:
		return False

	# System / JSON / XML / quoted content
	if t.startswith("<") or t.startswith("{") or t.startswith("[") or t.startswith(">"):
		return False

	# Tool output artifacts
	if "\u23bf" in t:  # ⎿
		return False
	if t.startswith("   ") or t.startswith("\t"):
		return False

	# Code-heavy (lots of special chars)
	special = sum(1 for c in t if c in "{}[]();=><|&\\`")
	if len(t) > 0 and special / len(t) > 0.1:
		return False

	# Formatted lists (pasted specs, not voice)
	lines = [l for l in t.split("\n") if l.strip()]
	if len(lines) > 2:
		formatted = sum(
			1
			for l in lines
			if re.match(r"^\s*[-*\u2022]\s", l)
			or re.match(r"^\s*\d+[.)]\s", l)
			or re.match(r"^\s*#{1,3}\s", l)
		)
		if formatted / len(lines) > 0.5:
			return False

	# Heavy markdown (likely pasted)
	if t.count("**") > 2 or t.count("| ") > 2:
		return False

	# File path dumps
	if t.count("/") > 4 and len(t) < 200:
		return False

	# Repeated patterns (copy-paste artifacts)
	if t.count("},") > 2 or t.count("[code]") > 1:
		return False

	# Common non-voice single-word responses
	lower = t.strip().lower()
	skip = {
		"continue", "yes", "no", "ok", "thanks", "go ahead", "go for it",
		"looks good", "lgtm", "commit", "push", "ship it", "proceed",
		"sounds good", "perfect", "do it", "approved", "accept",
	}
	if lower in skip:
		return False

	return True


def extract_prompts(sessions_dir: str) -> list[str]:
	"""Extract all human prompts from session logs."""
	pattern = os.path.join(sessions_dir, "*", "*.jsonl")
	files = glob.glob(pattern)

	# Filter out agent/worktree session dirs
	files = [
		f for f in files
		if "worktree" not in f and "agent" not in os.path.basename(os.path.dirname(f))
	]

	prompts = []
	files_read = 0

	for fpath in sorted(files):
		try:
			with open(fpath) as f:
				for line in f:
					try:
						obj = json.loads(line)
						if obj.get("type") != "user":
							continue
						msg = obj.get("message", {})
						if not isinstance(msg, dict):
							continue
						content = msg.get("content", "")

						texts = []
						if isinstance(content, str):
							texts = [content]
						elif isinstance(content, list):
							for item in content:
								if isinstance(item, dict) and item.get("type") == "text":
									texts.append(item["text"])

						for t in texts:
							# Strip code blocks
							t = re.sub(r"```[\s\S]*?```", "", t).strip()
							if is_voice(t):
								prompts.append(t)
					except (json.JSONDecodeError, KeyError):
						pass
			files_read += 1
		except OSError:
			pass

	return prompts, files_read


def main():
	parser = argparse.ArgumentParser(description="Extract voice corpus from Claude Code sessions")
	parser.add_argument(
		"--output", "-o",
		default="/tmp/voice-corpus.txt",
		help="Output file path (default: /tmp/voice-corpus.txt)",
	)
	parser.add_argument(
		"--sessions-dir",
		default=os.path.expanduser("~/.claude/projects"),
		help="Claude Code projects directory (default: ~/.claude/projects)",
	)
	parser.add_argument(
		"--stats", action="store_true",
		help="Print corpus statistics after extraction",
	)
	args = parser.parse_args()

	prompts, files_read = extract_prompts(args.sessions_dir)

	with open(args.output, "w") as f:
		for p in prompts:
			f.write(p + "\n---\n")

	print(f"Files read: {files_read}")
	print(f"Prompts extracted: {len(prompts)}")
	print(f"Written to: {args.output}")
	print(f"Size: {os.path.getsize(args.output) / 1024:.0f} KB")

	if args.stats:
		if not prompts:
			print("\nNo prompts extracted; skipping stats.")
		else:
			lengths = sorted(len(p) for p in prompts)
			print(f"\nLength distribution:")
			print(f"  Shortest: {lengths[0]} chars")
			print(f"  Median: {lengths[len(lengths) // 2]} chars")
			print(f"  90th pct: {lengths[int(len(lengths) * 0.9)]} chars")
			print(f"  Longest: {lengths[-1]} chars")


if __name__ == "__main__":
	main()
