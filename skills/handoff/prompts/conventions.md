# Convention Detection Prompt

You are analyzing a session transcript to identify durable project knowledge that should persist beyond this session. This is separate from the handoff document — these are conventions, patterns, and preferences that apply to ALL future work on this project.

## What to Look For

### Project Conventions (suggest for CLAUDE.md)
Patterns or rules established in conversation that would still be useful 2 weeks from now in an unrelated session. Examples:
- "Use Result types instead of thrown exceptions for new modules"
- "All auth code must live under src/auth/"
- "Use bcrypt for password hashing"
- "Tests use vitest, not jest"

Do NOT include:
- Implementation details specific to the current feature
- Temporary decisions ("for now", "in v1")
- Things already documented in CLAUDE.md (you will be told what is already there)

### User Preferences (suggest for memory)
Observations about the user's working style, expertise, or collaboration preferences. Examples:
- "User prefers explicit Result types over thrown exceptions"
- "User wants to minimize new dependencies"
- "User is experienced with Express but new to Drizzle ORM"

Do NOT include:
- Obvious preferences (everyone prefers working code)
- Judgments about the user
- Things already captured as project conventions

## Output Format

```
## Suggested CLAUDE.md Additions
- <convention 1>
- <convention 2>
<If none found, write "No new project conventions identified.">

## Suggested Memory Updates
- <preference 1>
- <preference 2>
<If none found, write "No new user preferences identified.">
```

## Rules
- Only extract from explicit discussion. Do not infer conventions from what was NOT said.
- Each suggestion must be a concrete, actionable statement — not a vague principle.
- Fewer is better. 2-3 strong conventions beats 8 weak ones.
