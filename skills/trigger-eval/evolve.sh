#!/bin/bash
# evolve.sh — description-rewrite autolearning loop on the trigger matrix.
#
# Runs run.sh, and while the matrix has misses, asks a headless claude to
# rewrite ONLY the frontmatter description, keeping a candidate only when
# the matrix score strictly improves (hill-climb with revert). The skill
# body is never touched. Optional --codex runs a cross-model review of the
# final description (binary rubric) so a Claude-written description isn't
# judged solely by Claude.
#
# Usage:
#   evolve.sh <skill> [--skill-file PATH] [--model MATRIX_MODEL]
#             [--rewrite-model MODEL] [--max-iters N] [--reps R] [--codex]
#
# Exit: 0 = matrix clean; 1 = iterations exhausted (best description kept,
# which is the original if nothing improved); 2 = usage/validation error.
#
# Hallucination guards (see README):
#  - fitness is mechanical (run.sh matrix), not judged prose
#  - rewriter output is confined to the description line by this script
#  - candidates echoing a matrix prompt verbatim are rejected (anti-Goodhart)
#  - strict-improvement acceptance, revert otherwise
#  - --codex cross-model rubric review of the final candidate
#
# ponytail: 1-rep hill climb can accept haiku noise as "improvement";
# use --reps 2+ on noisy floors, or --model claude-sonnet-5.
set -uo pipefail
cd "$(dirname "$0")"

SKILL="${1:?usage: evolve.sh <skill> [--skill-file PATH] [--model M] [--rewrite-model M] [--max-iters N] [--reps R] [--codex]}"; shift
MATRIX_MODEL=""
REWRITE_MODEL="claude-sonnet-5"
MAX_ITERS=3
REPS=1
CODEX=0
SKILL_FILE=""
while [ $# -gt 0 ]; do case "$1" in
	--model) MATRIX_MODEL="$2"; shift 2 ;;
	--rewrite-model) REWRITE_MODEL="$2"; shift 2 ;;
	--max-iters) MAX_ITERS="$2"; shift 2 ;;
	--reps) REPS="$2"; shift 2 ;;
	--codex) CODEX=1; shift ;;
	--skill-file) SKILL_FILE="$2"; shift 2 ;;
	*) echo "unknown flag: $1" >&2; exit 2 ;;
esac; done

# test seams (selftest stubs these)
RUN_SH="${EVOLVE_RUN_SH:-./run.sh}"
CLAUDE_BIN="${EVOLVE_CLAUDE_BIN:-claude}"

SKILL_FILE="${SKILL_FILE:-$HOME/.claude/skills/$SKILL/SKILL.md}"
SKILL_FILE="$(python3 -c 'import os,sys;print(os.path.realpath(sys.argv[1]))' "$SKILL_FILE")"
[ -f "$SKILL_FILE" ] || { echo "no SKILL.md at $SKILL_FILE" >&2; exit 2; }
PROMPTS="prompts/${SKILL}.txt"
[ -f "$PROMPTS" ] || { echo "no prompt set at $PROMPTS — write one first (see README)" >&2; exit 2; }

get_desc() { python3 - "$SKILL_FILE" <<'PY'
import sys
lines = open(sys.argv[1]).read().split('\n')
inf = False
for i, l in enumerate(lines):
    if l.strip() == '---':
        if not inf: inf = True; continue
        break
    if inf and l.startswith('description:'):
        if i + 1 < len(lines) and lines[i+1][:1] in (' ', '\t'):
            sys.exit(3)  # folded/multi-line description — not supported
        print(l[len('description:'):].strip()); sys.exit(0)
sys.exit(1)
PY
}

set_desc() { python3 - "$SKILL_FILE" "$1" <<'PY'
import sys
path, new = sys.argv[1], sys.argv[2]
lines = open(path).read().split('\n')
inf = False
for i, l in enumerate(lines):
    if l.strip() == '---':
        if not inf: inf = True; continue
        break
    if inf and l.startswith('description:'):
        lines[i] = 'description: ' + new
        open(path, 'w').write('\n'.join(lines)); sys.exit(0)
sys.exit(1)
PY
}

get_body() { python3 - "$SKILL_FILE" <<'PY'
import sys
t = open(sys.argv[1]).read()
parts = t.split('\n---\n', 2)
print(parts[2] if len(parts) > 2 else t)
PY
}

ORIG_DESC="$(get_desc)" || { echo "cannot read a single-line 'description:' from $SKILL_FILE (folded YAML unsupported)" >&2; exit 2; }
N_PROMPTS=$(grep -cE '^[+-] ' "$PROMPTS")

echo "== evolve: $SKILL =="
echo "skill file: $SKILL_FILE"
echo "budget: up to $(( N_PROMPTS * REPS * (MAX_ITERS + 1) )) matrix calls + $MAX_ITERS rewrite calls (headless, shared quota)"

# run the matrix REPS times; sets SCORE (total ok) and MISSES (deduped MISS lines)
run_matrix() {
	SCORE=0; MISSES=""; local out ok
	for _ in $(seq 1 "$REPS"); do
		out=$($RUN_SH "$SKILL" ${MATRIX_MODEL:+--model "$MATRIX_MODEL"} 2>&1)
		case "$out" in *"quota hot"*) echo "$out" >&2; echo "quota gate tripped — aborting" >&2; exit 3 ;; esac
		ok=$(printf '%s\n' "$out" | sed -n 's/^== \([0-9][0-9]*\) ok.*/\1/p' | tail -1)
		[ -n "$ok" ] || { printf '%s\n' "$out" >&2; echo "could not parse run.sh output" >&2; exit 2; }
		SCORE=$((SCORE + ok))
		MISSES="$MISSES$(printf '%s\n' "$out" | grep '^MISS' || true)
"
	done
	MISSES=$(printf '%s' "$MISSES" | awk 'NF' | sort -u)
}

# candidate echoes a matrix prompt verbatim? that's memorizing the test set
overfits() {
	local new="$1" p
	while IFS= read -r line; do
		case "$line" in "+ "*|"- "*) p="${line:2}" ;; *) continue ;; esac
		case "$new" in *"$p"*) return 0 ;; esac
	done < "$PROMPTS"
	return 1
}

PERFECT=$((N_PROMPTS * REPS))
run_matrix
BEST_SCORE=$SCORE; BEST_DESC="$ORIG_DESC"
echo "initial score: $SCORE/$PERFECT"

iter=0
while [ "$BEST_SCORE" -lt "$PERFECT" ] && [ "$iter" -lt "$MAX_ITERS" ]; do
	iter=$((iter + 1))
	echo "-- iteration $iter: rewriting description against $(printf '%s\n' "$MISSES" | grep -c .) miss(es)"

	PFILE=$(mktemp)
	{
		echo "You are tuning the frontmatter description of a Claude Agent Skill so it triggers correctly."
		echo
		echo "SKILL BODY — the only source of truth. The description must not claim anything the body does not support:"
		get_body
		echo
		echo "CURRENT DESCRIPTION:"
		echo "$BEST_DESC"
		echo
		echo "TRIGGER MATRIX MISSES (want=yes fired=no means it failed to trigger; want=no fired=yes means it over-triggered):"
		printf '%s\n' "$MISSES"
		echo
		echo "Rewrite the description to fix the misses while keeping current hits. Rules:"
		echo "- Triggering conditions only. Never summarize the skill's workflow or outputs."
		echo "- Every claim must be supported by the skill body."
		echo "- Do not quote any test prompt verbatim; generalize the phrasing."
		echo "- Third person, single line, under 900 characters."
		echo "- Keep a 'Not for ...' negative scope if the current description has one."
		echo
		echo "Output ONLY the new description text on a single line. No quotes, no markdown, no explanation."
	} > "$PFILE"

	SCRATCH=$(mktemp -d /tmp/claude-evolve-XXXX)
	# env -u: sanctioned nesting escape; --no-session-persistence + scratch cwd: no junk sessions
	NEW=$( cd "$SCRATCH" && env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT -u CLAUDE_CODE_SESSION_ID \
		$CLAUDE_BIN -p "$(cat "$PFILE")" --model "$REWRITE_MODEL" --max-turns 1 --no-session-persistence 2>/dev/null )
	rm -rf "$SCRATCH" "$PFILE"
	NEW=$(printf '%s\n' "$NEW" | awk 'NF' | tail -1)

	if [ -z "$NEW" ] || [ "$NEW" = "$BEST_DESC" ] || [ "${#NEW}" -gt 900 ]; then
		echo "   rejected candidate (empty, unchanged, or >900 chars)"; continue
	fi
	if overfits "$NEW"; then
		echo "   rejected candidate (echoes a matrix prompt verbatim — test-set memorization)"; continue
	fi

	set_desc "$NEW" || { echo "failed to write description" >&2; exit 2; }
	run_matrix
	if [ "$SCORE" -gt "$BEST_SCORE" ]; then
		echo "   accepted: $SCORE/$PERFECT (was $BEST_SCORE)"
		BEST_SCORE=$SCORE; BEST_DESC="$NEW"
	else
		echo "   reverted: $SCORE/$PERFECT did not beat $BEST_SCORE"
		set_desc "$BEST_DESC"
	fi
done

echo
echo "== result: $BEST_SCORE/$PERFECT =="
if [ "$BEST_DESC" != "$ORIG_DESC" ]; then
	echo "--- original"; echo "$ORIG_DESC"
	echo "+++ final"; echo "$BEST_DESC"
	echo "(file updated in place — review the diff before packaging/committing)"
else
	echo "description unchanged"
fi

if [ "$CODEX" = 1 ] && [ "$BEST_DESC" != "$ORIG_DESC" ]; then
	if command -v codex >/dev/null 2>&1; then
		echo; echo "== codex cross-model review =="
		codex exec "Review this rewritten frontmatter description for an AI agent skill. Answer each criterion with PASS or FAIL plus one sentence. 1) Every claim in the NEW description is supported by the SKILL BODY (no invented capabilities). 2) It states triggering conditions only — it does not summarize the skill's internal workflow or outputs. 3) It reads as generalized triggers, not memorized test phrases. 4) Nothing important in the ORIGINAL's scope (positive or negative) was silently dropped.

ORIGINAL: $ORIG_DESC

NEW: $BEST_DESC

SKILL BODY:
$(get_body)"
	else
		echo "codex CLI not found — review the diff above cross-model manually (e.g. /codex)"
	fi
fi

[ "$BEST_SCORE" -eq "$PERFECT" ]
