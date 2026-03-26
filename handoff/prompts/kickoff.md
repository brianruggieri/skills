# Kickoff Prompt Generation

Generate a kickoff prompt that a fresh Claude Code session receives as its first user message. The handoff document provides context (via system prompt); the kickoff prompt provides action instructions.

## Inputs

You have:
1. The extracted handoff sections (Summary, Decisions, Next Steps, Key Files)
2. User's execution requirements (gathered interactively in Phase 5)
3. Current branch name and status
4. Plan/spec file paths (detected from Key Files and transcript)

## Auto-Detection

Before asking the user, detect these from the handoff context:

### Plan/Spec Files
Scan Key Files and the transcript for files matching:
- `**/plans/**`, `**/specs/**`, `**/designs/**`
- Files with "plan", "spec", "design", "rfc", "proposal" in the name
- `PLAN.md`, `SPEC.md`, `DESIGN.md`, `TODO.md`

### Test Commands
Look for test commands in:
1. CLAUDE.md (project conventions)
2. `package.json` scripts (`test`, `test:unit`, `test:e2e`)
3. Transcript references to pytest, jest, vitest, cargo test, go test, etc.
4. Makefile targets

### Task Structure
From Next Steps, detect:
- Total number of tasks
- Which tasks are already complete (mentioned as done in the session)
- Dependency chains (tasks that reference other tasks)
- Independent tasks (parallelizable)

### Branch Status
- Current branch name
- Whether it exists on remote
- Whether commits need pushing

## User Requirements Mapping

Map the user's freeform requirements to prompt sections:

| User says | Prompt section |
|-----------|---------------|
| "full effort", "thorough" | Execution: subagent-driven, spec review + code review after each task |
| "fast", "quick" | Execution: sequential, no intermediate reviews |
| "appropriate models", "model tiers" | Model tiers: sonnet for mechanical, opus for judgment |
| "end with a PR", "create PR" | Post-completion: push + `gh pr create` with summary points |
| "deploy", "ship it" | Post-completion: deploy step after PR |
| "right branch", "worktree" | Branch: verify/create branch, optional worktree setup |
| "tests", "verify" | Post-completion: run detected test command |
| "parallel", "concurrent" | Execution: parallelize independent tasks |

Defaults (when user says "default" or doesn't specify):
- Execution: subagent-driven development
- Post-completion: run tests + create PR
- Branch: use current branch (already checked out)

## Output Structure

Generate the kickoff prompt with these sections in order. Omit sections that don't apply.

```
[Action + Plan Reference]
Execute [description] at [plan-file-path] using [execution-approach].
— OR if no plan file: "Implement the next steps from the handoff context."

[Branch Setup]
Branch: [name] ([already exists / needs creation]).
— If worktree needed: "Create worktree at .worktrees/[name] from [branch]."

[Completed Work — only if some tasks are done]
[Task N] ([description]) is already complete and committed. Start from [Task N+1].

[Execution Approach]
- [subagent-driven / parallel agents / sequential]
- [model tier assignment — only if user specified]
  - Use sonnet for mechanical tasks ([list]) — clear specs, isolated files
  - Use opus for judgment tasks ([list]) — integration, design decisions
- [parallelization strategy — only if applicable]
  - Parallelize independent tasks: [list]
  - Sequential chain: [A → B → C]

[Post-Completion Steps]
After all tasks pass:
- Run [test command]
- Push branch and create PR with gh pr create summarizing:
  - [key point 1 — from Decisions/Summary]
  - [key point 2]
- [deploy step — only if specified]

[Project Conventions]
Read CLAUDE.md for project conventions. [1-2 critical conventions from the session, e.g., "Always use .venv/bin/python. Tabs for indentation."]
```

## Rules

- Keep under 300 words. Dense, not verbose.
- Use imperative voice throughout.
- Reference specific file paths from Key Files.
- The prompt must be self-contained — don't assume the reader has context beyond the system prompt.
- If the user didn't specify model tiers, omit that section entirely.
- Always include a test step — detect the test command or use "run the test suite".
- PR summary points should be derived from Decisions and Summary — what does a reviewer need to know?
