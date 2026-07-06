---
name: session-archaeology
description: "Use for any question answerable from Claude Code history: 'what have I done with X', 'check your claude logs', 'we've talked about this before', retrospectives, resume/interview material, or auditing a tool's own session behavior. Mines ~/.claude/projects JSONLs correctly, filtering tool-generated noise. NOT for consolidating/evicting memory files (use brain-sleep)."
---

# /session-archaeology

Mine Claude Code session history for evidence. Every finding must be cited (session id, date, quote) — line-cited evidence, not vibes.

## Corpus map

- **Sessions:** `~/.claude/projects/<cwd-slug>/*.jsonl` — slug is the cwd with `/` → `-` (e.g. `-Users-brianruggieri-git-curling`).
- **Per-project memory:** `~/.claude/projects/<slug>/memory/MEMORY.md` — read first; often already answers "have we decided this".
- **Archive fallback:** `~/.claude-archive/projects/` for pre-Mar-10-2026 history (retention was 30 days before `cleanupPeriodDays: 99999`).
- **JSONL shape:** one JSON object per line. Human/assistant turns are wrapped: `{"type":"user"|"assistant","message":{...},"timestamp":...,"sessionId":...}`. Also present: progress events, tool results, subagent sidecar files. Human input = `type == "user"` where `message.content` is a string (or text block) and there's no `toolUseResult`.

## Noise filters — apply FIRST, before any analysis

Most files in the corpus are NOT human work. Known junk populations (canonical counts — headless-claude-hygiene links here):

1. **1-message haiku one-shots:** ccp's `--ai-context` summarizer. Fixture prompt: `Summarize this developer task in 3-5 words`. Drop any session whose only user message matches known fixture prompts.
2. **Headless `--print` runs:** candidate-eval (~3,000 sessions), pulse (257 test sessions), personalities (~120 benchmark runs). These are program output, not Brian's work.
3. **Harness-generated worktree sessions:** arc `--worktrees-*` dirs, `agent-*` worktree slugs, sculptor `-sculptor-workspaces-*` slugs.
4. **Fixture cwds:** anything under `/private/tmp/ccp-*` or other `/private/tmp` slugs.

Cheap heuristics, in order:

```bash
# tiny sessions (1-3 lines) are almost always one-shots
find ~/.claude/projects/<slug> -name '*.jsonl' -size -4k

# fixture-prompt check
grep -l 'Summarize this developer task in 3-5 words' ~/.claude/projects/<slug>/*.jsonl

# junk dirs by slug pattern
ls ~/.claude/projects/ | grep -E 'worktrees|agent-|sculptor-workspaces|private-tmp'
```

Filter by: message count, known fixture prompts, `/private/tmp` cwds, worktree/`agent-*` dirs. When in doubt, sample the first user message — if it reads like a template, it's a template.

## Identification rules

- **Main session of a project = largest file, not newest mtime.** mtime gets touched by summarizers and background reads. `ls -laS ~/.claude/projects/<slug>/*.jsonl | head -3`.
- **Effective tokens = input + output + cache_read + cache_creation** (from `message.usage`). Raw input/output alone wildly undercounts real activity.
- **Failure forensics:** headless-run failures (e.g. 401 auth expiry) are buried in the session `.jsonl`, not stderr — grep the JSONL for the error, don't trust exit codes alone.

## Workflow

1. Read the relevant project `memory/MEMORY.md` files — decisions are often already recorded there.
2. Map candidate project dirs: `ls -d ~/.claude/projects/*/ | grep -vE 'worktrees|agent-|sculptor'`. Include `~/.claude-archive` if the question predates Mar 10 2026.
3. Apply noise filters above.
4. **Broad questions** ("what have I done with X", retrospective, resume material): fan out — one subagent per project dir, each mining human user messages + outcomes from the filtered JSONLs; a synthesizer pass reconciles overlaps and dedupes.
5. **Narrow questions** ("have we decided this before", "check your logs before re-deciding"): NO fan-out. Targeted grep across the relevant project's JSONLs first:

```bash
grep -l '<keyword>' ~/.claude/projects/<slug>/*.jsonl
# then extract matching human turns with context
python3 -c "
import json,sys
for line in open(sys.argv[1]):
    try: o=json.loads(line)
    except: continue
    if o.get('type')=='user' and isinstance(o.get('message',{}).get('content'),str) and 'KEYWORD' in o['message']['content']:
        print(o.get('timestamp',''), o.get('sessionId','')[:8], o['message']['content'][:300])
" <file>
```

## Output

Every claim cites its source: **session id (short), date, project, and a direct quote**. Format:

> "exact quote from the session" — `a1b2c3d4`, 2026-03-28, ~/git/candidate-eval

If a question can't be answered from the corpus, say so — don't extrapolate from memory files alone. Distinguish "Brian said X" (user message) from "Claude did X" (assistant/tool activity).
