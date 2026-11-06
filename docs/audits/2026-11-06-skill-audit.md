# Skill audit — 2026-11-06

Scope: every skill in `skills/`, the trigger-eval harness, the nested eval
runbooks, and the plugin manifest. Method: static read of each SKILL.md
against the house rules in CONTRIBUTING.md, `claude plugin validate`,
`claude --plugin-dir . plugin details skills`, the bundled Python tests, and a
live trigger-matrix run of all 12 active skills on haiku via `--plugin-dir`.

**What this audit could not measure:** actual invocation frequency. Session
logs live on the author's machine and were not available here, so "underuse"
below is assessed structurally — whether a skill *can* fire and *can* run for
anyone other than its author — not from usage counts. Re-run
`session-archaeology` locally (grep `"skill":"skills:<name>"` across
`~/.claude/projects`) to get the real numbers.

## Headline findings

1. **The trigger-eval harness was leaking the answer into every prompt.** The
   prompt loop reads `prompts/<skill>.txt` on stdin, and `claude -p` appends
   anything on stdin to the prompt. Without `</dev/null`, every run received
   the *entire* +/- matrix after its own prompt. Verified in transcripts: the
   first user message of each run was `<prompt>\n+ run brain sleep\n+ …`.
   Every prior "clean matrix" result, including the tuning commit
   `a858b56`, is therefore unvalidated. Fixed in `run.sh`; results below are
   from the fixed harness.
2. **The harness could silently reuse the previous prompt's verdict.** It
   computed a `before` file count but never checked it, so a run that wrote
   no transcript (timeout, quota, auth) was graded on the newest *older*
   file. Now reported as `ERR` and counted as a failure.
3. **The harness could not test an uninstalled checkout.** No way to load the
   repo as a plugin, so CONTRIBUTING's "run the matrix before opening a PR"
   was only possible after installing. Added `--plugin-dir`.
4. **Three nested SKILL.md files are not skills.** `claude plugin details`
   lists 13 skills; `eval-extract`, `eval-triage` and `eval-implementation`
   are not among them (plugins load only `skills/<name>/SKILL.md`). The
   documented invocation `/handoff:eval-implementation` could never work for
   a plugin named `skills`. They are now labelled as repo-maintenance
   runbooks with a working invocation.
5. **The archived skill was still loaded.** `scope-repo` says "do not
   auto-invoke" but sat in `skills/`, costing ~110 always-on tokens in every
   installer's session and advertising WebSearch/WebFetch. Moved to
   `archive/`.
6. **Six skills hard-depended on the author's private tooling or on dated
   assertions**, which makes them unusable or misleading for anyone else:

   | Skill | Blocker | Fix |
   |---|---|---|
   | brain-sleep | required `~/.claude/scripts/digest-sessions.py`, a gbrain MCP server, a `[[wiki-link]]` to a private memory file, a `-Users-*` glob that fails on Linux, and a hardcoded first-run date | all optional with stated fallbacks; platform-neutral memory-dir resolution; relative first-run window |
   | headless-claude-hygiene | "Still true as of July 2026 … recheck after 2026-10-01" was overdue; `cleanupPeriodDays: 99999` and five private project names presented as canonical | billing claim reframed as "verify before relying"; private names generalised to the pattern they illustrate; one gendered pronoun fixed |
   | session-archaeology | junk-session list and a Mar-2026 archive cutoff were author-specific | labelled as examples; retention expressed in terms of `cleanupPeriodDays` |
   | ab-experiment | quota gate pointed at a non-shipped script and `usage-state.json`; "June 2026 billing change paused" | gate optional; billing claim defers to headless-claude-hygiene |
   | codex-imagegen | "As of July 2026 … best path"; example prompt and asset-pipeline note referenced a private game project; no check that `codex` exists | "last verified" framing; generic example; preflight for the CLI |
   | tiered-fanout | three rules cited "per global CLAUDE.md" (the author's, not the installer's) | rules inlined |

7. **The harness's pinned floor model was the biggest "underuse" signal of
   all.** With the stdin leak fixed, identical matrices scored 43/68 on
   haiku 4.5 (24 under-triggers, 1 over-trigger) and 62/68 on haiku 5.5
   (6 under-triggers, 0 over-triggers). On haiku 4.5 even "grill me on this
   architecture proposal" and "ghostwrite a reply … in my voice" did not
   load their skills — the model acted directly or asked a clarifying
   question first. A year-old default model was measuring its own
   reluctance to call `Skill`, not the descriptions. Default moved to the
   current haiku; the README now says to keep it current.
8. **Five descriptions were still under-firing on the current model**, all
   with the same shape: the model started *doing* the task (running `gh`,
   looking for the image file, asking for the email) instead of loading the
   skill first. Each description now says to load before intake or before
   the first shell command, and names the substitute behaviour to avoid:
   - tiered-fanout — "Load FIRST, before any gh/git/worktree command or Agent call"; both positives had missed on every model.
   - grill-me — "load it even if the plan itself hasn't been pasted yet".
   - ghostwrite — "Load it BEFORE asking for the source text".
   - codex-imagegen — "BEFORE searching for the source file or attempting a substitute (hand-written SVG is not an image)"; haiku had hand-built a 16×16 SVG sprite rather than fire.
   - brain-sleep — added the "my memory files are stale" phrasing its own matrix tests.
   Each was re-run after the change; ghostwrite and codex-imagegen twice,
   since single-prompt trigger results are one stochastic sample.
9. **Two matrices were under the 3+/3- house minimum** (honest-assessment,
   tiered-fanout). Extended.
10. `claude plugin validate` passes; the only warning is a missing plugin
    icon (cosmetic, not fixed). Bundled tests: 61 passed, 1 skipped.

## Per-skill assessment

| Skill | Loads | Matrix | Portable for a public installer | Notes |
|---|---|---|---|---|
| handoff | yes | 3+/3- | yes | largest skill (7.4k tokens on invoke); evidence-backed; no changes |
| fix-pr-reviews | yes | 3+/3- | yes (needs `gh`) | 8.8k tokens on invoke; security section is the house pattern; no changes |
| grill-me | yes | 3+/3- | yes (soft redirects to optional skills) | 8.9k tokens on invoke; description: load before the plan is pasted |
| ghostwrite | yes | 3+/3- | yes | script + security tests ship; description: load before intake |
| ab-experiment | yes | 3+/3- | now yes | depended on private gate script |
| honest-assessment | yes | 2→3+/2→3- | yes | thin matrix extended; description gained the new prompt's phrasing + a NOT clause |
| tiered-fanout | yes | 2→3+/2→3- | now yes | "global CLAUDE.md" refs inlined; description rewritten — 0/2 positives fired on any model before |
| session-archaeology | yes | 3+/3- | now yes | author-specific junk list generalised |
| headless-claude-hygiene | yes | 3+/3- | now yes | overdue time-bomb removed |
| brain-sleep | yes | 3+/3- | now yes, degraded | gbrain/digest phases optional; description widened to include "my memory files are stale" |
| codex-imagegen | yes | 3+/3- | needs Codex CLI | stated up front now; description: no hand-drawn substitutes |
| trigger-eval | yes | 3+/3- | yes | three harness bugs fixed (above); default model moved to current haiku |
| scope-repo | **no longer** | none | n/a | moved to `archive/` |
| eval-extract / eval-triage / eval-implementation | **never did** | none | n/a | labelled as runbooks |

## Trigger matrix results (fixed harness, `--plugin-dir`, one run per cell)

`a/b` = prompts graded correctly out of total; `(n↓ m↑)` = under-triggers / over-triggers. The first two columns are the committed descriptions before this audit (same snapshot, two models); the third is this branch.

| Skill | haiku 4.5, original descriptions | haiku 5.5, original descriptions | haiku 5.5, refined descriptions |
|---|---|---|---|
| ab-experiment | 3/6 (3↓ 0↑) | 6/6 | 6/6 |
| brain-sleep | 6/6 | 5/6 (1↓ 0↑) | 6/6 |
| codex-imagegen | 4/6 (2↓ 0↑) | 5/6 (1↓ 0↑) | 6/6 |
| fix-pr-reviews | 3/6 (3↓ 0↑) | 6/6 | 6/6 |
| ghostwrite | 4/6 (2↓ 0↑) | 5/6 (1↓ 0↑) | 6/6 |
| grill-me | 3/6 (3↓ 0↑) | 5/6 (1↓ 0↑) | 6/6 |
| handoff | 3/6 (2↓ 1↑) | 6/6 | 6/6 |
| headless-claude-hygiene | 3/6 (3↓ 0↑) | 6/6 | 6/6 |
| honest-assessment | 2/4 (2↓ 0↑) | 4/4 | 5/6 (1↓ 0↑) |
| honest-assessment-rerun1 | n/a | n/a | 6/6 |
| honest-assessment-rerun2 | n/a | n/a | 6/6 |
| session-archaeology | 6/6 | 6/6 | 6/6 |
| tiered-fanout | 2/4 (2↓ 0↑) | 2/4 (2↓ 0↑) | 6/6 |
| trigger-eval | 4/6 (2↓ 0↑) | 6/6 | 6/6 |
| **total** | **43/68** | **62/68** | **83/84** |

The one remaining miss in the third column was a `+` prompt added by this
audit ("audit the numbers in this sprint report, which were actually measured
and which came from mocks?"). The description was given that phrasing and a
"NOT a progress summary" clause, then re-run twice: 6/6 and 6/6. Final
state: every active skill's matrix is clean on the current haiku, 72/72.

Cost of the whole evaluation: roughly 290 headless haiku prompts (four full
68–72-prompt passes plus targeted re-runs), a few dollars at list price.
Every pass ran in a neutral scratch cwd with `--permission-mode dontAsk`
and left its transcripts under `~/.claude/projects/-tmp-te-w*` for
inspection; they were deleted between passes.


## Still open

- Real usage counts (needs the author's session corpus).
- Plugin icon warning from `claude plugin validate`.
- Trigger behaviour on haiku is a floor; the house rule to re-run with the
  daily-driver model before trusting a borderline description still stands.
