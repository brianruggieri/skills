# trigger-eval

Measures skill trigger reliability: does a skill's frontmatter description
fire on the prompts it should, and stay silent on the ones it shouldn't?
The one failure mode a ~100-skill library can't see by eye (adopted from
Chase AI's skill-evals post, rebuilt on our headless-claude-hygiene rules).

## Run

```bash
./run.sh brain-sleep                 # uses prompts/brain-sleep.txt, haiku
./run.sh brain-sleep --plugin-dir "$(git rev-parse --show-toplevel)"   # test THIS checkout, uninstalled
./run.sh my-skill --model claude-sonnet-5        # or TRIGGER_EVAL_MODEL=... in the env
./run.sh my-project-skill --cwd ~/git/my-project # project-scoped skills need an in-scope cwd
                                                 # --cwd runs --permission-mode default (prompts) so
                                                 # prompt text can't mutate the repo; TRIGGER_EVAL_UNSAFE_CWD=1 forces dontAsk
```

Exit 0 = perfect matrix; nonzero = at least one MISS or ERR (or quota gate refused).
ERR means the run wrote no transcript (timeout, quota, auth) — the verdict is
unknown, not a pass, and the harness refuses to reuse the previous prompt's file.

## Prompt sets

`prompts/<skill>.txt`, one prompt per line:
- `+ ` prefix — realistic user ask that MUST load the skill
- `- ` prefix — adjacent-sounding ask that must NOT load it

Negative prompts are the valuable half: write them as near-misses
(same vocabulary, different intent), not obviously-unrelated asks.

## Mechanics & caveats

- Each prompt is one headless `claude -p` capped at `--max-turns 2` on the
  current haiku by default — we're testing the trigger, not the task. ~6
  prompts ≈ pennies and a couple of minutes. Keep the default current: the
  2026-11-06 audit ran identical matrices on haiku 4.5 (43/68) and haiku 5.5
  (62/68, zero over-triggers) — a stale floor model under-fires on its own.
- Detection = a `Skill` tool invocation for the target skill in the run's
  session JSONL. Sessions persist deliberately (the transcript is the
  artifact) under neutral `/tmp/te-w<cksum>` project dirs — the name is
  deliberately skill-agnostic so it doesn't leak the answer into the
  model's cwd; known junk, session-archaeology filters them.
- Quota gate at 85% runs first if `~/.claude/scripts/claude-usage-gate.sh`
  exists (it is not shipped here); otherwise the harness warns and continues.
  The nested-session hang is avoided with `env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT`.
- Each `claude -p` gets `</dev/null`. The prompt loop's stdin is the matrix
  file and `claude -p` appends stdin to the prompt, so without the redirect
  every run was handed the whole +/- list — every trigger phrase leaked into
  every negative. A matrix that "passes" with that leak proves nothing; the
  bug was found and fixed 2026-11-06 (see `docs/audits/`).
- Trigger behavior is model-dependent AND stochastic: a matrix that passes
  on haiku is a floor, not a ceiling, and a single run per prompt is one
  sample. Re-run a borderline matrix twice, and with your daily-driver model,
  before trusting or tuning a description on one MISS.
- When shipping a NEW skill: write the prompt set first, run the matrix,
  then iterate the frontmatter description until clean — cheaper than
  discovering a never-fires skill months later.
