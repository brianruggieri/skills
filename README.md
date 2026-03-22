# skills

Custom [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills for my development workflow. Built for how I work; fork and adapt for yours.

Each skill is a directory with a `SKILL.md` that Claude Code discovers automatically. Invoke with `/skill-name` inside any Claude Code session.

## Skills

### grill-me

Stress-test a plan or design through relentless Socratic questioning. Builds a risk tree, walks it depth-first, and won't move on until every branch is resolved. Dispatches research agents when you say "I don't know" instead of letting you off the hook.

`/grill-me` when you want your design torn apart before production does it for you.

### fix-pr-reviews

Systematically address every review comment on a GitHub PR. Categorizes comments by priority, fixes code, runs tests, resolves threads via GraphQL, and updates the PR description. Nine-phase workflow that handles the tedious loop of review-fix-verify-push.

`/fix-pr-reviews` when a PR has review comments piling up.

### handoff

Extract structured context from a planning session and generate a handoff document for a fresh build session. Captures decisions, negative knowledge ("Do Not Retry"), constraints, and next steps. Uses a JSONL preprocessor and Claude-as-extractor architecture. Auto-saves session transcripts for eval corpus building.

Includes a blind eval harness (`/eval-extract`) that dispatches isolated subagents to grade extraction quality across 8 dimensions.

`/handoff` when a planning session is complete and you want to start building in a clean context window.

### scope-repo

Full codebase planning pipeline using Claude Code Agent Teams. Spawns 4-9 analyst agents to scan a repo in parallel, interviews you using their findings, validates scope, and outputs a prioritized `ROADMAP.md` plus GitHub Issues with dependency links. One session, ~20-30 minutes.

`/scope-repo` when you want a structured roadmap for a repo you're about to invest serious time in.

Requires Agent Teams enabled (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in settings.json). Also ships a standalone CLI wrapper (`scope-repo/scopework`) for running outside a session.

## Install

Symlink individual skills into your Claude Code skills directory:

```bash
git clone https://github.com/brianruggieri/skills.git ~/git/skills

# install one skill
ln -s ~/git/skills/grill-me ~/.claude/skills/grill-me

# install all
for skill in ~/git/skills/*/; do
  [ -f "$skill/SKILL.md" ] && ln -s "$skill" ~/.claude/skills/$(basename "$skill")
done
```

Or copy a skill directory into any project's `.claude/skills/` to share it with collaborators.

## Structure

```
skills/
├── grill-me/
│   └── SKILL.md
├── fix-pr-reviews/
│   └── SKILL.md
├── handoff/
│   ├── SKILL.md
│   ├── prompts/       # extraction + convention detection prompts
│   ├── eval/          # blind eval harness (SKILL.md + grading rubric)
│   ├── scripts/       # JSONL preprocessor
│   └── tests/         # fixtures for eval
└── scope-repo/
    ├── SKILL.md
    ├── scopework      # standalone CLI wrapper
    └── install.sh
```

Each skill is self-contained in its directory. The `SKILL.md` has YAML frontmatter (`name`, `description`, `allowed-tools`) and a markdown body with the full protocol Claude follows when the skill is invoked.

## License

MIT
