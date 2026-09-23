# Execution policy (canonical)

Shared defaults for `tiered-fanout`, `session-archaeology`,
`astra-orchestration`, and the `orchestration` stub. Upstream Superpowers
skills stay unmodified; user guidance makes this file authoritative when their
SDD/planning/review advice conflicts.

## Milestone scope

Use one measurable milestone per thread/run. A materially different objective
gets fresh context containing only the accepted plan plus a short
decisions/results delta, not full history. Continue authorized work without
re-asking routine execution choices. Do not add handoff docs when the plan is
enough or automatically start adjacent work.

## Multi-agent use and settlement

Keep small bounded work direct/inline. When fan-out is justified:

- Cap the supervised wave at **3 live, truly independent workers total**;
  planners, reviewers, and in-scope research all count.
- Land shared foundations before dependent waves.
- Expansion above 3 is allowed only for a concrete, recorded reason
  (independence, ownership, or capacity) — never as an arbitrary hard ceiling
  or an arbitrary default.
- Queue remaining ready work. Prefer native Orca; the coordinator delegates
  and reviews but does not edit.
- On settlement, reuse the exact terminal with new Task/Dispatch IDs only when
  an immediate related ready task is queued; otherwise release it. Retain only
  by explicit user request. A later replacement receives the compact accepted
  plan, relevant diff, and verified finding.

## Review depth and ownership

Review meaningful deliverables/diffs/shared surfaces, not every microstep.
Default to one initial review, then one scoped repair/re-review only when a
finding exists. Further rounds require evidence of a still-unresolved
acceptance failure or new regression; never mandate 3/5 rounds or loop “until
green.” Required tests and independent cross-family review still apply for
nontrivial work.

Normal cleanup must not leave an implementer idle through review. Reviewers are
independent and cold-started. The routing table's required reviewer set is
authoritative; workers must not launch unplanned duplicates beyond it.

## Acceptance evidence

State the baseline when comparative, exact target/workload,
command/environment/build, observed result, and caveats. A partial sample does
not verify a larger brief; status remains partial/failed until the target is
met. A file, sum, or green summary line alone is not proof. Re-run what changed,
failed, or remains unresolved without weakening required suites. Record compact
delta evidence in the project's `.codex/` (or equivalent) ledger.

## Integration ownership

One integration owner per feature branch/PR checks whether the target base
moved. Never auto-rebase a dirty tree; commit, stash, clean, or disturb another
agent's state; delete an active worktree; or merge straight to main. A branch/PR
is not push/merge permission. Disjoint ownership may share a checkout; isolate
only on a concrete conflict.

Clean up only a run-owned worktree that is clean, merged, inactive, and already
authorized. Never blanket-clean or turn a fixable test failure into a routine
human gate: resolve authorized failures or dispatch repair, and ask only for a
blocking decision or destructive/out-of-scope action.

A shared browser, profiler, CPU-heavy job, or other live environment gets one
owner. Verify fixtures against the relevant live state.

## Operational discipline

- Load `orca skills get orchestration` compactly; fetch a reference only for
  the command surface needed.
- Process and ACK the entire delivered batch before polling. Worker checkpoints
  use `check --terminal <live_handle>` and ACK the returned whole Delivery with
  its current ID; at completion, continue until the checkpoint is empty.
- After a timed-out question, use `ask --resume <returned_message_id>` with the
  exact live-preamble authority; never recreate it or use stale IDs.
- Keep waits at **≤60 seconds per call**. A timeout is a checkpoint: preserve
  session/exec IDs, resume the same operation, and never duplicate or stop a
  live/unverifiable worker on silence.
- Report tokens only when known; `unknown` is valid.

## No new gates, no savings claims

Do not add approval gates or bypass authorization/safety rules. Do not claim
token/time savings from this policy; none has been measured.
