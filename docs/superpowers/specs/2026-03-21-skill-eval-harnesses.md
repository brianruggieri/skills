# Skill Eval Harness Adaptations

> How to apply the handoff blind-eval + ralph-loop pattern to fix-pr-reviews, grill-me, and scope-repo.

## The Handoff Pattern (Reference)

The handoff eval works because the skill is a **single-pass extraction**: transcript in → handoff document out. The pattern:

1. **Fixtures** — diverse synthetic transcripts covering edge cases
2. **Blind extraction** — agent reads prompt + fixture, produces output
3. **Blind grading** — agent reads rubric + fixture + output, produces scorecard
4. **Ralph loop** — iterate on prompt until all fixtures pass (≥7.0 overall, no dim <4)

This pattern transfers directly to any skill component that takes structured input and produces structured output in one pass. For interactive or multi-agent skills, we need modified patterns.

---

## Three Modified Patterns

### Pattern A: Single-Pass Extraction (same as handoff)

**Works for:** Any skill phase where input → structured output in one pass.

```
fixture (input) → blind agent (reads prompt) → output → blind grader (reads rubric) → scorecard
```

**Ralph loop target:** The prompt being evaluated.

### Pattern B: Simulated Conversation

**Works for:** Interactive skills where quality depends on the conversation arc, not a single output.

```
fixture (plan + planted weaknesses + respondent script)
  → blind interviewer agent (reads skill prompt + plan)
  → respondent agent (reads script, plays user role)
  → full transcript
  → blind grader (reads rubric + plan + transcript + answer key)
  → scorecard
```

The key innovation: a **respondent agent** that plays the user role from a scripted fixture. The fixture includes:
- The plan/design to discuss
- Planted weaknesses the interviewer should find
- A respondent script defining how to answer (vague on topic X, confident on Y, say "idk" on Z)
- An answer key listing what a perfect interviewer would discover

**Ralph loop target:** The skill's questioning logic and protocols.

### Pattern C: Component Isolation

**Works for:** Multi-agent skills where end-to-end eval is impractical but individual phases produce graded output.

```
Phase 1 fixture (repo snapshot) → blind analyst agent → briefing → blind grader → scorecard
Phase 2 fixture (briefings + decisions) → blind lead agent → ROADMAP.md → blind grader → scorecard
```

Each phase gets its own eval pipeline with its own fixtures and rubric. Phases are tested independently — you don't need to run a full multi-agent pipeline to test whether the ROADMAP template produces good output.

**Ralph loop target:** Individual phase prompts (analyst prompt, interview protocol, ROADMAP template).

---

## Skill-by-Skill Analysis

### 1. fix-pr-reviews

**Skill nature:** Multi-phase, external-dependent (GitHub API), code-modifying.

**Evaluable components:**

| Component | Pattern | Feasibility | Impact |
|-----------|---------|-------------|--------|
| Comment triage (Phase 2) | A — Single-Pass | High | High |
| Fix plan generation | A — Single-Pass | Medium | High |
| Commit message quality | A — Single-Pass | High | Low |
| Thread resolution logic | Not evaluable offline | — | — |

**Recommended: Triage Eval (Pattern A)**

The highest-leverage target is Phase 2 comment categorization. The skill's value hinges on correctly distinguishing critical bugs from style nits. Wrong triage = wrong priority = wasted effort or missed bugs.

**Fixture format:**
```markdown
# PR Context
Title: {title}
Description: {description}
Files changed: {list}

# Review Comments
## Comment 1
Reviewer: {username}
File: {path}
Line: {line}
Body: {comment text}
In reply to: {id or null}

## Comment 2
...

# Source Context
## {path}:{line range}
```{language}
{relevant source code}
```
```

**What the extraction produces:** Categorized comment list with:
- Priority (critical / important / style / informational)
- Planned action (fix, skip with reason, respond only)
- Rationale for categorization

**Grading dimensions:**

| Dimension | Weight | What it measures |
|-----------|--------|-----------------|
| TRIAGE_ACCURACY | 3x | Correct priority assignment — critical bugs not missed, style not over-promoted |
| CONTEXT_AWARENESS | 2x | Did it read source code before categorizing? Does rationale reference actual code? |
| ACTION_QUALITY | 2x | Is the planned action appropriate? Minimal fix, not over-fix? |
| SKIP_JUSTIFICATION | 1x | When skipping a comment, is the reason valid and well-explained? |
| THREAD_COMPREHENSION | 1x | For threaded discussions, did it understand the resolution? |
| COMPLETENESS | 1x | All comments addressed, none dropped |
| CONCISENESS | 1x | Triage output is structured and scannable, not prose |

**Fixture diversity needed:**
- `simple-style-nits.md` — All style comments, nothing critical (tests: doesn't over-promote)
- `hidden-security-bug.md` — Security issue buried in a polite suggestion (tests: catches critical even when phrased softly)
- `conflicting-reviewers.md` — Two reviewers disagree on approach (tests: handles conflict)
- `threaded-resolution.md` — Comment thread where issue was already discussed and resolved (tests: reads full thread)
- `copilot-noise.md` — Mix of Copilot auto-review + human review (tests: filters noise from signal)

**Ralph loop target:** The categorization heuristics in `fix-pr-reviews/SKILL.md` Phase 2, or a new extracted `fix-pr-reviews/prompts/triage.md` prompt.

---

### 2. grill-me

**Skill nature:** Interactive, conversational. Quality depends on the full arc: risk tree → questions → follow-ups → resolution.

**Evaluable components:**

| Component | Pattern | Feasibility | Impact |
|-----------|---------|-------------|--------|
| Risk tree construction | A — Single-Pass | High | High |
| Question quality | B — Simulated Conversation | Medium | Very High |
| Follow-up discipline | B — Simulated Conversation | Medium | Very High |
| "I don't know" protocol | B — Simulated Conversation | Medium | High |
| Decision log quality | A — Single-Pass | High | Medium |

**Recommended: Two-tier eval**

**Tier 1 — Risk Tree Eval (Pattern A)**

Cheapest to build. Given a plan, does the skill produce a well-ordered risk tree?

**Fixture format:**
```markdown
# Plan: {title}

## Overview
{description of what's being built}

## Architecture
{technical design}

## Known Weaknesses (ANSWER KEY — grader only)
1. {weakness} — complexity: {high/medium}, risk: {high/medium/low}
2. {weakness} — ...
```

**What the extraction produces:** The risk tree from Phase 1.

**Grading dimensions:**

| Dimension | Weight | What it measures |
|-----------|--------|-----------------|
| COVERAGE | 3x | Did it identify all planted weaknesses? (precision + recall against answer key) |
| ORDERING | 2x | Complexity-first, then risk — per the skill's own rules |
| SPECIFICITY | 2x | Branches reference real architectural concerns, not generic platitudes |
| GRANULARITY | 1x | Sub-branches where needed, not just top-level bullets |
| NO_SOFTBALLS | 1x | No branches that are already answered by the plan itself |

**Tier 2 — Conversation Eval (Pattern B)**

More expensive but tests the core value: does it actually find weaknesses through questioning?

**Fixture format:**
```markdown
# Plan
{the plan to grill}

# Respondent Script
When asked about {topic A}: give vague answer ("we'll figure it out")
When asked about {topic B}: give confident, correct answer
When asked about {topic C}: say "I don't know"
When asked about {topic D}: give a wrong answer that contradicts the codebase
Default: give reasonable, specific answers

# Answer Key
The interviewer should:
1. Follow up on {topic A} vagueness at least 2x
2. Accept {topic B} and move on
3. Dispatch research on {topic C}
4. Catch the contradiction on {topic D} by reading code
```

**Orchestration:**
1. Blind interviewer agent reads `grill-me/SKILL.md` + the plan section of the fixture
2. Respondent agent reads the respondent script + plan, plays the user via `AskUserQuestion` simulation
3. The two agents exchange messages until the interviewer closes the session (or hits a turn limit)
4. Full transcript is captured
5. Blind grader reads rubric + answer key + transcript, produces scorecard

**Implementation note:** The respondent agent can't literally answer `AskUserQuestion` calls. Instead, the orchestrator mediates: interviewer writes its question, orchestrator feeds it to respondent, respondent writes answer, orchestrator feeds it back. This is a **turn-based simulation loop**.

**Grading dimensions:**

| Dimension | Weight | What it measures |
|-----------|--------|-----------------|
| WEAKNESS_DISCOVERY | 3x | Did it find all planted weaknesses? (against answer key) |
| FOLLOW_UP_DISCIPLINE | 2x | Pursued vague answers, didn't accept "we'll figure it out" |
| IDK_PROTOCOL | 2x | Dispatched research on "I don't know" responses |
| CONTRADICTION_CATCH | 2x | Caught wrong answers by reading code |
| ONE_QUESTION_RULE | 1x | One question per turn, no batching |
| RISK_TREE_UPDATE | 1x | Added new branches discovered during conversation |
| NO_SOFTBALLS | 1x | Questions attack weaknesses, not strengths |

**Ralph loop target:** The questioning rules, ambiguity protocol, and "idk" protocol in `grill-me/SKILL.md`.

**Fixture diversity needed:**
- `clean-plan.md` — Well-thought-out plan with 1-2 subtle weaknesses (tests: finds subtle issues)
- `swiss-cheese-plan.md` — Plan full of holes, vague on everything (tests: prioritizes and doesn't get stuck)
- `defensive-user.md` — Respondent pushes back, deflects, gets frustrated (tests: stays on thread)
- `idk-heavy.md` — Respondent says "I don't know" on 3+ topics (tests: research dispatch works)

---

### 3. scope-repo

**Skill nature:** Multi-agent, requires codebase access, long-running. End-to-end eval is impractical.

**Evaluable components:**

| Component | Pattern | Feasibility | Impact |
|-----------|---------|-------------|--------|
| Analyst briefing quality | C — Component Isolation | Medium | High |
| Interview question quality | C — Component Isolation | Medium | High |
| ROADMAP.md generation | A — Single-Pass | High | Very High |
| Work item decomposition | A — Single-Pass | High | High |
| Scope validation | Not worth isolating | — | Low |

**Recommended: ROADMAP Eval (Pattern A) + Briefing Eval (Pattern C)**

**Tier 1 — ROADMAP Eval (Pattern A)**

Highest leverage, most feasible. Given pre-written briefings + interview decisions, does the lead produce a good ROADMAP.md?

**Fixture format:**
```markdown
# Repo Context
Name: {name}
Description: {what it does}

# Briefings

## Architecture Briefing
{pre-written analyst briefing following the prescribed format}

## Quality Briefing
{pre-written analyst briefing}

## Developer Experience Briefing
{pre-written analyst briefing}

## Tech Debt Briefing
{pre-written analyst briefing}

# Interview Decisions
- Priority 1: {what the user said matters most}
- Priority 2: {second priority}
- Design decision: {resolved decision with rationale}
- Deferred: {what user said "not now" to}

# Work Items (co-created during interview)
- WI-01: {title} — scope: {files}, depends: nothing
- WI-02: {title} — scope: {files}, depends: WI-01
- WI-03: {title} — scope: {files}, depends: nothing
```

**What the extraction produces:** ROADMAP.md in the prescribed format.

**Grading dimensions:**

| Dimension | Weight | What it measures |
|-----------|--------|-----------------|
| STRUCTURE | 2x | All required sections, correct format, self-contained |
| BRIEFING_SYNTHESIS | 2x | Filtered briefing content by relevance to stated goals, not raw dump |
| WORK_ITEM_QUALITY | 3x | Scope specific, success criteria measurable, dependencies correct |
| WAVE_SEQUENCING | 2x | Execution waves respect dependencies and make logical sense |
| DECISION_CAPTURE | 1x | Resolved decisions include context, chosen option, and rejected alternatives |
| KICKOFF_READINESS | 1x | Could a fresh session execute from this ROADMAP alone? |
| FAITHFULNESS | 2x | No fabricated findings, decisions, or work items — everything traceable to fixture |

**Tier 2 — Analyst Briefing Eval (Pattern C)**

Tests whether individual analyst prompts produce good briefings when pointed at a codebase.

**Fixture format:** A small, self-contained repo snapshot (or a real public repo) with known characteristics. The answer key lists what the analyst should find.

This is harder to fixture because it requires actual code to analyze. Two approaches:
1. **Snapshot approach:** Include a directory tree + key file contents in the fixture markdown
2. **Live repo approach:** Point at a known public repo (e.g., a small well-understood OSS project)

The snapshot approach is self-contained and deterministic. The live repo approach tests real-world behavior but can't be graded against a fixed answer key.

**Recommended:** Start with snapshot approach for determinism, add live repo fixtures later for regression testing.

**Ralph loop target:** The analyst prompt templates (currently embedded in `scope-repo/SKILL.md` — would need extraction to `scope-repo/prompts/` for iteration).

---

## Implementation Priority

| Priority | Skill | Eval Type | Why First |
|----------|-------|-----------|-----------|
| 1 | fix-pr-reviews | Triage Eval (Pattern A) | Closest to handoff pattern, highest confidence we can build it quickly |
| 2 | grill-me | Risk Tree Eval (Pattern A) | Tier 1 is cheap, validates the approach before investing in conversation sim |
| 3 | scope-repo | ROADMAP Eval (Pattern A) | Pattern A tier is straightforward, most value per effort |
| 4 | grill-me | Conversation Eval (Pattern B) | Novel pattern, highest complexity, but also highest potential value |
| 5 | scope-repo | Briefing Eval (Pattern C) | Requires repo snapshots, most fixture authoring effort |

## Shared Infrastructure

All eval harnesses reuse:
- **`run-ralph.sh` pattern** — parameterized per skill (copy + adapt, not a shared script)
- **Blind agent dispatch** — same orchestration flow as handoff
- **Scorecard format** — weighted dimensions, OVERALL formula, PASS/FAIL gate
- **Directory structure:**
  ```
  {skill}/
    eval/
      SKILL.md          # /eval-{name} orchestrator
      RALPH-PROMPT.md   # ralph-loop refinement prompt
      prompts/
        grade.md        # grading rubric
      run-ralph.sh      # bash harness
    tests/
      fixtures/         # diverse test fixtures
      output/
        eval/           # extraction + scorecard results
  ```

## Prompt Extraction Prerequisite

For `grill-me` and `scope-repo`, the refinable prompt logic is currently embedded in `SKILL.md` rather than extracted to `prompts/`. The ralph loop needs an isolated file to iterate on. Before building eval harnesses:

1. **grill-me:** Extract questioning rules, ambiguity protocol, and "idk" protocol to `grill-me/prompts/interview.md`
2. **scope-repo:** Extract analyst startup prompts to `scope-repo/prompts/analyst-{type}.md` and ROADMAP template to `scope-repo/prompts/roadmap.md`
3. **fix-pr-reviews:** Extract Phase 2 categorization logic to `fix-pr-reviews/prompts/triage.md`

This separation (orchestration in SKILL.md, refinable logic in prompts/) is the same pattern handoff uses and is what makes blind eval + ralph loop work.

## Open Questions

1. **Conversation simulation fidelity (Pattern B):** Can a turn-based orchestrator faithfully simulate the `AskUserQuestion` interaction? The grill-me skill expects to control the conversation — the respondent agent needs to be passive and reactive.

2. **Fixture authoring cost:** Grill-me and scope-repo fixtures are more complex than handoff transcripts. Should we invest in fixture generators (agents that create diverse fixtures from templates)?

3. **Cross-skill regression:** When we ralph-loop one skill's prompt, could changes inadvertently affect shared patterns? Each skill is independent, so this shouldn't happen — but worth monitoring.

4. **Minimum fixture count:** Handoff uses 4 fixtures. Is that enough for skills with more behavioral surface area? Grill-me conversation eval may need 6+ to cover the interaction matrix.
