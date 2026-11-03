# homelab-tickets conventions

The ai-ops work queue. Detectors file tickets here; the operator (with the
fixer agent) works them. This file is the law — synced from
`home-ops/infrastructure/forgejo/skills/`, edit there.

## Ticket anatomy

- **Title**: `[SEV] <finding title>`.
- **Body**: source, `aggregation_key`, fingerprint, subject
  (kind/name/namespace), observation and fire/resolve timestamps, and enrichment.
  The consumer's leading incident marker hashes source + alert name + scope
  (namespace/workload/node/container labels, Deployment pod hashes stripped):
  one ticket per alert and affected workload. A rollout's replacement pods
  and a rule-error storm across many rule groups share a ticket. Only
  Alertmanager-sourced findings are ticketed.
- **Comments**: per-instance state transitions (fire, resolve, re-fire) extend
  the incident timeline. Re-notifications of an unchanged state are suppressed; only a new
  failure can reopen a closed ticket. Resolution is evidence, never automatic
  permission to close. The operator may add `flap` when the timeline shows
  repeated transitions.
- **Holmes investigation**: an automated comment on create, and on reopen at
  most once per 6h (root cause, evidence, proposed fix, verification). A
  hypothesis to confirm, not a verdict; absent if Holmes timed out.

## Lifecycle

1. `open` — inbox. Nobody owns it yet.
2. **Claim** — comment `taking` (and assign yourself) before starting work.
   Merge historical duplicates or distinct keys with the same root cause:
   close the losers with a link to the survivor; do not edit consumer markers.
3. **Fix** — change goes to `home-ops` on GitHub as a PR. Public PRs stay
   terse: what + why-in-one-line + ticket number. No incident prose, no
   internal detail — context lives here, not there.
4. **Verify** — prove it per `skills/acceptance.md` for the ticket's class.
5. `closed` — one closing comment: PR link + the verification evidence.

## Fixer rules

- The human merges. Agents propose, never merge.
- Cluster changes are GitOps-first. Runtime mutations are forbidden except for the enumerated, evidence-gated operations in the merged-plan exception below.
- Blast radius beats elegance: prefer the boring, reversible fix.
- **Evidence-gated exception for `cluster-aiops`**: before human merge, the PR body and ticket comment must contain matching post-merge close/learn plans bound to the exact PR head SHA and specifying exact operation, scope, preconditions, verification, and rollback/stop conditions. Human merge of that approved head constitutes approval only for that plan. After merge, the orchestrator reads the actual merge SHA, confirms it is the merge of that PR and approved head, and rechecks the same unchanged, matching plans before every plan-authorized operation, close, or lesson dispatch. Missing, changed, divergent, or wrong-head plans become `NEEDS_HUMAN` without performing the action. The orchestrator may then close and dispatch lessons only after this document's acceptance criteria are met. The same plan may authorize only the enumerated non-disruptive operations: provider activation, Memory Space creation, and production scheduler invocation, each with intent/result records and before/after verification. No merged plan means no automatic close, lesson dispatch, or live operation, and heavy-impact operations still require separate execution-time approval.
