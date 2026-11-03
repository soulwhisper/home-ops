---
description: Read-only post-merge verification and close-readiness checks
---

# Cluster verification

Verify a merged fix through Flux and the original failure signal, then determine whether the incident can close. This command is read-only: do not edit files, cluster resources, tickets, or review threads.

## 1. Preconditions

1. Read `skill://homelab-gitops` and `skill://homelab-tickets`. Confirm the merged PR, merge SHA, affected Kustomizations, and `main`/origin state. For ticket operations, use `F="${FORGEJO_URL:-http://nas.homelab.internal:9003}/api/v1/repos/${TICKETS_REPO:-soulwhisper/homelab-tickets}"` and `TOKEN_FILE="${FORGEJO_TOKEN_FILE:-$HOME/forgejo_tickets.key}"`.
2. Do not invoke a new scheduler execution, restart a workload, create a Memory Space, enable a provider, or close a ticket merely to make verification finish. Return `NEEDS_HUMAN` with `resume_stage: VERIFYING` and the exact runtime action. The master may resume only non-disruptive actions through `EXECUTING_APPROVED_PLAN`, and only when an existing merged plan authorizes that action. Workload restarts and other heavy-impact actions require the `homelab-gitops` risk/recovery disclosure plus `ask` and resume through `EXECUTING_HEAVY_PLAN`; a merged plan alone never authorizes them. Verification never performs the action.
3. Keep all queries bounded and redact credentials. Use unique read-only canary arguments and never retry a denied tool call to make it pass.

## 2. Merge and rollout verification

1. Confirm the merge commit is present on a clean, current `main` and note any stale branches without deleting them or pruning refs.
2. Read the GitRepository revision and every affected Flux Kustomization's applied revision, `Ready` condition, rollout status, and non-ready pods. If the merged revision is not applied, report `PENDING_RECONCILE`. If it is applied but not Ready, inspect the condition reason and rollout state: report `PENDING_RECONCILE` only while reconciliation is progressing and `FAIL` for a completed failure; do not annotate or trigger reconciliation.
3. Inspect actual deployed values, not only Git: image tag, environment variables, volume mounts, resource limits, allowlists, ConfigMap/patch revision, and CNP paths/methods.

## 3. Original-signal verification

Use the runbook's `post_merge_verify` contract where present:

- **Holmes**: use either acceptance path: (a) the current ScheduledHealthCheck and child use the expected query/marker and report `pass`, or (b) the underlying condition measurably improved with before/after numbers. Scheduled-run freshness applies only to path (a); do not rerun an old prompt or force a scheduler invocation when path (b) already proves correction. Consumer resolution is separate from either result.
- **MCP tiers**: run `tools/list` plus a small read-only call with unique arguments. A previous denial is not proof of current failure; use the audit reason and current version/config instead of repeated retries.
- **Guardrails**: verify a normal read-only call with a different fingerprint succeeds. An intentionally repeated identical read-only call may be used only when the user explicitly requested the negative test; a different read-only call must still succeed afterward. Do not generate denial traffic during a routine check.
- **Browser**: navigate once to a unique public URL and inspect the snapshot. Do not retry after content-policy denial or switch tools to bypass it.
- **Mnemon**: verify `Home` is the only active conversational mapping, non-home mappings are inactive, Hindsight has no pending/failed operation, and an existing fact can be recalled. Do not create a test memory during a read-only check.
- **Tickets/observation**: Alert tickets require a normal raw condition and consumer `resolved`; Kyverno tickets require the live PolicyReport, before/after remediation evidence, and durable PolicyViolation evidence for 24h after verifying collector/leader and VictoriaLogs health with no collection gaps and intended actors; ScheduledHealthCheck tickets require a clean answer to the same question; config/docs tickets require render/lint/CI evidence and one green reconcile. Silence or an empty alert response is not resolution.

If acceptance is waiting for a current ScheduledHealthCheck result, report `PENDING_SCHEDULED_RUN`. If other evidence is older than the merge or the required observation is incomplete, report `WAIT_OBSERVATION` with `next_check_at`; never report stale evidence as healthy.

## 4. Close-readiness

Classify every incident as exactly one typed result; do not return a generic `PENDING`:

| Result | Required meaning | Master action |
| --- | --- | --- |
| `READY_TO_CLOSE` | Fixed behavior and the finding class's acceptance gate are verified: Alert/Kyverno requires consumer `resolved` plus 24h observation; ScheduledHealthCheck requires a clean answer or measurable before/after correction; config/docs require one green reconcile. | `CLOSE_COMMENT_INTENT` |
| `OUTDATED` | Latest transition is resolved or the old finding no longer matches verified current state. Include the scope-specific reason; verification does not write the outdated marker. | `OUTDATED_COMMENT_INTENT` |
| `PENDING_RECONCILE` | Merged revision is not applied, or reconciliation/rollout is still progressing. Include observed/target revisions and `next_check_at`; an unchanged revision uses fresh rollout-progress evidence. | `PENDING_RECONCILE` |
| `PENDING_SCHEDULED_RUN` | Acceptance requires a current ScheduledHealthCheck result that does not exist yet. Include the next scheduled time; never rerun an old prompt as proof. | `PENDING_SCHEDULED_RUN` |
| `WAIT_OBSERVATION` | Consumer resolution, evidence freshness, or the class-specific observation window is incomplete. Include `next_check_at`. | `WAIT_OBSERVATION` |
| `FAIL` | Original behavior still fails, a regression appeared, evidence contradicts the fix, or reconciliation/rollout completed with failure. | `NEEDS_HUMAN` with `resume_stage: VERIFYING`; no automatic remediation |
| `NEEDS_HUMAN` | Verification prerequisites are missing, or a runtime action needs a plan/human decision. Include the exact action and `resume_stage: VERIFYING`; verification does not perform it. | `NEEDS_HUMAN`; an already approved non-disruptive plan may resume through `EXECUTING_APPROVED_PLAN` |

`cluster-aiops` performs the actual close and lesson steps after these results. Verification itself remains read-only.

Lessons and distilled incident memory in `learnings/` are separate close steps. Do not treat a lesson write as proof that the incident is durable.

## 5. Report contract

Report in Chinese, ordered by severity, with exact timestamps and evidence:

- merge SHA and applied Flux revision;
- deployed config and behavior verification;
- raw condition and consumer-resolution state;
- the exact typed close-readiness result, mapped master state, every remaining blocker, and `resume_stage` or `next_check_at` as applicable;
- next concrete action, without performing it.

No edits, closures, restarts, provider activation, or runtime creation are performed by this command.
