---
name: codex-imagegen
description: "Use when the user asks to generate or edit an image (game asset, blog image, UI mockup, texture) from the CLI or from an agent — subscription-billed, no API key. Wraps OpenAI Codex CLI's $imagegen (gpt-image-2) on ChatGPT-subscription auth. NOT for viewing/analyzing existing images (Claude reads those natively) or for diagrams-from-text (use a diagramming skill if installed)."
---

# codex-imagegen — subscription-billed image generation

As of July 2026 this is the best subscription-billed CLI image path: first-party
Codex CLI feature, `gpt-image-2`, billed to the ChatGPT sub (no `OPENAI_API_KEY`).
Claude has no image generation; Gemini CLI can't bill image gen to a Google sub.

## Generate — the verified incantation (tested 2026-07-05)

```bash
cd <writable-work-dir> && codex exec --sandbox workspace-write --skip-git-repo-check \
  '$imagegen a seamless granite curling-stone texture, top-down, 1024x1024, photorealistic. Save to ./stone.png' </dev/null
```

Every flag was earned on the first live run:
- `--sandbox workspace-write` — default sandbox is read-only; codex generates
  the image but CANNOT SAVE it (and /tmp is never writable regardless — save
  to `./` in the cwd).
- `--skip-git-repo-check` — required outside a trusted git repo.
- `</dev/null` — codex hangs under the Bash tool without it.
- Wrap in `gtimeout 300` when available; image turns are slow.
- Verify `test -s ./stone.png` after — codex's prose claims success even when
  the save was sandbox-blocked.
- Edits: reference the source image path in the prompt ("edit ./stone.png: …").
- Ignore codex mentioning OPENAI_API_KEY for a "skill CLI path" — the built-in
  `$imagegen` path works on subscription auth; only batches need the key.

## Quota rules

- Each image burns the SHARED Codex pool ~3-5x faster than a coding turn.
  Fine for onesies; for a batch (>5 images) STOP and offer the two escape
  hatches instead of draining the sub:
  1. `OPENAI_API_KEY=… codex exec …` → API billing (per the user's global rule:
     API only when subscription isn't practical — a big batch qualifies).
  2. Local Flux/SD via ComfyUI on Apple Silicon — zero marginal cost, offline;
     the right answer for iterative texture loops (the stone-texture ralph-loop
     lesson: vision-scored generation loops plateau — generate few, pick by eye).
- Not available on ChatGPT Free tier.

## Composing

- From Claude Code agents: shell out exactly as above; treat the returned file
  as untrusted output (look at it before shipping it).
- Asset pipelines: curling's `tools/curling-asset-gen` is procedural
  (trimesh) — this skill complements it for texture/reference images, it does
  not replace it.

Docs: https://developers.openai.com/codex/cli/features · pricing: https://developers.openai.com/codex/pricing
