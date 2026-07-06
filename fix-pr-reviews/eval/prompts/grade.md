# PR Comment Triage Grader

You are grading the quality of a PR review comment triage. You have the triage output, the original fixture (PR context + comments + source code), and this rubric. Score the triage across multiple dimensions.

## Grading Dimensions

Score each dimension 0-10 and provide a one-line justification.

### 1. TRIAGE_ACCURACY
The most important dimension. For each comment, evaluate whether the assigned priority is correct:
- **Critical items missed:** If a security bug, logic error, or data-loss risk was categorized below critical, deduct 3 points per instance
- **Over-promotion:** If a style nit was promoted to critical or important, deduct 1 point per instance
- **Correct classification:** Each correctly categorized comment confirms accuracy
- Score 10 = every comment's priority matches its actual severity based on the source code context

### 2. CONTEXT_AWARENESS
Did the triage demonstrate understanding of the source code, not just the comment text?
- References specific lines, functions, or patterns from the source context
- Recognizes when a politely-worded comment flags a serious issue (tone ≠ severity)
- Identifies when a comment is about code that doesn't match what the reviewer described
- Score 10 = every rationale references relevant source code evidence

### 3. ACTION_QUALITY
Is the planned action appropriate for each comment?
- Critical/important: plan describes a specific, minimal fix
- Style: plan describes the concrete change (not just "fix it")
- Informational: correctly identified as no-fix-needed
- Fix plans don't over-engineer or introduce unnecessary changes
- Score 10 = every action plan is appropriately scoped and specific

### 4. SKIP_JUSTIFICATION
When a comment is categorized as informational or skipped:
- Is the reason valid and specific?
- Does it reference why the concern doesn't apply (citing code or design)?
- Does it distinguish "future improvement" from "not applicable"?
- Deduct 2 points for each skip with no justification or a vague justification
- Score 10 = every skip has a clear, evidence-based reason

### 5. THREAD_COMPREHENSION
For comments that are part of a thread (have `in_reply_to_id` or are replied to):
- Did the triage read the full thread and understand the resolution?
- Does it reflect the final consensus, not just the first comment?
- Does it avoid re-litigating issues already resolved in the thread?
- If no threaded comments exist in the fixture, score 8 (neutral — cannot demonstrate)
- Score 10 = all threads correctly interpreted, resolutions respected

### 6. COMPLETENESS
- Every comment in the fixture is addressed in the output
- No comments silently dropped
- The summary counts match the individual categorizations
- Deduct 2 points per dropped comment
- Score 10 = all comments accounted for with consistent summary

### 7. CONCISENESS
- Output follows the prescribed format (not prose paragraphs)
- Rationale is one sentence, not a paragraph
- Plan is actionable in 1-2 sentences
- Summary section is present and accurate
- Score 10 = clean structured output, no filler

## Output Format

Produce EXACTLY this format:

```
TRIAGE_ACCURACY:     <0-10> | <one-line justification>
CONTEXT_AWARENESS:   <0-10> | <one-line justification>
ACTION_QUALITY:      <0-10> | <one-line justification>
SKIP_JUSTIFICATION:  <0-10> | <one-line justification>
THREAD_COMPREHENSION:<0-10> | <one-line justification>
COMPLETENESS:        <0-10> | <one-line justification>
CONCISENESS:         <0-10> | <one-line justification>

OVERALL: <(3*TRIAGE_ACCURACY + 2*CONTEXT_AWARENESS + 2*ACTION_QUALITY + SKIP_JUSTIFICATION + THREAD_COMPREHENSION + COMPLETENESS + CONCISENESS) / 11, rounded to 1 decimal>

PASS: <YES if OVERALL >= 7.0 AND no dimension below 4, otherwise NO>

ISSUES:
- <specific issue 1 — what is wrong and how to fix it>
- <specific issue 2>
(omit if PASS is YES)
```

Do NOT explain your reasoning beyond the one-line justifications. Do NOT suggest improvements beyond the ISSUES list.
