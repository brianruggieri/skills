# Handoff Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `/handoff` Claude Code skill that extracts structured context from a planning session's transcript and writes a handoff document for a fresh build session.

**Architecture:** A skill (SKILL.md) orchestrates six phases: (1) Python preprocessor strips noise from session JSONL, (2) Claude reads condensed transcript and applies extraction prompts from `prompts/`, (3) assembles and writes handoff document, (4) presents diagnostics, (5) routes durable knowledge to CLAUDE.md/memory with user approval, (6) presents launch instructions. Extraction prompts live in separate files for ralph-loop iteration.

**Tech Stack:** Python 3 (preprocessor), Markdown (skill + prompts), Claude Code skill system

**Spec:** `docs/superpowers/specs/2026-03-21-handoff-skill-design.md`

---

## File Structure

```
handoff/
  SKILL.md                      ← Orchestration: phases 1-5, knowledge routing, UX
  prompts/
    extract.md                  ← Extraction prompt for handoff document (ralph-loop target)
    conventions.md              ← Convention/preference detection (ralph-loop target)
  scripts/
    preprocess.py               ← JSONL preprocessor: locate, filter, truncate, output
```

Each file has one clear responsibility:
- `SKILL.md`: Knows the workflow (what to do in what order). Does NOT contain extraction logic.
- `prompts/extract.md`: Knows what to extract and how to format it. Does NOT know about preprocessing or file paths.
- `prompts/conventions.md`: Knows how to identify durable knowledge. Does NOT know about the handoff document.
- `scripts/preprocess.py`: Knows the JSONL schema and how to filter/truncate. Does NOT know what Claude will do with the output.

---

### Task 1: Create the JSONL Preprocessor

**Files:**
- Create: `handoff/scripts/preprocess.py`

This is the foundation — everything else depends on it producing clean output.

- [ ] **Step 1: Write the session file discovery function**

```python
#!/usr/bin/env python3
"""
Preprocess a Claude Code session JSONL for handoff extraction.

Locates the current session's JSONL, extracts conversation text and thinking
blocks, strips noise (progress, tool_results, system entries), enforces size
budget, and writes condensed output.

Usage: python3 preprocess.py [--output /path/to/output.md]
       Prints to stdout if --output is not specified.
"""

import json
import os
import sys
import glob
import subprocess
from pathlib import Path


def find_session_jsonl() -> str:
    """Find the current session's JSONL file.

    Discovery order:
    1. Git root path, encoded (/ and . replaced with -)
    2. $PWD encoded (if different from git root)
    3. Emergency: most recently modified JSONL across all projects
    """
    home = Path.home()
    projects_dir = home / ".claude" / "projects"

    if not projects_dir.is_dir():
        die("~/.claude/projects/ not found. Is Claude Code installed?")

    # Try git root first
    git_root = get_git_root()
    if git_root:
        encoded = encode_path(git_root)
        result = find_latest_jsonl(projects_dir / encoded)
        if result:
            return result

    # Try $PWD if different
    cwd = os.getcwd()
    if cwd != git_root:
        encoded = encode_path(cwd)
        result = find_latest_jsonl(projects_dir / encoded)
        if result:
            return result

    # Emergency fallback: most recent JSONL across all project dirs
    import time
    best_path, best_mtime = None, 0
    for proj_dir in projects_dir.iterdir():
        if not proj_dir.is_dir():
            continue
        for f in proj_dir.glob("*.jsonl"):
            if f.is_file() and not f.is_symlink():
                mt = f.stat().st_mtime
                if mt > best_mtime and (time.time() - mt) < 10:
                    best_mtime = mt
                    best_path = str(f)

    if best_path:
        return best_path

    die("Could not find session JSONL. Try running from within a git repository.")


def encode_path(path: str) -> str:
    """Encode a path the way Claude Code does: replace / and . with -"""
    return path.replace("/", "-").replace(".", "-")


def get_git_root() -> str | None:
    """Get the git repository root, or None."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def find_latest_jsonl(project_dir: Path) -> str | None:
    """Find the most recently modified top-level .jsonl in a project dir."""
    if not project_dir.is_dir():
        return None
    best_path, best_mtime = None, 0
    for f in project_dir.glob("*.jsonl"):
        if f.is_file() and not f.is_symlink():
            mt = f.stat().st_mtime
            if mt > best_mtime:
                best_mtime = mt
                best_path = str(f)
    return best_path


def die(msg: str):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)
```

- [ ] **Step 2: Run the script to verify session discovery works**

Run: `cd /Users/brianruggieri/git/skills && python3 handoff/scripts/preprocess.py --help`
Expected: Help text or usage error (script not complete yet, but no import errors)

- [ ] **Step 3: Write the JSONL parsing and content extraction**

Add to `preprocess.py`:

```python
# Size budget constants
MAX_OUTPUT_CHARS = 600_000  # ~150K tokens
MAX_USER_MSG_CHARS = 2000   # Truncate huge user messages
TRUNCATE_KEEP_CHARS = 200   # Keep first/last N chars when truncating


def extract_conversation(jsonl_path: str) -> dict:
    """Parse JSONL and extract conversation text, thinking blocks, and file paths.

    Returns:
        {
            "messages": [{"role": "user"|"assistant", "text": str, "index": int, "timestamp": str}],
            "thinking": [{"text": str, "index": int, "timestamp": str}],
            "file_paths": [str],
            "session_id": str,
            "slug": str,
            "git_branch": str,
            "total_entries": int,
        }
    """
    messages = []
    thinking_blocks = []
    file_paths = set()
    session_id = ""
    slug = ""
    git_branch = ""
    total_entries = 0
    entry_index = 0

    with open(jsonl_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            total_entries += 1
            entry_type = entry.get("type")
            timestamp = entry.get("timestamp", "")

            # Grab metadata from first entry that has it
            if not session_id and entry.get("sessionId"):
                session_id = entry["sessionId"]
            if not slug and entry.get("slug"):
                slug = entry["slug"]
            if not git_branch and entry.get("gitBranch"):
                git_branch = entry["gitBranch"]

            if entry_type == "user":
                text = extract_user_text(entry)
                if text:
                    messages.append({
                        "role": "user",
                        "text": text,
                        "index": entry_index,
                        "timestamp": timestamp,
                    })

            elif entry_type == "assistant":
                content = entry.get("message", {}).get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        btype = block.get("type")
                        if btype == "text" and block.get("text"):
                            messages.append({
                                "role": "assistant",
                                "text": block["text"],
                                "index": entry_index,
                                "timestamp": timestamp,
                            })
                        elif btype == "thinking" and block.get("thinking"):
                            thinking_blocks.append({
                                "text": block["thinking"],
                                "index": entry_index,
                                "timestamp": timestamp,
                            })
                        elif btype == "tool_use":
                            paths = extract_file_paths_from_tool(block)
                            file_paths.update(paths)

            entry_index += 1

    return {
        "messages": messages,
        "thinking": thinking_blocks,
        "file_paths": sorted(file_paths),
        "session_id": session_id,
        "slug": slug,
        "git_branch": git_branch,
        "total_entries": total_entries,
    }


def extract_user_text(entry: dict) -> str:
    """Extract human-written text from a user entry.
    Handles both string content and array content (skips tool_result blocks).
    """
    content = entry.get("message", {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
        return "\n".join(texts)
    return ""


def extract_file_paths_from_tool(block: dict) -> list[str]:
    """Extract file paths from a tool_use block."""
    name = block.get("name", "")
    inp = block.get("input", {})
    paths = []
    if name in ("Read", "Write", "Edit") and inp.get("file_path"):
        paths.append(inp["file_path"])
    elif name == "Glob" and inp.get("pattern"):
        # Record the search directory, not the pattern
        if inp.get("path"):
            paths.append(inp["path"])
    return paths
```

- [ ] **Step 4: Write the recency weighting and size budget enforcement**

Add to `preprocess.py`:

```python
def apply_recency_weighting(data: dict) -> str:
    """Apply recency weighting and size budget, return formatted transcript.

    - Thinking blocks: keep for last 60% of entries, strip for first 40%
    - User messages over MAX_USER_MSG_CHARS: truncate to first/last TRUNCATE_KEEP_CHARS
    - Total output capped at MAX_OUTPUT_CHARS
    """
    messages = data["messages"]
    thinking = data["thinking"]
    total = data["total_entries"]

    # Determine the 40% cutoff index
    cutoff_index = int(total * 0.4)

    # Build thinking map: index -> text (only for entries after cutoff)
    thinking_map = {}
    for t in thinking:
        if t["index"] >= cutoff_index:
            thinking_map.setdefault(t["index"], []).append(t["text"])

    # Build the output
    parts = []

    # Header with metadata
    parts.append(f"# Session Transcript (preprocessed for handoff)")
    parts.append(f"Session: {data['session_id']}")
    parts.append(f"Branch: {data['git_branch']}")
    parts.append(f"Total entries: {data['total_entries']}")
    parts.append(f"Messages extracted: {len(messages)}")
    parts.append("")

    if data["file_paths"]:
        parts.append("## Files Referenced")
        for fp in data["file_paths"]:
            parts.append(f"- `{fp}`")
        parts.append("")

    parts.append("## Conversation")
    parts.append("")

    for msg in messages:
        role_label = "USER" if msg["role"] == "user" else "CLAUDE"
        text = msg["text"]

        # Truncate oversized user messages
        if msg["role"] == "user" and len(text) > MAX_USER_MSG_CHARS:
            omitted = len(text) - (TRUNCATE_KEEP_CHARS * 2)
            text = (
                text[:TRUNCATE_KEEP_CHARS]
                + f"\n[truncated — {omitted} chars omitted]\n"
                + text[-TRUNCATE_KEEP_CHARS:]
            )

        parts.append(f"### {role_label}")
        parts.append(text)
        parts.append("")

        # Insert thinking blocks that belong to this message index
        if msg["index"] in thinking_map and msg["role"] == "assistant":
            for thought in thinking_map[msg["index"]]:
                # Truncate very long thinking blocks too
                if len(thought) > 3000:
                    thought = thought[:1500] + "\n[thinking truncated]\n" + thought[-1500:]
                parts.append(f"<claude-thinking>")
                parts.append(thought)
                parts.append(f"</claude-thinking>")
                parts.append("")

    output = "\n".join(parts)

    # Enforce hard cap
    if len(output) > MAX_OUTPUT_CHARS:
        # Strategy: keep last 40% of messages in full, drop oldest first
        # (Matches spec: "Keep ALL messages from the last 40% of the session in full")
        keep_count = max(int(len(messages) * 0.4), 5)  # Keep at least 5 messages
        messages_trimmed = messages[-keep_count:]

        parts_trimmed = parts[:10]  # Keep header
        parts_trimmed.append("[Earlier conversation truncated for size budget]")
        parts_trimmed.append("")

        for msg in messages_trimmed:
            role_label = "USER" if msg["role"] == "user" else "CLAUDE"
            text = msg["text"]
            if msg["role"] == "user" and len(text) > MAX_USER_MSG_CHARS:
                omitted = len(text) - (TRUNCATE_KEEP_CHARS * 2)
                text = (
                    text[:TRUNCATE_KEEP_CHARS]
                    + f"\n[truncated — {omitted} chars omitted]\n"
                    + text[-TRUNCATE_KEEP_CHARS:]
                )
            parts_trimmed.append(f"### {role_label}")
            parts_trimmed.append(text)
            parts_trimmed.append("")
            if msg["index"] in thinking_map and msg["role"] == "assistant":
                for thought in thinking_map[msg["index"]]:
                    if len(thought) > 3000:
                        thought = thought[:1500] + "\n[thinking truncated]\n" + thought[-1500:]
                    parts_trimmed.append(f"<claude-thinking>")
                    parts_trimmed.append(thought)
                    parts_trimmed.append(f"</claude-thinking>")
                    parts_trimmed.append("")

        output = "\n".join(parts_trimmed)

    return output
```

- [ ] **Step 5: Write the main entry point and argument parsing**

Add to `preprocess.py`:

```python
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Preprocess Claude Code session JSONL for handoff")
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    parser.add_argument("--file", "-f", help="Path to specific JSONL file (default: auto-detect)")
    args = parser.parse_args()

    # Locate session file
    if args.file:
        jsonl_path = args.file
        if not os.path.isfile(jsonl_path):
            die(f"File not found: {jsonl_path}")
    else:
        jsonl_path = find_session_jsonl()

    # Check file size
    file_size = os.path.getsize(jsonl_path)
    if file_size > 100_000_000:  # 100MB
        print(f"WARNING: Large session file ({file_size // 1_000_000}MB). "
              f"Processing may take a moment.", file=sys.stderr)

    # Extract and format
    data = extract_conversation(jsonl_path)
    output = apply_recency_weighting(data)

    # Write output
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Preprocessed transcript written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Test preprocessor against real session data**

Run: `cd /Users/brianruggieri/git/skills && python3 handoff/scripts/preprocess.py | head -40`
Expected: Session metadata header, files referenced section, and conversation starting with USER/CLAUDE blocks.

Run: `cd /Users/brianruggieri/git/skills && python3 handoff/scripts/preprocess.py | wc -c`
Expected: Output size well under 600,000 characters.

- [ ] **Step 7: Commit the preprocessor**

```bash
git add handoff/scripts/preprocess.py
git commit -m "Add JSONL preprocessor for handoff skill"
```

---

### Task 2: Create the Extraction Prompt

**Files:**
- Create: `handoff/prompts/extract.md`

This is the core extraction logic — what Claude reads to know how to turn a transcript into a handoff document. This file is a ralph-loop target and will be iterated on.

- [ ] **Step 1: Write the extraction prompt**

```markdown
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
```

- [ ] **Step 2: Verify the prompt file is readable**

Run: `cat handoff/prompts/extract.md | wc -l`
Expected: ~60-80 lines

- [ ] **Step 3: Commit the extraction prompt**

```bash
git add handoff/prompts/extract.md
git commit -m "Add extraction prompt for handoff skill"
```

---

### Task 3: Create the Convention Detection Prompt

**Files:**
- Create: `handoff/prompts/conventions.md`

Separate extraction pass for identifying durable project knowledge and user preferences.

- [ ] **Step 1: Write the convention detection prompt**

```markdown
# Convention Detection Prompt

You are analyzing a session transcript to identify durable project knowledge that should persist beyond this session. This is separate from the handoff document — these are conventions, patterns, and preferences that apply to ALL future work on this project.

## What to Look For

### Project Conventions (→ suggest for CLAUDE.md)
Patterns or rules established in conversation that would still be useful 2 weeks from now in an unrelated session. Examples:
- "Use Result types instead of thrown exceptions for new modules"
- "All auth code must live under src/auth/"
- "Use bcrypt for password hashing"
- "Tests use vitest, not jest"

Do NOT include:
- Implementation details specific to the current feature
- Temporary decisions ("for now", "in v1")
- Things already documented in CLAUDE.md (you will be told what is already there)

### User Preferences (→ suggest for memory)
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
```

- [ ] **Step 2: Commit the convention prompt**

```bash
git add handoff/prompts/conventions.md
git commit -m "Add convention detection prompt for handoff skill"
```

---

### Task 4: Create the SKILL.md Orchestrator

**Files:**
- Create: `handoff/SKILL.md`

This is the main skill file that Claude Code loads when the user types `/handoff`. It orchestrates all five phases.

- [ ] **Step 1: Write SKILL.md**

```markdown
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

Run the preprocessor to extract conversation text from the session JSONL:

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
- If edit: let the user modify the text, then append
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
```

- [ ] **Step 2: Verify the SKILL.md structure matches existing skills**

Run: `head -15 handoff/SKILL.md`
Expected: YAML frontmatter with name, description, allowed-tools matching spec.

- [ ] **Step 3: Commit the SKILL.md**

```bash
git add handoff/SKILL.md
git commit -m "Add handoff skill orchestrator"
```

---

### Task 5: Integration Test — End-to-End Dry Run

**Files:**
- No new files. Testing existing files against real data.

- [ ] **Step 1: Run the preprocessor against the current session**

```bash
cd /Users/brianruggieri/git/skills
python3 handoff/scripts/preprocess.py --output /tmp/handoff-test-transcript.md
```

Expected: File written, no errors.

- [ ] **Step 2: Verify preprocessor output quality**

```bash
head -30 /tmp/handoff-test-transcript.md
```

Expected: Header with session ID, branch, file count. Conversation section with USER/CLAUDE blocks.

```bash
wc -c /tmp/handoff-test-transcript.md
```

Expected: Under 600,000 characters.

```bash
grep -c '### USER' /tmp/handoff-test-transcript.md
grep -c '### CLAUDE' /tmp/handoff-test-transcript.md
grep -c '<claude-thinking>' /tmp/handoff-test-transcript.md
```

Expected: Reasonable counts — user messages, assistant messages, and some thinking blocks from the latter portion of the session.

- [ ] **Step 3: Verify the skill files are all in place**

```bash
ls -la handoff/SKILL.md handoff/prompts/extract.md handoff/prompts/conventions.md handoff/scripts/preprocess.py
```

Expected: All four files exist.

- [ ] **Step 4: Clean up test artifacts**

```bash
rm -f /tmp/handoff-test-transcript.md
```

- [ ] **Step 5: Final commit with all files**

```bash
git add handoff/
git commit -m "Add handoff skill: plan-to-build session handoff for Claude Code

Skill extracts decisions, negative knowledge, constraints, and next steps
from planning sessions. Uses a Python preprocessor for JSONL parsing and
Claude's reasoning for semantic extraction. Extraction prompts live in
separate files for ralph-loop iteration."
```

---

### Task 6: Create Test Fixture for Ralph-Loop

**Files:**
- Create: `handoff/tests/fixtures/real-planning-session.md`

- [ ] **Step 1: Save a real preprocessed transcript as a test fixture**

```bash
mkdir -p handoff/tests/fixtures
cd /Users/brianruggieri/git/skills
python3 handoff/scripts/preprocess.py --output handoff/tests/fixtures/real-planning-session.md
```

This captures the handoff skill's own design session — rich with decisions, constraints, negative knowledge, and a multi-phase plan. Ideal first fixture.

- [ ] **Step 2: Verify the fixture is usable**

```bash
wc -l handoff/tests/fixtures/real-planning-session.md
head -20 handoff/tests/fixtures/real-planning-session.md
```

Expected: Reasonable line count, clean header with metadata.

- [ ] **Step 3: Commit fixture**

```bash
git add handoff/tests/fixtures/
git commit -m "Add real session fixture for handoff ralph-loop iteration"
```
