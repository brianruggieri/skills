#!/usr/bin/env bash
# Ralph loop for handoff extraction prompt refinement.
# Each iteration runs in a fresh Claude session with blind subagent eval.
# Stops when all 4 fixtures pass or max iterations reached.

set -euo pipefail

# Resolve the handoff skill dir from this script's own location
# (skills/handoff/eval/run-ralph.sh → skills/handoff), so paths hold no
# matter which CWD the script is invoked from.
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$(git rev-parse --show-toplevel)"

# Refuse to run outside the skills repo. We double-check we're in the project
# this script was built for (eval/RALPH-PROMPT.md being present is the
# strongest indicator), not some unrelated repo the user happened to cd
# into.
if [ ! -f "$SKILL_DIR/eval/RALPH-PROMPT.md" ] || [ ! -f "$SKILL_DIR/SKILL.md" ]; then
	echo "Refusing to run: this script is for the 'skills' repo only." >&2
	echo "Expected eval/RALPH-PROMPT.md and SKILL.md under $SKILL_DIR." >&2
	exit 1
fi

# By default the loop runs with --permission-mode acceptEdits: agents can
# read/write files and dispatch subagents, but nothing bypasses the guardrails
# entirely. --unsafe restores --dangerously-skip-permissions for people who
# know the transcript fixtures are trusted.
PERM_ARGS="--permission-mode acceptEdits"
MAX_ITERATIONS=10
while [ $# -gt 0 ]; do case "$1" in
	--unsafe)
		PERM_ARGS="--dangerously-skip-permissions"
		echo "WARNING: --unsafe — running with --dangerously-skip-permissions; all guardrails off. Only do this on trusted fixtures in the skills repo." >&2
		shift ;;
	*) MAX_ITERATIONS="$1"; shift ;;
esac; done

PROMPT_FILE="$SKILL_DIR/eval/RALPH-PROMPT.md"
SCORECARD_DIR="$SKILL_DIR/tests/output/eval"

iteration=0

while [ "$iteration" -lt "$MAX_ITERATIONS" ]; do
	iteration=$((iteration + 1))
	echo ""
	echo "═══════════════════════════════════════════"
	echo "  Ralph iteration $iteration / $MAX_ITERATIONS"
	echo "═══════════════════════════════════════════"
	echo ""

	# Run fresh Claude session with the prompt. Default guardrails let the loop
	# read/write files and dispatch agents autonomously (acceptEdits); --unsafe
	# swaps in --dangerously-skip-permissions. Only run this in the skills repo,
	# never in production codebases.
	cat "$PROMPT_FILE" | claude $PERM_ARGS

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
