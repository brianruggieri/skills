# Handoff Extraction Prompt

You are reading a preprocessed session transcript. Your job is to extract a handoff document that gives a fresh Claude Code session everything it needs to continue this work — and nothing it doesn't.

## Rules

- Write in imperative voice ("Use X", "Avoid Y", not "We decided to X")
- Only extract what was explicitly discussed or demonstrated in the transcript. Do NOT infer decisions that were not stated. Do NOT fabricate alternatives that were not mentioned.
- Be ruthlessly selective. A handoff with 20 minor decisions buries the 3 that matter. For each item ask: "Would a fresh session make a materially different choice without this?" If no, omit it.
- Do NOT include API keys, passwords, connection strings, tokens, or secrets. If a decision references a secret, describe the decision without the value.
- Target 600-1000 tokens total. If the session was long, prioritize recency and relevance over completeness.

## Output Format

Produce EXACTLY this markdown structure. Do not add, remove, or rename sections.

```
## Summary
<2-3 sentences. What was accomplished in this session and where it stopped.>

## Decisions
<Bulleted list. Only decisions that affect how the next session proceeds.>
- **<topic>:** <choice> over <alternatives>. <one sentence of reasoning>
<If thinking blocks reveal Claude was uncertain about a decision, append [FRAGILE]>
<If no meaningful decisions were made, write "No significant decisions captured.">

## Do Not Retry
<Bulleted list. What was tried or considered and failed or was explicitly ruled out.>
- <what was attempted> — <why it failed or was ruled out>
<This is the highest-value section. Be specific about failure modes so the next session does not re-attempt.>
<If nothing failed, write "No failed approaches to report.">

## Constraints
<Bulleted list. Agreements and boundaries from conversation NOT captured in code or config.>
- <constraint>
<Examples: "no new dependencies", "defer OAuth until v2", "keep all auth code in src/auth/">
<If no conversational constraints exist, write "No additional constraints beyond what is in code.">

## Next Steps
<Numbered list in dependency order. Concrete enough to execute without a discovery phase.>
1. <first task> — <why it is first, or what it depends on>
2. <second task> — <dependency if any>
<If the session ended with no clear next steps, write "Session ended without a defined plan. Review the conversation for context.">

## Key Files
<Bulleted list. Only files the next session will need to touch or reference.>
- `<path>` — <one-line annotation>
<Derive from the "Files Referenced" section in the transcript header and from file paths mentioned in conversation.>
```

## Thinking Block Instructions

The transcript may contain `<claude-thinking>` blocks. These are Claude's internal deliberation from the planning session. Use them to:

1. **Detect [FRAGILE] decisions** — if thinking shows hedging, uncertainty, or "I'm not sure but..." before committing to a choice in the visible response, flag that decision as [FRAGILE].
2. **Find negative knowledge** — thinking blocks often contain rejected approaches that didn't make it into the visible response. These belong in "Do Not Retry."
3. **Identify deeper reasoning** — use the reasoning in thinking blocks to write better "why" explanations in the Decisions section.

Do NOT reproduce thinking block content verbatim. Extract the insight, not the stream of consciousness.
