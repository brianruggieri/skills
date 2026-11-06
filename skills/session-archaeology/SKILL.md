---
name: session-archaeology
description: "Use for any question answerable from Claude Code session history: 'what have I done with X', 'check your claude logs', 'we've talked about this before, dig it up', retrospectives, resume/interview material, or auditing a tool's own session behavior. Mines ~/.claude/projects JSONLs correctly, filtering tool-generated noise. NOT for application/server logs, git history questions, building a writing voice profile (use ghostwrite), or consolidating memory files (use brain-sleep)."
---

# /session-archaeology

Mine Claude Code session history for evidence. Every finding must be cited (session id, date, quote) — line-cited evidence, not vibes.

## Corpus map

- **Sessions:** `~/.claude/projects/<cwd-slug>/*.jsonl` — slug is the cwd with `/` → `-` (e.g. `-Users-example-git-myrepo`). Resolve your own project slugs at runtime rather than hardcoding a home dir: `ls ~/.claude/projects/`.
- **Per-project memory:** `~/.claude/projects/<slug>/memory/MEMORY.md` — read first; often already answers "have we decided this".
- **Archive fallback:** `~/.claude-archive/projects/` if you archive old project dirs there (headless-claude-hygiene's audit mode offers this). Default retention is `cleanupPeriodDays: 30`; anything older is gone unless you raised it or archived.
- **JSONL shape:** one JSON object per line. Human/assistant turns are wrapped: `{"type":"user"|"assistant","message":{...},"timestamp":...,"sessionId":...}`. Also present: progress events, tool results, subagent sidecar files. Human input = `type == "user"` where `message.content` is a string (or text block) and there's no `toolUseResult`.

## Noise filters — apply FIRST, before any analysis

Most files in the corpus are NOT human work. Junk populations, with examples from one real corpus (substitute the tools in your own environment — the categories transfer, the names don't):

1. **1-message one-shots from summarizer tools:** e.g. a commit-summarizer's haiku call with the fixture prompt `Summarize this developer task in 3-5 words`. Drop any session whose only user message matches a known fixture prompt.
2. **Headless `--print` runs:** eval harnesses (~3,000 sessions in one case), test suites that forgot to stub `claude` (257 sessions), benchmark loops (~120 runs). These are program output, not the user's work.
3. **Harness-generated worktree sessions:** `--worktrees-*` dirs, `agent-*` worktree slugs, sandbox-workspace slugs from agent orchestrators.
4. **Fixture cwds:** anything under `/private/tmp/*` or `/tmp/*` slugs (trigger-eval's `te-w*` dirs land here deliberately).

Cheap heuristics, in order:

```bash
# tiny sessions (1-3 lines) are almost always one-shots
find ~/.claude/projects/<slug> -name '*.jsonl' -size -4k

# fixture-prompt check
grep -l 'Summarize this developer task in 3-5 words' ~/.claude/projects/<slug>/*.jsonl

# junk dirs by slug pattern
ls ~/.claude/projects/ | grep -E 'worktrees|agent-|workspaces|private-tmp|^-tmp-'
```

Filter by: message count, known fixture prompts, `/private/tmp` cwds, worktree/`agent-*` dirs. When in doubt, sample the first user message — if it reads like a template, it's a template.

## Identification rules

- **Main session of a project = largest file, not newest mtime.** mtime gets touched by summarizers and background reads. `ls -laS ~/.claude/projects/<slug>/*.jsonl | head -3`.
- **Effective tokens = input + output + cache_read + cache_creation** (from `message.usage`). Raw input/output alone wildly undercounts real activity.
- **Failure forensics:** headless-run failures (e.g. 401 auth expiry) are buried in the session `.jsonl`, not stderr — grep the JSONL for the error, don't trust exit codes alone.

## Workflow

1. Read the relevant project `memory/MEMORY.md` files — decisions are often already recorded there.
2. Map candidate project dirs: `ls -d ~/.claude/projects/*/ | grep -vE 'worktrees|agent-|workspaces'`. Include `~/.claude-archive` if the question predates your retention window.
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

> "exact quote from the session" — `a1b2c3d4`, 2026-03-28, ~/git/my-project

If a question can't be answered from the corpus, say so — don't extrapolate from memory files alone. Distinguish "the user said X" (user message) from "Claude did X" (assistant/tool activity).
