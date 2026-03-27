---
name: ghostwrite
description: Write text in the user's authentic voice using a quantitative voice profile built from their session logs. Two modes — build a profile from scratch, or write using an existing one. Use when asked to "ghostwrite", "write in my voice", "draft something that sounds like me", or "build my voice profile".
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Agent
  - AskUserQuestion
---

# Ghostwrite

Write text in the user's authentic voice. Two modes: **build** a voice profile from session logs, or **write** using an existing profile.

## Mode Detection

When invoked, check for an existing voice profile:

1. Check project memory: `<project>/.claude/*/memory/voice_profile*.md`
2. Check home: `~/.claude/voice-profile.md`

If found, enter **Write Mode**. If not found, enter **Build Mode**.

The user can also explicitly request a mode:
- "build my voice profile" / "update my voice" / "analyze my voice" → Build Mode
- "write in my voice" / "draft this as me" → Write Mode (error if no profile exists)

---

## Build Mode

Build a quantitative voice profile from the user's Claude Code session logs.

### Phase 1: Extract

Run the corpus extraction script bundled with this skill.

Find the script path by searching for `write-voice/scripts/extract-corpus.py` in common locations (`~/git/skills`, `~/.claude/skills`). Then run:

```bash
python3 <skill-dir>/scripts/extract-corpus.py --output /tmp/voice-corpus.txt --stats
```

If the script reports fewer than 50 prompts, warn the user:
> "Only found N prompts. The profile will be thin. You can improve it by using Claude Code more and rebuilding later."

If fewer than 10, abort:
> "Not enough data to build a meaningful profile. Need at least 10 organic prompts across your session history."

### Phase 2: Analyze

Read `/tmp/voice-corpus.txt`. Analyze the FULL corpus across these dimensions:

1. **Sentence structure** — fragment frequency, average length, how ideas connect (commas vs periods vs nothing), first-word patterns
2. **Punctuation** — terminal punctuation frequency (period/question/exclamation/none), comma patterns, what they NEVER use
3. **Capitalization** — sentence-start caps frequency, proper noun handling, pronoun capitalization
4. **Vocabulary** — top 20 distinctive words/phrases (not stop words), words they never use, technical vocabulary patterns
5. **Tone modes** — identify 2-4 distinct registers (directive, thinking, feedback, etc.) with example quotes
6. **Conversational patterns** — how they approve, reject, ask questions, express uncertainty, express frustration
7. **Signature phrases** — recurring phrases that are distinctively theirs, with counts
8. **Anti-patterns** — things that would sound WRONG in their voice (equally important as positive patterns)
9. **Formality spectrum** — examples from most casual to most formal, with context for when each appears

Every claim must be supported by a specific quote from the corpus. This is evidence-based, not impressionistic.

### Phase 3: Write Profile

Write the profile to `~/.claude/voice-profile.md` with this structure:

```markdown
# Voice Profile

**Version:** <version>
**Generated:** <date>
**Corpus:** <prompt count> prompts from <file count> sessions
**Method:** Full extraction from Claude Code session logs

## Writing DNA
<3-4 sentence summary that would let someone identify this writer in a blind test>

## Key Stats
<quantitative markers: capitalization %, punctuation %, fragment %, median length>

## Sentence Structure
<patterns with examples>

## Signature Phrases
<table: phrase, count, context>

## Tone Modes
<2-4 modes with examples>

## Anti-Patterns
<things that sound WRONG — this section teaches models more than positive patterns>

## Formality for Applications
<specific guidance for formal-ish contexts: what to preserve, what to adjust>

## Version History
<changelog of profile versions>
```

### Phase 4: Index

If the current project has a memory directory with MEMORY.md, add a pointer:
```
- [voice_profile.md](voice_profile.md) — vN.N voice profile from N prompts. Use for writing in user's voice.
```

Also copy or symlink the profile into the project memory if it was written to `~/.claude/`.

Tell the user:
> "Voice profile v<N> saved. <prompt count> prompts analyzed. Invoke `/write-voice` with a writing task to use it."

---

## Write Mode

Generate text in the user's voice using the loaded profile.

### Step 1: Load Profile

Read the voice profile. Internalize:
- The Writing DNA summary (overall feel)
- Anti-patterns (what to avoid — prioritize this)
- Signature phrases (use sparingly, not in every sentence)
- Sentence structure patterns (fragment frequency, comma-chaining, length)
- Capitalization and punctuation habits
- The formality guidance for the target context

### Step 2: Understand the Task

Ask the user (if not already specified):
> "What should I write? Give me the topic, the audience, the format (application answer, blog post, email, etc.), and roughly how long."

### Step 3: Draft

Write the text. Rules:

- **Anti-patterns are hard constraints.** If the profile says "never uses semicolons," there are zero semicolons. If it says "never starts with 'I am excited to,'" that phrase does not appear.
- **Sentence structure matches the profile's stats.** If 88% of prompts are fragments, the output should be fragment-heavy. If median length is 19 words, sentences should cluster short.
- **Signature phrases appear naturally**, not forced. Use 1-2 per paragraph at most. They should feel like they belong, not like they were inserted for authenticity.
- **Tone mode matches the context.** An application answer uses the "design thinking" register, not the "directive" register. A Slack message uses "directive."
- **Do NOT perform the voice.** The goal is not to sound like a caricature. The goal is to sound like the person writing naturally in the given context. When in doubt, err toward their "design thinking" mode — that's where they're most articulate while still being themselves.
- **No em dashes** unless the profile explicitly shows them as a pattern.
- **Contractions always** unless the profile says otherwise.

### Step 4: Present and Iterate

Show the draft. Ask:
> "Does this sound like you? What's off?"

If the user gives feedback:
1. Revise the draft
2. Note the feedback for potential profile updates
3. If the feedback reveals a pattern not in the profile, offer to update it:
   > "You mentioned [X]. Should I add that to your voice profile for next time?"

### Step 5: Profile Refinement (optional)

If the user approved text that differs from what the profile would predict, or if they gave feedback that reveals new patterns:

1. Read the current profile
2. Add the new pattern or adjust existing ones
3. Bump the minor version (e.g., v1.0 → v1.1)
4. Add to Version History: "v1.1 (<date>): Added [pattern] based on validated output in [context]"

Approved output becomes ground truth. Text the user confirmed as "sounds like me" is more authoritative than corpus statistics.

---

## Anti-patterns — do NOT do these

- Writing a caricature of the user's casual voice when the context is formal
- Inserting every signature phrase into a single paragraph
- Ignoring the anti-patterns list (this is the highest-value section)
- Using the profile's casual-mode patterns in a professional context without adjusting
- Refusing to write because the profile seems "too informal" for the task
- Over-explaining which patterns you applied (the user doesn't need a meta-commentary)
- Generating text and then adding a disclaimer about how it "may not perfectly capture" their voice
- Using em dashes as a default connector (common AI habit, usually flagged in profiles)

---

## Rebuilding / Updating

When the user asks to "update my voice profile" or "rebuild voice":

1. Re-run the extraction script (captures new sessions since last build)
2. Re-analyze the full corpus
3. Bump the major version (v1.x → v2.0)
4. Preserve any manually-added patterns from Step 5 refinements (marked in Version History)
5. Diff against the previous version and report what changed:
   > "v2.0 changes: capitalization rate shifted from 27% to 31%, new signature phrase 'ship it' appeared 15 times, removed 'please advise' (dropped from 136 to 8 uses)."
