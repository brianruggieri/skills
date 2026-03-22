---
name: handoff
description: Extract structured context from a planning session and generate a handoff document for a fresh build session. Captures decisions, negative knowledge, constraints, and next steps. Use when a planning session is complete and you want to start building in a clean context window.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
---

# Handoff

Generate a structured handoff document from the current planning session, capturing decisions, failed approaches, constraints, and next steps for a fresh build session.

## Process

### Phase 1: Locate & Preprocess

Run the preprocessor to extract conversation text from the session JSONL.

First locate the preprocessor script. It lives alongside this SKILL.md:
```bash
# The skill directory is where SKILL.md lives — use Glob to find it
# Then run the preprocessor from scripts/ within that directory
python3 <skill-dir>/scripts/preprocess.py --output /tmp/handoff-transcript.md
```

To find the skill directory, use Glob for `**/handoff/scripts/preprocess.py` scoped to common locations (`~/git`, `~/.claude`). Cache the path for the rest of this invocation.

If the preprocessor cannot find the session JSONL, ask the user to provide the path:
"I couldn't auto-detect the session file. Can you provide the path? Check `~/.claude/projects/` for .jsonl files."

### Phase 2: Extract

1. Read the preprocessed transcript from `/tmp/handoff-transcript.md`
2. Read the extraction prompt from the skill's `prompts/extract.md` file
3. Apply the extraction prompt to the transcript to produce the handoff sections
4. Read the convention detection prompt from `prompts/conventions.md`
5. Read the project's CLAUDE.md (if it exists) for dedup checking
6. Apply the convention prompt to identify durable knowledge

### Phase 3: Assemble & Write

1. **Derive the slug** from the current git branch:
   ```bash
   git branch --show-current | sed 's|.*/||' | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g' | sed 's/-\+/-/g' | sed 's/^-\|-$//g'
   ```
   If on main/master, use the session slug from the preprocessor output instead.

2. **Build the filename:**
   ```
   TIMESTAMP=$(date -u +"%Y%m%d-%H%M%S")
   FILENAME="${TIMESTAMP}-${SLUG}.md"
   ```

3. **Assemble the handoff document** with this header:
   ```markdown
   # Handoff: <slug>
   > Generated: <ISO timestamp> | Session: <session_id> | Branch: <branch>
   ```
   Followed by the six extracted sections (Summary, Decisions, Do Not Retry, Constraints, Next Steps, Key Files).

4. **Write the handoff file:**
   ```bash
   mkdir -p .claude/handoffs
   ```
   Write the assembled markdown to `.claude/handoffs/${FILENAME}`.

5. **Update the latest symlink:**
   ```bash
   ln -sf "${FILENAME}" .claude/handoffs/latest.md
   ```

6. **Log the generation event:**
   Append one JSON line to `.claude/handoffs/log.jsonl`:
   ```json
   {"ts":"<ISO>","file":"<FILENAME>","tokens":<estimated>,"sections":{"decisions":<N>,"doNotRetry":<N>,"constraints":<N>,"nextSteps":<N>},"conventions":<N>,"sessionDuration":"<Nm>"}
   ```

7. **Add to .gitignore** if not already present:
   ```bash
   grep -q '.claude/handoffs/' .gitignore 2>/dev/null || echo '.claude/handoffs/' >> .gitignore
   ```

8. **Save transcript for eval:**
   ```bash
   cp /tmp/handoff-transcript.md ".claude/handoffs/${TIMESTAMP}-${SLUG}.transcript.md"
   ```
   This builds a corpus of real session transcripts automatically. The eval harness discovers these alongside curated fixtures.

### Phase 4: Present Diagnostics

Display the handoff summary:

```
Handoff written to .claude/handoffs/<FILENAME>
  Sections: <N> decisions, <N> do-not-retry, <N> constraints, <N> next steps, <N> key files
  Token estimate: ~<N>
```

### Phase 5: Knowledge Routing

If convention detection found any suggestions:

**For CLAUDE.md additions:**
Present each suggestion individually. For each one, ask the user:
"Suggested CLAUDE.md addition: `<convention>` — Apply? [y/n/edit]"
- If y: append to CLAUDE.md
- If edit: let the user modify the text inline, then append the modified version
- If n: skip

**For memory updates:**
Write any identified user preferences as memory updates (use the memory system directly).

### Phase 6: Launch Instructions

After all knowledge routing is complete, present the launch command:

```
To start the build session:
  claude --append-system-prompt-file .claude/handoffs/<FILENAME>

Or in a new tmux window:
  tmux new-window "claude --append-system-prompt-file .claude/handoffs/<FILENAME>"
```

If `--append-system-prompt-file` is not available, fall back to:
```
  claude --append-system-prompt "$(cat .claude/handoffs/<FILENAME>)"
```

### Cleanup

Remove the temporary transcript file:
```bash
rm -f /tmp/handoff-transcript.md
```

## Edge Cases

### No plan detected
If the transcript doesn't contain a clear plan or set of decisions, still generate the handoff with whatever is available. Write "Session ended without a defined plan" in the Next Steps section. The handoff is still valuable for capturing any decisions, constraints, or negative knowledge.

### Very short session
If the preprocessed transcript is under 500 characters, warn the user:
"This session is very short. The handoff may not contain enough context to be useful. Generate anyway? [y/n]"

### CLAUDE.md doesn't exist
Skip the dedup check in convention detection. If the user approves any conventions, create CLAUDE.md with those entries.

### Session on main/master branch
Use the session slug (from the preprocessor output) instead of the branch name for the handoff filename.

## Anti-patterns — do NOT do these

- Summarizing the entire session instead of extracting specific categories
- Including full file contents in the handoff (paths + annotations only)
- Including git diffs (branch + file list is sufficient)
- Including API keys, passwords, or secrets in any output
- Auto-launching a new session without the user's explicit action
- Modifying CLAUDE.md without the user's approval per item
- Generating a handoff from a build/implementation session (this is for planning sessions)
- Fabricating decisions or constraints not explicitly discussed in the transcript
