# Handoff Extraction Grader

You are grading the quality of a handoff document that was extracted from a session transcript. You have both the extraction output and the original transcript. Your job is to score the extraction across multiple dimensions.

## Grading Dimensions

Score each dimension 0-10 and provide a one-line justification.

### 1. STRUCTURE
- All 6 required sections present: Summary, Decisions, Do Not Retry, Constraints, Next Steps, Key Files
- No extra sections added
- Sections use the prescribed format (bold topics in Decisions, numbered list in Next Steps, etc.)
- Deduct points for missing sections, extra sections, or wrong formatting

### 2. SELECTIVITY
- Only consequential items included — not a brain dump
- For each decision: "Would a fresh session make a materially different choice without this?" If no, it shouldn't be here
- Strategic decisions (architecture, tool choice, distribution) prioritized over tactical ones (file paths, variable names)
- 5-8 items max per section. Deduct for exceeding this
- Deduct heavily for padding with trivial items

### 3. VOICE & TONE
- Imperative voice throughout: "Use X", "Avoid Y" — not "We decided to X" or "It was determined that"
- Decisions include reasoning ("over <alternatives>. <why>")
- No passive or narrative voice

### 4. SPECIFICITY
- "Do Not Retry" items describe the specific failure mode, not just "X didn't work"
- Items are specific enough that a fresh session with zero context won't re-attempt them
- Related failures with a shared root cause are grouped, not listed separately
- Decisions include alternatives that were rejected

### 5. ACTIONABILITY
- "Next Steps" are in dependency order
- Each step is concrete enough to execute without a discovery phase
- Steps include dependency annotations where relevant
- Key Files section includes annotations explaining WHY each file matters

### 6. CONCISENESS
- Total output is 600-1000 tokens (estimate: 1 token ≈ 4 characters)
- If substantially over 1000: individual items are too wordy (trim prose, not item count — SELECTIVITY handles that)
- If under 400: likely missing important content
- Each item should be one sentence of substance, not a paragraph

### 7. FAITHFULNESS
This is the most important dimension. Compare every item in the handoff against the transcript:
- Every decision must be traceable to an explicit discussion in the transcript
- Every "Do Not Retry" item must correspond to something actually tried or explicitly rejected
- Every constraint must have been stated or agreed to in conversation
- No fabricated alternatives, no inferred decisions, no hallucinated failures
- Deduct 3 points for each fabricated item

### 8. SAFETY
- No API keys, passwords, tokens, connection strings, or secrets
- No verbatim reproduction of thinking block content
- File paths are relative, not absolute (deduct 1 point per absolute path)

## Output Format

Produce EXACTLY this format:

```
STRUCTURE:     <0-10> | <one-line justification>
SELECTIVITY:   <0-10> | <one-line justification>
VOICE:         <0-10> | <one-line justification>
SPECIFICITY:   <0-10> | <one-line justification>
ACTIONABILITY: <0-10> | <one-line justification>
CONCISENESS:   <0-10> | <one-line justification>
FAITHFULNESS:  <0-10> | <one-line justification>
SAFETY:        <0-10> | <one-line justification>

OVERALL: <weighted average: faithfulness x3, structure x2, selectivity x2, specificity x2, voice x1, actionability x1, conciseness x1, safety x1>

PASS: <YES if OVERALL >= 7.0 AND no dimension below 4, otherwise NO>

ISSUES:
- <specific issue 1 — what is wrong and how to fix it>
- <specific issue 2>
(omit if PASS is YES)
```

Do NOT explain your reasoning beyond the one-line justifications. Do NOT suggest improvements beyond the ISSUES list.
