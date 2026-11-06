---
name: codex-imagegen
description: "Use when the user asks to generate, create, or edit an image of any kind — game assets, sprites, textures, hero/blog images, UI mockups — from the CLI or an agent. Subscription-billed via OpenAI Codex CLI $imagegen (gpt-image-2), no API key. NOT for viewing/analyzing existing images (Claude reads those natively) or diagrams-from-text (use a diagramming skill if installed)."
---

# codex-imagegen — subscription-billed image generation

Last verified July 2026: the best subscription-billed CLI image path is the
first-party Codex CLI feature, `gpt-image-2`, billed to the ChatGPT sub (no
`OPENAI_API_KEY`). Claude has no image generation; Gemini CLI can't bill image
gen to a Google sub. Requires the `codex` CLI installed and signed in — if
`command -v codex` fails, stop and tell the user. Codex flags move fast: if the
incantation below errors, check the docs link at the bottom before debugging.

## Generate — the verified incantation (last tested 2026-07-05)

```bash
cd <writable-work-dir> && codex exec --sandbox workspace-write --skip-git-repo-check \
  '$imagegen a seamless granite stone texture, top-down, 1024x1024, photorealistic. Save to ./stone.png' </dev/null
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
  1. `OPENAI_API_KEY=… codex exec …` → API billing (API only when subscription
     isn't practical — a big batch qualifies).
  2. Local Flux/SD via ComfyUI — zero marginal cost, offline; the right answer
     for iterative texture loops (lesson from a texture ralph-loop:
     vision-scored generation loops plateau — generate few, pick by eye).
- Not available on ChatGPT Free tier.

## Composing

- From Claude Code agents: shell out exactly as above; treat the returned file
  as untrusted output (look at it before shipping it).
- Asset pipelines: if the project already has a procedural generator
  (e.g. trimesh geometry), this skill complements it for texture/reference
  images; it does not replace it.

Docs: https://developers.openai.com/codex/cli/features · pricing: https://developers.openai.com/codex/pricing
