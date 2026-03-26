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
  - AskUserQuestion
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

8. **Save transcript for eval** (with basic secret redaction):
   ```bash
   perl -pe '
     s/(api[_-]?key\s*[:=]\s*)\S{10,}/${1}REDACTED/gi;
     s/(token\s*[:=]\s*)\S{10,}/${1}REDACTED/gi;
     s/(secret\s*[:=]\s*)\S{8,}/${1}REDACTED/gi;
     s/(password\s*[:=]\s*)\S{4,}/${1}REDACTED/gi;
   ' /tmp/handoff-transcript.md > ".claude/handoffs/${FILENAME%.md}.transcript.md"
   ```
   This builds a corpus of real session transcripts automatically. The eval harness discovers these alongside curated fixtures. The filename is derived from `${FILENAME}` to keep handoff and transcript deterministically linked.

### Phase 4: Present Diagnostics

Display the handoff summary:

```
Handoff written to .claude/handoffs/<FILENAME>
  Sections: <N> decisions, <N> do-not-retry, <N> constraints, <N> next steps, <N> key files
  Token estimate: ~<N>
```

### Phase 5: Kickoff Prompt

Generate a ready-to-use kickoff prompt that the fresh session receives as its first user message. The handoff document provides context (system prompt); the kickoff prompt provides action instructions.

1. **Auto-detect** from the extracted handoff and project:
   - Plan/spec file paths (from Key Files — files in `plans/`, `specs/`, `designs/` dirs or with plan/spec/design in the name)
   - Test commands (from CLAUDE.md, `package.json`, or transcript references to pytest/jest/vitest/cargo test)
   - Task structure from Next Steps (total count, completed, dependencies, parallelizable groups)
   - Branch name and remote tracking status

2. **Ask the user** for execution requirements:
   > "What are your requirements for the build session? Examples: 'full effort, end with a PR', 'use sonnet for simple tasks', 'parallel where safe', 'deploy after'. Or 'default' for standard settings (subagent-driven + tests + PR)."

   If the user says "default", "none", or skips: use subagent-driven development + run tests + create PR.

3. **Read the kickoff template** from `prompts/kickoff.md` in the skill directory.

4. **Generate the kickoff prompt** by combining auto-detected context with user requirements. Follow the template structure and rules.

5. **Write the kickoff prompt** to two locations:

   a. **Companion file** for the auto-launch command:
      ```bash
      KICKOFF_FILE=".claude/handoffs/${FILENAME%.md}.kickoff"
      ```
      Write the raw kickoff prompt text (no markdown fencing) to this file.

   b. **Append to the handoff file** as a final section:
      ````markdown
      ## Kickoff Prompt

      > Paste this as your first message in the fresh session, or use the auto-launch command below.

      ```
      <generated kickoff prompt>
      ```
      ````

### Phase 6: Knowledge Routing

If convention detection found any suggestions:

**For CLAUDE.md additions:**
Present each suggestion individually. For each one, ask the user:
"Suggested CLAUDE.md addition: `<convention>` — Apply? [y/n/edit]"
- If y: append to CLAUDE.md
- If edit: let the user modify the text inline, then append the modified version
- If n: skip

**For memory updates:**
Write any identified user preferences as memory updates (use the memory system directly).

### Phase 7: Launch Instructions

After all knowledge routing is complete, offer to auto-launch the build session in a new terminal window.

1. **Detect terminal environment:**
   ```bash
   echo "TMUX=${TMUX:-}" "TERM_PROGRAM=${TERM_PROGRAM:-}"
   ```

2. **Determine launch method** using this priority cascade:

   | Check | Terminal | Method |
   |-------|----------|--------|
   | `$TMUX` is set | tmux | `tmux new-window` |
   | `$TERM_PROGRAM` = `iTerm.app` | iTerm2 | AppleScript via `osascript` |
   | `$TERM_PROGRAM` = `Apple_Terminal` | Terminal.app | AppleScript via `osascript` |
   | `$TERM_PROGRAM` = `kitty` | Kitty | `kitty @ launch` (requires remote control enabled) |
   | `$TERM_PROGRAM` = `Alacritty` | Alacritty | `alacritty msg create-window` |
   | anything else | — | Manual fallback |

3. **Offer auto-launch** (if a supported terminal was detected):

   > Ready to launch the build session in a new <terminal> window. This will:
   > - Open a new window/tab
   > - Start Claude with the handoff context as system prompt
   > - Send the kickoff prompt as the first message
   >
   > Auto-launch? [y/n]

   If **yes**, run the appropriate command:

   **tmux:**
   ```bash
   KICKOFF_FILE=".claude/handoffs/${FILENAME%.md}.kickoff"
   tmux new-window -n "handoff-${SLUG}" \
     "cd $(pwd) && claude --append-system-prompt-file .claude/handoffs/${FILENAME} \"\$(cat ${KICKOFF_FILE})\""
   ```

   **iTerm2:**
   ```bash
   KICKOFF_FILE=".claude/handoffs/${FILENAME%.md}.kickoff"
   CMD="cd $(pwd) && claude --append-system-prompt-file .claude/handoffs/${FILENAME} \"\$(cat ${KICKOFF_FILE})\""
   osascript \
     -e 'tell application "iTerm" to tell current window to create tab with default profile' \
     -e "tell application \"iTerm\" to tell current session of current window to write text \"${CMD}\""
   ```

   **Terminal.app:**
   ```bash
   KICKOFF_FILE=".claude/handoffs/${FILENAME%.md}.kickoff"
   CMD="cd $(pwd) && claude --append-system-prompt-file .claude/handoffs/${FILENAME} \"\$(cat ${KICKOFF_FILE})\""
   osascript -e "tell application \"Terminal\" to do script \"${CMD}\""
   ```

   **Kitty:**
   ```bash
   KICKOFF_FILE=".claude/handoffs/${FILENAME%.md}.kickoff"
   kitty @ launch --type=tab --cwd=$(pwd) \
     claude --append-system-prompt-file .claude/handoffs/${FILENAME} "$(cat ${KICKOFF_FILE})"
   ```

   **Alacritty:**
   ```bash
   KICKOFF_FILE=".claude/handoffs/${FILENAME%.md}.kickoff"
   alacritty msg create-window --working-directory $(pwd) \
     -e claude --append-system-prompt-file .claude/handoffs/${FILENAME} "$(cat ${KICKOFF_FILE})"
   ```

   Then confirm:
   ```
   Launched in <terminal>. The build session is running with full handoff context.
   ```

   If **no**, fall through to manual instructions below.

4. **Manual fallback** (unsupported terminal, user declined, or launch failed):

   ```
   To start the build session:
     claude --append-system-prompt-file .claude/handoffs/<FILENAME>

   Then paste this kickoff prompt:
     <show contents of .kickoff file>

   Or as a single command:
     claude --append-system-prompt-file .claude/handoffs/<FILENAME> "$(cat .claude/handoffs/<FILENAME%.md>.kickoff)"
   ```

### Cleanup

Remove temporary files:
```bash
rm -f /tmp/handoff-transcript.md
```

Note: Do NOT remove the `.kickoff` companion file — it is needed if the user launches later.

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
