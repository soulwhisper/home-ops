---
description: Read-only post-merge verification and close-readiness checks
---

# Cluster verification

Verify a merged fix through Flux and the original failure signal, then determine whether the incident can close. This command is read-only: do not edit files, cluster resources, tickets, or review threads.

## 1. Preconditions

1. Read `skill://homelab-gitops` and `skill://homelab-tickets`. Confirm the merged PR, merge SHA, affected Kustomizations, and `main`/origin state. For ticket operations, use `F="${FORGEJO_URL:-http://nas.homelab.internal:9003}/api/v1/repos/${TICKETS_REPO:-soulwhisper/homelab-tickets}"` and `TOKEN_FILE="${FORGEJO_TOKEN_FILE:-$HOME/forgejo_tickets.key}"`.
2. Do not invoke a new scheduler execution, restart a workload, create a Memory Space, enable a provider, or close a ticket merely to make verification finish. Those actions need explicit user instruction and are not implied by `cluster-verification`.
3. Keep all queries bounded and redact credentials. Use unique read-only canary arguments and never retry a denied tool call to make it pass.

## 2. Merge and rollout verification

1. Confirm the merge commit is present on a clean, current `main` and note any stale branches without deleting them or pruning refs.
2. Read the GitRepository revision and every affected Flux Kustomization's applied revision, `Ready` condition, rollout status, and non-ready pods. If the merged revision is not applied, report `PENDING_RECONCILE`. If it is applied but not Ready, inspect the condition reason and rollout state: report `PENDING` only while reconciliation is progressing and `FAIL` for a completed failure; do not annotate or trigger reconciliation.
3. Inspect actual deployed values, not only Git: image tag, environment variables, volume mounts, resource limits, allowlists, ConfigMap/patch revision, and CNP paths/methods.

## 3. Original-signal verification

Use the runbook's `post_merge_verify` contract where present:

- **Holmes**: use either acceptance path: (a) the current ScheduledHealthCheck and child use the expected query/marker and report `pass`, or (b) the underlying condition measurably improved with before/after numbers. Scheduled-run freshness applies only to path (a); do not rerun an old prompt or force a scheduler invocation when path (b) already proves correction. Consumer resolution is separate from either result.
- **MCP tiers**: run `tools/list` plus a small read-only call with unique arguments. A previous denial is not proof of current failure; use the audit reason and current version/config instead of repeated retries.
- **Guardrails**: verify a normal read-only call with a different fingerprint succeeds. An intentionally repeated identical read-only call may be used only when the user explicitly requested the negative test; a different read-only call must still succeed afterward. Do not generate denial traffic during a routine check.
- **Browser**: navigate once to a unique public URL and inspect the snapshot. Do not retry after content-policy denial or switch tools to bypass it.
- **Mnemon**: verify `Home` is the only active conversational mapping, non-home mappings are inactive, Hindsight has no pending/failed operation, and an existing fact can be recalled. Do not create a test memory during a read-only check.
- **Tickets/observation**: Alert tickets require a normal raw condition and consumer `resolved`; Kyverno tickets require the live PolicyReport, before/after remediation evidence, and durable PolicyViolation evidence for 24h after verifying collector/leader and VictoriaLogs health with no collection gaps and intended actors; ScheduledHealthCheck tickets require a clean answer to the same question; config/docs tickets require render/lint/CI evidence and one green reconcile. Silence or an empty alert response is not resolution.

If the current evidence is older than the merge or scheduled run, report it as pending rather than healthy.

## 4. Close-readiness

Classify every incident as `READY_TO_CLOSE`, `OUTDATED`, `PENDING`, or `FAIL`:

- `READY_TO_CLOSE`: fixed behavior verified and the finding class's acceptance gate is met: Alert/Kyverno requires consumer `resolved` plus 24h observation; ScheduledHealthCheck requires a clean answer to the same question or measurable before/after correction of the underlying condition; config/docs require one green reconcile.
- `OUTDATED`: latest transition is resolved or the old finding no longer matches verified current state. An outdated close still needs a marker and reason; this command only reports it.
- `PENDING`: merge/reconcile/scheduled run/consumer resolution/class-specific observation is incomplete, or a runtime action needs explicit user instruction.
- `FAIL`: the original behavior still fails, a regression appeared, or evidence contradicts the fix. Report `FAIL` and stop; `cluster-aiops` maps this to `NEEDS_HUMAN` and never invokes automatic remediation.

`cluster-aiops` performs the actual close and lesson steps after these gates. Verification itself remains read-only.

Lessons and distilled incident memory in `learnings/` are separate close steps. Do not treat a lesson write as proof that the incident is durable.

## 5. Report contract

Report in Chinese, ordered by severity, with exact timestamps and evidence:

- merge SHA and applied Flux revision;
- deployed config and behavior verification;
- raw condition and consumer-resolution state;
- close-readiness and every remaining blocker;
- next concrete action, without performing it.

No edits, closures, restarts, provider activation, or runtime creation are performed by this command.
