---
name: tiered-fanout
description: "Use when actually DISPATCHING 3+ parallel subagents/worktrees — 'fan out agents', 'close these N issues in parallel', 'dispatch agents over these plans' — before creating worktrees or spawning anything. Classifies work into safe-parallel vs shared-surface-serial tiers with proven dispatch guardrails. NOT for advice on organizing or planning an epic without dispatching agents."
---

# /tiered-fanout

Cross-cutting defaults (worker cap, review-round bounds, acceptance evidence,
event-wait discipline) live in `references/execution-policy.md` — read it
once; `session-archaeology`, `astra-orchestration`, and the `orchestration`
stub all point here too instead of repeating it.

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
| **A** | Parallel-safe, isolated surface (own module/crate, no shared symbols) | Assign disjoint ownership in the current checkout when safe; create a worktree only for a concrete checkout conflict. Run in parallel, **default cap 3 live workers total across the wave** (see `references/execution-policy.md`); go higher only for a concrete, recorded independence/ownership/capacity reason |
| **B** | Shared crate/module/contract | **SERIAL** — one integration owner coordinates the module on a feature branch/PR. Check whether the base moved before integration, but never auto-rebase or commit, stash, clean, or otherwise disturb another agent's dirty work |
| **C** | Ambiguous or hard-to-reverse judgment/design-intent calls — not routine design already authorized by the plan | **Hold.** Do not dispatch. Surface to human with a recommendation |
| **D** | Suspected bugs | Verify-first track: reproduce before fixing, dispatched **after** cleanup tiers land (the "bug" may be dead code a cleanup deletes) |

Before spawning, record ownership and assigned checkout paths. Create only the
worktrees justified by a concrete conflicting-write risk.

## Step 3: Per-agent briefing

Generate every prompt from this boilerplate — no freehand briefs:

```
Task: <exact scope — issue #, files, symbols. Nothing else.>
Checkout/worktree: <absolute path>. Branch: <name>. All paths must be absolute.
STOP after completing this task. Do not pick up adjacent work, do not
"improve while you're in there", do not start a follow-up.
Forbidden: global cargo fmt / prettier --write . / any repo-wide reformat;
touching files outside your scope; force-push; committing to main.
Commit: brief imperative messages, no Co-Authored-By trailers.
Model: <pinned model id>.
Done means: <the exact target/workload, the command that checks it, and the
observed result — not just "tests pass" or "gate green" with no numbers>.
```

**Always pin the model explicitly.** Never leave model selection floating on an unattended run — the curlit overnight run died 23x because model selection floated instead of being pinned.

## Step 4: Orchestrator duties during the run

Orchestrator owns completion — poll and resume workers via native Orca
(`orca orchestration check --wait`, or Monitor/SendMessage outside Orca) at
≤60s per wait call, never trust a quiet agent to self-report or self-resume
(global CLAUDE.md hard rule). A poll timeout is a checkpoint, not a failure:
re-issue the same wait against the same worker, don't launch a duplicate.

- **One CPU-heavy sweep/test-suite at a time.** Check load (`uptime`) before launching another.
- Verify each assigned checkout and feature branch immediately after dispatch:
  `git -C <assigned-path> branch --show-current`; never dispatch ongoing work
  on `main`.
- Track per-agent status in a simple checklist (issue, tier, owner, checkout,
  state, verified-done).

## Step 5: Integration protocol

- **One integration owner owns the feature branch/PR and all shared-contract
  integration.** Before integrating, check whether the target base moved and
  diff against its current tip. Integrate Tier-B work serially in dependency
  order. A feature branch is not push/merge permission; preserve the existing
  authorization boundary.
- Before merging any two branches, diff their worktrees for duplicate additions (M1 shipped duplicate contract fields):

```bash
git diff <target-base>...branch-a -- <contract files> > /tmp/a.diff
git diff <target-base>...branch-b -- <contract files> > /tmp/b.diff
diff /tmp/a.diff /tmp/b.diff
```

- **Do not integrate a known failure:** reject a false zero-caller deletion,
  resolve an authorized red determinism/test gate or dispatch a scoped repair,
  and preserve any uncommitted state by coordinating ownership or isolating the
  work. Never commit, stash, clean, or rebase another agent's dirty checkout.
  Ask the user only when the remaining choice is blocking, destructive,
  hard-to-reverse, or outside the authorized scope — not for a routine fixable
  test failure.

## Cleanup

After authorized integration, clean up only a worktree created by this run when
it is clean, merged, has no active agent, and cleanup is already authorized.
Never blanket-delete every branch/worktree or clean one with uncommitted work;
audit with `git worktree list` and the repository's actual target branch.

## Quick checklist

1. [ ] API-level overlap grep done; DAG sketched
2. [ ] Every item assigned tier A/B/C/D
3. [ ] Contracts-foundation commit landed (if any B items share types)
4. [ ] Ownership/checkouts recorded; conflict-only worktrees; ≤3 live workers by default
5. [ ] Every brief from boilerplate; model pinned; STOP guardrail present
6. [ ] Polling loop running; branches verified post-dispatch
7. [ ] Integration owner combines shared contracts serially on a feature branch/PR
8. [ ] Tier-D verify-first only after cleanups land; Tier-C sent to human
9. [ ] Only eligible run-owned clean/merged worktrees cleaned up
