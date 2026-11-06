---
name: tiered-fanout
description: "Load FIRST — before any gh/git/worktree command or Agent call — whenever the user wants several coding agents working at once: 'dispatch agents to close these N issues in parallel', 'fan out subagents over these plans', 'run five agents on these tasks', 'a worktree per plan'. Classifies the work into safe-parallel vs shared-surface-serial tiers and generates the per-agent briefs; skipping it is how green-in-isolation branches ship incompatible. NOT for running shell commands or tests in parallel, and NOT for advice on organizing an epic when no agents will be dispatched."
---

# /tiered-fanout

Do NOT do a flat N-way parallel run. Classify first, dispatch second. Every rule below was earned: curling epic #418 closed 26 issues cleanly with tiers; candidate-eval v0.5 shipped mutually-incompatible code because two "independent" plans shared a function signature (green in isolation, broken merged); Sculptor M1 leaked uncommitted state and duplicated contract fields; curlit's overnight run self-abandoned its background jobs and kept dying to a floating model (see Step 3 for the full telling).

## Step 1: Dependency analysis (before any worktree)

Analyze at the **API level, not the file level**. Two plans touching different files can still collide on a shared contract.

For each plan/issue, list the function signatures, trait/interface definitions, contract types, and schema fields it will add or modify. Then grep for overlap:

```bash
# for each symbol a plan says it will touch:
grep -rn "fn <name>\|type <Name>\|struct <Name>\|interface <Name>" src/
```

- Two plans share a signature or contract type → **same Tier-B serial track**, OR the lead lands a contracts-foundation commit first that both build on (M1 pattern), then they may parallelize.
- Build a rough DAG: contract/foundation work is wave 1; dependents are wave 2+.

## Step 2: Tier classification

Assign every item exactly one tier. Write the list down before spawning anything.

| Tier | What | Dispatch shape |
|------|------|----------------|
| **A** | Parallel-safe, isolated surface (own module/crate, no shared symbols) | Own worktree each, run in parallel, **cap ~6 concurrent** |
| **B** | Shared crate/module/contract | **SERIAL** — one agent per module, each re-fetches main before starting (`git fetch origin && git rebase origin/main`) |
| **C** | Judgment or design-intent calls | **Hold.** Do not dispatch. Surface to human with a recommendation |
| **D** | Suspected bugs | Verify-first track: reproduce before fixing, dispatched **after** cleanup tiers land (the "bug" may be dead code a cleanup deletes) |

Create all Tier-A worktrees before spawning any agent (`.worktrees/<branch-name>` inside the repo, gitignored).

## Step 3: Per-agent briefing

Generate every prompt from this boilerplate — no freehand briefs:

```
Task: <exact scope — issue #, files, symbols. Nothing else.>
Worktree: <absolute path>. Branch: <name>. All paths you use must be absolute.
STOP after completing this task. Do not pick up adjacent work, do not
"improve while you're in there", do not start a follow-up.
Forbidden: global cargo fmt / prettier --write . / any repo-wide reformat;
touching files outside your scope; force-push; committing to main.
Commit: brief imperative messages, no Co-Authored-By trailers.
Model: <pinned model id>.
Done means: <verifiable check — test command, file exists, gate green>.
```

**Always pin the model explicitly.** Never leave model selection floating on an unattended run — the curlit overnight run died 23x because model selection floated instead of being pinned.

## Step 4: Orchestrator duties during the run

Orchestrator owns completion — poll and resume workers via Monitor/SendMessage, never trust a quiet agent to self-report or self-resume.

- **One CPU-heavy sweep/test-suite at a time.** Check load (`uptime`) before launching another.
- Verify each agent's branch immediately after dispatch: `git -C .worktrees/<name> branch --show-current` — one agent once committed straight to main.
- Track per-agent status in a simple checklist (issue, tier, worktree, state, verified-done).

## Step 5: Merge protocol

- **Lead owns all shared-contract merges.** Tier-B branches merge one at a time, in dependency order, main re-fetched between each.
- Before merging any two branches, diff their worktrees for duplicate additions (M1 shipped duplicate contract fields):

```bash
git diff origin/main...branch-a -- <contract files> > /tmp/a.diff
git diff origin/main...branch-b -- <contract files> > /tmp/b.diff
diff /tmp/a.diff /tmp/b.diff
```

- **Hard-stop conditions** — halt the merge train and escalate to human:
  - A "zero-caller" deletion that actually has a caller (`grep -rn <symbol>` before believing any agent's dead-code claim)
  - Determinism gate red
  - Any branch with uncommitted state in its worktree (`git -C .worktrees/<name> status --porcelain` must be empty)

## Cleanup

Run the 3-step worktree cleanup (`git worktree remove` → `git worktree prune` → `git branch -d`) for every branch, then audit nothing was left behind: `git worktree list && git branch --merged main`.

## Quick checklist

1. [ ] API-level overlap grep done; DAG sketched
2. [ ] Every item assigned tier A/B/C/D
3. [ ] Contracts-foundation commit landed (if any B items share types)
4. [ ] Worktrees created before spawning; ≤6 concurrent Tier-A
5. [ ] Every brief from boilerplate; model pinned; STOP guardrail present
6. [ ] Polling loop running; branches verified post-dispatch
7. [ ] Lead merges shared contracts serially; duplicate-addition diff done
8. [ ] Tier-D verify-first only after cleanups land; Tier-C sent to human
9. [ ] Worktree cleanup ×3 per branch
