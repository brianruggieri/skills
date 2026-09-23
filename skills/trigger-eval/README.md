# trigger-eval

Measures skill trigger reliability: does a skill's frontmatter description
fire on the prompts it should, and stay silent on the ones it shouldn't?
The one failure mode a ~100-skill library can't see by eye (adopted from
Chase AI's skill-evals post, rebuilt on our headless-claude-hygiene rules).

## Run

```bash
./run.sh brain-sleep                 # uses prompts/brain-sleep.txt, haiku
./run.sh my-skill --model claude-sonnet-5
./run.sh curling-research --cwd ~/git/curling   # project-scoped skills need an in-scope cwd
                                                 # --cwd runs --permission-mode default (prompts) so
                                                 # prompt text can't mutate the repo; TRIGGER_EVAL_UNSAFE_CWD=1 forces dontAsk
```

Exit 0 = perfect matrix; nonzero = at least one MISS (or quota gate refused).

## Prompt sets

`prompts/<skill>.txt`, one prompt per line:
- `+ ` prefix — realistic user ask that MUST load the skill
- `- ` prefix — adjacent-sounding ask that must NOT load it

Negative prompts are the valuable half: write them as near-misses
(same vocabulary, different intent), not obviously-unrelated asks.

## Mechanics & caveats

- Each prompt is one headless `claude -p` capped at `--max-turns 2` on
  haiku by default — we're testing the trigger, not the task. ~6 prompts
  ≈ pennies and a couple of minutes.
- Detection = a `Skill` tool invocation for the target skill in the run's
  session JSONL. Sessions persist deliberately (the transcript is the
  artifact) under neutral `/tmp/te-w<cksum>` project dirs — the name is
  deliberately skill-agnostic so it doesn't leak the answer into the
  model's cwd; known junk, session-archaeology filters them.
- Quota gate at 85% runs first; the nested-session hang is avoided with
  `env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT`.
- Trigger behavior is model-dependent: a matrix that passes on haiku is
  a floor, not a ceiling. Re-run with your daily-driver model before
  trusting a borderline skill description.
- When shipping a NEW skill: write the prompt set first, run the matrix,
  then iterate the frontmatter description until clean — cheaper than
  discovering a never-fires skill months later.

## Evolve (autolearning loop)

`evolve.sh <skill>` automates the iterate step: run matrix → headless
claude rewrites ONLY the frontmatter description against the misses →
re-run → keep the candidate only if the score strictly improves, else
revert. Stops when clean or `--max-iters` (default 3) is exhausted.

```bash
./evolve.sh resume-tailor --model claude-sonnet-5            # matrix on sonnet
./evolve.sh my-skill --reps 2                                # noisy haiku floor
./evolve.sh my-skill --codex                                 # cross-model final review
```

Hallucination guards, in code not prompts: mechanical fitness (the matrix),
rewriter confined to the description line, candidates echoing a matrix
prompt verbatim rejected (test-set memorization), strict-improvement
acceptance with revert, and optional `--codex` binary-rubric review of the
final diff by a different model family. The body is never modified; the
file is edited in place but never committed/packaged — review the printed
diff. Rewrites run `--no-session-persistence` from a scratch cwd (no junk
sessions); matrix sessions persist as usual (they're the detection
artifact). `test/selftest.sh` exercises accept + reject paths with stubbed
binaries, zero quota.
