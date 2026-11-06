#!/bin/bash
# trigger-eval — measure whether a skill's frontmatter description fires
# when it should and stays silent when it shouldn't.
#
# Usage:
#   run.sh <skill-name> [--model MODEL] [--cwd DIR] [--plugin-dir DIR]
#
# --plugin-dir DIR loads a plugin checkout (e.g. this repo) into each headless
# run, so a skill can be trigger-tested before it is installed anywhere.
# TRIGGER_EVAL_MODEL overrides the default model without a flag.
#
# Prompt sets live in prompts/<skill-name>.txt, one per line:
#   + prompt that MUST load the skill
#   - prompt that must NOT load the skill
#
# Each prompt = one headless claude call (capped at 2 turns, default
# haiku — cheap and trigger behavior is what's under test, not task
# quality). Sessions are DELIBERATELY persisted: the transcript is the
# eval artifact we grep for the Skill invocation. They land under a
# self-labeling junk project dir (session-archaeology filters it).
set -uo pipefail
cd "$(dirname "$0")"

SKILL="${1:?usage: run.sh <skill-name> [--model MODEL] [--cwd DIR] [--plugin-dir DIR]}"; shift
MODEL="${TRIGGER_EVAL_MODEL:-claude-haiku-4-5-20251001}"
RUN_CWD=""
PLUGIN_DIR=""
while [ $# -gt 0 ]; do case "$1" in
	--model) MODEL="$2"; shift 2 ;;
	--cwd) RUN_CWD="$2"; shift 2 ;;
	--plugin-dir) PLUGIN_DIR="$(cd "$2" && pwd -P)" || { echo "no such dir: $2" >&2; exit 2; }; shift 2 ;;
	*) echo "unknown flag: $1" >&2; exit 2 ;;
esac; done

PROMPTS="prompts/${SKILL}.txt"
[ -f "$PROMPTS" ] || { echo "no prompt set at $PROMPTS — write one (+/- prefixed lines)" >&2; exit 2; }

# quota preflight (headless-claude-hygiene) — optional: public cloners
# won't have the gate script, so warn and continue rather than hard-fail.
GATE="$HOME/.claude/scripts/claude-usage-gate.sh"
if [ -x "$GATE" ]; then
	"$GATE" --threshold 85 || { echo "quota hot — aborting eval" >&2; exit 3; }
else
	echo "note: usage gate not found ($GATE) — skipping quota preflight" >&2
fi

# 120s wall-clock cap per prompt, if a timeout binary is available
TIMEOUT=""
for t in gtimeout timeout; do command -v "$t" >/dev/null 2>&1 && { TIMEOUT="$t 120"; break; }; done

# NEUTRAL dir name — naming it after the skill under test leaks the answer
# into the model's cwd and poisons every negative prompt (found on first run)
#
# Permission mode is tied to whose dir we run in. The auto-generated scratch
# dir is disposable, so dontAsk (no prompts) is safe. A caller-supplied --cwd
# is a REAL repo: dontAsk there would let prompt-matrix text mutate its files,
# so we drop to --permission-mode default (prompts) and warn. Override with
# TRIGGER_EVAL_UNSAFE_CWD=1 if you know the cwd is disposable.
if [ -n "$RUN_CWD" ]; then
	if [ "${TRIGGER_EVAL_UNSAFE_CWD:-}" = "1" ]; then
		PERM_MODE="dontAsk"
		echo "warning: TRIGGER_EVAL_UNSAFE_CWD=1 — running dontAsk in caller cwd $RUN_CWD; prompt text can mutate it" >&2
	else
		PERM_MODE="default"
		echo "warning: --cwd is a real dir — running --permission-mode default (prompts) so prompt text can't mutate it. Set TRIGGER_EVAL_UNSAFE_CWD=1 to force dontAsk." >&2
	fi
else
	PERM_MODE="dontAsk"
fi
RUN_CWD="${RUN_CWD:-/tmp/te-w$(printf '%s' "$SKILL" | cksum | cut -d' ' -f1)}"
mkdir -p "$RUN_CWD"
RUN_CWD="$(cd "$RUN_CWD" && pwd -P)"   # resolve /tmp → /private/tmp etc.
PROJ_DIR="$HOME/.claude/projects/$(echo "$RUN_CWD" | tr '/' '-')"

pass=0; fail=0; results=""
while IFS= read -r line; do
	[ -z "$line" ] && continue
	sign="${line:0:1}"; prompt="${line:2}"
	[ "$sign" = "+" ] || [ "$sign" = "-" ] || continue

	before=$(ls "$PROJ_DIR"/*.jsonl 2>/dev/null | wc -l)
	# env -u: nested claude -p hangs inside a live session otherwise.
	# </dev/null is NOT optional: this loop's stdin is the prompt file, and
	# claude -p appends anything on stdin to the prompt — without the redirect
	# every run received the ENTIRE +/- matrix as part of its prompt, which
	# leaks every trigger phrase into every negative (found 2026-11-06).
	( cd "$RUN_CWD" && env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT -u CLAUDE_CODE_SESSION_ID \
		$TIMEOUT claude -p "$prompt" --model "$MODEL" --max-turns 2 --permission-mode "$PERM_MODE" \
		${PLUGIN_DIR:+--plugin-dir "$PLUGIN_DIR"} ) </dev/null >/dev/null 2>&1   # ${x:+...} keeps bash 3.2 (macOS) happy under set -u

	# A run that produced no new transcript (quota, auth, timeout) must not
	# silently inherit the previous prompt's verdict.
	after=$(ls "$PROJ_DIR"/*.jsonl 2>/dev/null | wc -l)
	if [ "$after" -le "$before" ]; then
		fail=$((fail+1)); results="${results}ERR  no transcript written (timeout/quota/auth?) | ${prompt:0:70}\n"; continue
	fi
	# newest transcript = this run
	f=$(ls -t "$PROJ_DIR"/*.jsonl 2>/dev/null | head -1)
	fired=no
	# Anchor the skill match: allow only an optional plugin prefix ending
	# in ':' and require a closing quote right after the name, so e.g.
	# evaluating fix-pr-reviews doesn't count forgejo-fix-pr-reviews.
	[ -n "$f" ] && grep -q "\"name\":\"Skill\"" "$f" && grep -qE "\"skill\":[[:space:]]*\"([^\"]*:)?${SKILL}\"" "$f" && fired=yes

	want=$([ "$sign" = "+" ] && echo yes || echo no)
	if [ "$fired" = "$want" ]; then verdict="OK  "; pass=$((pass+1)); else verdict="MISS"; fail=$((fail+1)); fi
	results="${results}${verdict} want=${want} fired=${fired} | ${prompt:0:70}\n"
done < "$PROMPTS"

echo "== trigger-eval: $SKILL (model: $MODEL${PLUGIN_DIR:+, plugin-dir: $PLUGIN_DIR}) =="
printf "%b" "$results"
echo "== $pass ok, $fail miss =="
[ "$fail" -eq 0 ]
