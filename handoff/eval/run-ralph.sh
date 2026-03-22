#!/usr/bin/env bash
# Ralph loop for handoff extraction prompt refinement.
# Each iteration runs in a fresh Claude session with blind subagent eval.
# Stops when all 4 fixtures pass or max iterations reached.

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

MAX_ITERATIONS="${1:-10}"
PROMPT_FILE="handoff/eval/RALPH-PROMPT.md"
SCORECARD_DIR="handoff/tests/output/eval"

iteration=0

while [ "$iteration" -lt "$MAX_ITERATIONS" ]; do
	iteration=$((iteration + 1))
	echo ""
	echo "═══════════════════════════════════════════"
	echo "  Ralph iteration $iteration / $MAX_ITERATIONS"
	echo "═══════════════════════════════════════════"
	echo ""

	# Run fresh Claude session with the prompt
	# NOTE: --dangerously-skip-permissions is used because the ralph loop needs
	# to read/write files and dispatch agents autonomously across iterations.
	# Only run this in the skills repo, never in production codebases.
	if [ "${RALPH_SKIP_PERMISSIONS:-}" = "1" ]; then
		cat "$PROMPT_FILE" | claude --dangerously-skip-permissions
	else
		echo "WARNING: This script runs Claude with full file/agent access."
		echo "Set RALPH_SKIP_PERMISSIONS=1 to proceed, or run interactively:"
		echo "  cat $PROMPT_FILE | claude"
		exit 1
	fi

	# Check if all fixtures passed
	all_pass=true
	for scorecard in "$SCORECARD_DIR"/*-scorecard.md; do
		if [ ! -f "$scorecard" ]; then
			all_pass=false
			break
		fi
		if ! grep -q "PASS: YES" "$scorecard"; then
			all_pass=false
			echo "  FAIL: $(basename "$scorecard")"
		else
			echo "  PASS: $(basename "$scorecard")"
		fi
	done

	if [ "$all_pass" = true ]; then
		echo ""
		echo "All fixtures pass after $iteration iterations."
		exit 0
	fi
done

echo ""
echo "Max iterations ($MAX_ITERATIONS) reached. Check scorecards for remaining issues."
exit 1
