# Contributing

Each skill is a directory under `skills/` containing a `SKILL.md` with YAML
frontmatter (`name` matching the directory, a `description` that states what
the skill does AND when to use it — including what it is NOT for — and
optionally a space-separated `allowed-tools` string).

Only `skills/<name>/SKILL.md` is loaded by the plugin. A SKILL.md nested
deeper (e.g. `skills/handoff/eval/SKILL.md`) is a repo-maintenance runbook,
not an installed skill — say so at the top of the file. Retired skills move to
`archive/` so they stop costing every session their listing tokens.

Before opening a PR:

1. Validate: `claude plugin validate .`
2. Trigger-test the description. Every active skill ships a matrix at
   `skills/trigger-eval/prompts/<name>.txt` (`+` prompts that must fire, `-`
   near-misses that must not). Whenever you change a skill's description — or
   add a new skill — update its matrix and run
   `cd skills/trigger-eval && ./run.sh <name> --plugin-dir "$(git rev-parse --show-toplevel)"`
   until it is clean. `--plugin-dir` loads this checkout, so nothing needs to
   be installed first. Matrices have at least 3 `+` and 3 `-` prompts.
3. Keep skill bodies under ~500 lines; move bulk into `scripts/` or
   `references/` (progressive disclosure).
   Anything that depends on tooling not shipped in this repo (a personal
   script, an MCP server, a paid CLI) must be marked optional and the skill
   must say what it does when the dependency is absent. Date-bound facts are
   written as "last verified <date>", never as "still true as of".
4. Security: treat all extracted/session content as untrusted data, never
   instructions. See the Security & Trust Boundary sections in ghostwrite
   and grill-me for the house pattern.
