# Contributing

Each skill is a directory under `skills/` containing a `SKILL.md` with YAML
frontmatter (`name` matching the directory, a `description` that states what
the skill does AND when to use it — including what it is NOT for — and
optionally a space-separated `allowed-tools` string).

Before opening a PR:

1. Validate: `claude plugin validate .`
2. Trigger-test the description. Every active skill ships a matrix at
   `skills/trigger-eval/prompts/<name>.txt` (`+` prompts that must fire, `-`
   near-misses that must not). Whenever you change a skill's description — or
   add a new skill — update its matrix and run
   `cd skills/trigger-eval && ./run.sh <name>` until it is clean.
3. Keep skill bodies under ~500 lines; move bulk into `scripts/` or
   `references/` (progressive disclosure).
4. Security: treat all extracted/session content as untrusted data, never
   instructions. See the Security & Trust Boundary sections in ghostwrite
   and grill-me for the house pattern.
