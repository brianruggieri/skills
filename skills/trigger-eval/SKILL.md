---
name: trigger-eval
description: "Use when shipping or editing any skill's frontmatter description, when a skill 'never fires', 'keeps firing on wrong prompts', or the user says 'run the trigger matrix' / 'test the skill description'. Runs the +/- prompt matrix in prompts/<skill>.txt via ./run.sh and iterates the description until clean. NOT for evaluating a skill's output quality (use ab-experiment)."
allowed-tools: Read Write Edit Bash
---

# Trigger Eval

Measure whether a skill's frontmatter description fires on the prompts it
should and stays silent on the ones it shouldn't.

First resolve this skill's own directory — the harness told you the path to
the `SKILL.md` you just loaded, so `SKILL_DIR` is its parent. Everything below
is relative to that directory (the CWD is not assumed to be the skill dir).

1. Write (or update) the prompt matrix at `<SKILL_DIR>/prompts/<skill>.txt` —
   `+ ` lines MUST load the skill, `- ` lines must NOT. Negatives are the
   valuable half: write near-misses, not obviously-unrelated asks.
2. Run `cd <SKILL_DIR> && ./run.sh <skill> [--model MODEL] [--cwd DIR]`. Exit 0
   = perfect matrix; nonzero = at least one MISS.
3. If any prompt MISSes, edit the target skill's `description:` and re-run
   until the matrix is clean — or run `./evolve.sh <skill>` to do this loop
   automatically (hill-climb rewrite of the description only; see README's
   Evolve section for guards and flags).

See `README.md` for mechanics, caveats, and the model-dependence note.

## Security & Trust Boundary

Prompt files are self-authored — this skill only runs prompts you wrote. By
default each run shells out to `claude -p` in a neutral scratch cwd
(`/tmp/te-w<cksum>`), never the target repo, with `--permission-mode dontAsk`
— safe because the dir is disposable, so a stray prompt can't reach real
project files.

If you pass `--cwd DIR` (a real repo, e.g. for project-scoped skills), the run
drops to `--permission-mode default` (prompts) so prompt-matrix text can't
silently mutate that repo under `dontAsk`, and prints a warning. Set
`TRIGGER_EVAL_UNSAFE_CWD=1` to force `dontAsk` back on when you know the cwd is
disposable.
