---
name: trigger-eval
description: Use when shipping or editing a skill's frontmatter description, or when a skill seems to fire on wrong prompts / never fire — runs the +/- prompt matrix in prompts/<skill>.txt via ./run.sh and iterates the description until clean. NOT for evaluating a skill's output quality (use ab-experiment).
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
   until the matrix is clean.

See `README.md` for mechanics, caveats, and the model-dependence note.

## Security & Trust Boundary

Prompt files are self-authored — this skill only runs prompts you wrote. Each
run shells out to `claude -p` with `--permission-mode dontAsk` in a neutral
scratch cwd (`/tmp/te-w<cksum>`), never the target repo, so a stray prompt
can't reach or mutate real project files.
