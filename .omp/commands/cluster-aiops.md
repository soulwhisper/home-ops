---
description: Orchestrate diagnosis, PR remediation, verification, closure, and learning from Forgejo tickets with resumable human gates
---

# Cluster aiops

Master the incident loop from a Forgejo ticket. Invoke the other cluster commands by name and persist every intent and result in the ticket. Do not create another state database, runbook set, or control plane.

## 1. Invocation and authority

```text
cluster-aiops run <ticket-number>
cluster-aiops resume <ticket-number>
```

For every Forgejo operation, set `F="${FORGEJO_URL:-http://nas.homelab.internal:9003}/api/v1/repos/${TICKETS_REPO:-soulwhisper/homelab-tickets}"` and `TOKEN_FILE="${FORGEJO_TOKEN_FILE:-$HOME/forgejo_tickets.key}"`; do not hardcode another repository or token path.

- `run` starts only when no active run exists. If one exists, it behaves as `resume`; it never creates a second PR, comment, runtime action, or lesson for the same incident.
- `resume` reads the latest lease, stage, and action records and continues from there. `DONE` is a no-op. An unexpired run owned by another worker returns `ALREADY_RUNNING`.
- Claim with `taking` before new work and read the complete ticket/comment timeline before selecting a stage.
- Human interfaces are limited to **merging a PR** and **handling `NEEDS_HUMAN`**. Do not call `ask` for a known runbook or hide failure behind another approval prompt. Heavy-impact operations still follow `skill://homelab-gitops` and require an explicit risk disclosure plus `ask` as part of `NEEDS_HUMAN`.

Canonical incident state lives in the Forgejo ticket and `learnings/`; no external memory service is used. Any local execution lock is advisory in the supervised model and is never authoritative state.

## 2. Shared lease and action idempotency

### Shared run lease

Start each run with a bounded comment:

```yaml
aiops-run: 01K...
owner: <worker/session-id>
stage: INTAKE
heartbeat_at: <UTC timestamp>
expires_at: <UTC timestamp>
```

- Forgejo serializes individual comment creation, but comment writes and re-reads are not compare-and-swap or fencing. `aiops-run` comments are recovery/ownership records only. In the current supervised model, the human invoking the master must ensure that only one master invocation works a ticket at a time; concurrent invocation is unsupported. After writing the lease, re-read it and continue only if your `run_id` and owner are current. An unexpired different owner returns `ALREADY_RUNNING`. No automated mutual exclusion is claimed.
- A blocked stage is resumable by its existing `run_id`, not a new run. An expired lease may be reclaimed only by resuming that run in a new human-driven invocation after confirming that no other owner is active and checking its last action record; never start over.
- Release the lease on `DONE`. On error or yield, leave accurate stage/heartbeat so another worker can resume rather than duplicate work.

### Intent/result records

Before every external side effect, write an intent record, then perform the action and write its result:

```yaml
aiops-action: <run_id>:<action_id>:<head_or_merge_sha_or_na>
state: intent | done | failed
stage: RECONCILING
external_ref: <PR/comment/lesson path/workflow run/image digest>
```

- `run_id` is mandatory. `action_id` is stable within the run (`open-pr`, `link-pr`, `reconcile`, `verify`, `close-comment`, `close`, `lesson`). Use head SHA before merge, merge SHA afterward, and `na` for a no-PR occurrence; never an empty key.
- On resume, first look for the intent's deterministic marker in the external artifact. If it exists, record `done` without repeating the action. If absent, repeat only a safe idempotent action. Never infer success from intent alone.
- Recover `open-pr` and `link-pr` independently from their exact markers in the PR body and each source-ticket PR-link/plan comment. Adopt and update an existing related unmarked PR instead of duplicating it.
- Scope lookups to the current run, so reopened incidents and new heads are not suppressed by older keys.
- `READY_TO_CLOSE` must become `CLOSE_COMMENT_INTENT` → keyed comment → `CLOSE_COMMENT_WRITTEN` → close-only → `TICKET_CLOSED`. Do not conflate comment creation with ticket closure.

## 3. State machine

| Stage | Master action | Next state |
| --- | --- | --- |
| `INTAKE` | Recall matching tickets and `learnings/`, then invoke `cluster-diagnosis`. | `DIAGNOSED` |
| `DIAGNOSED` needs a fix | Invoke `cluster-remediation` and route the actual result, not an assumed PR. | `REMEDIATION_RESULT` |
| `DIAGNOSED` healthy with merged PR | Do not open another PR. Reconcile if unapplied; otherwise verify. | `RECONCILING` or `VERIFYING` |
| `DIAGNOSED` healthy/outdated without a PR | Do not invent PR/CI work or auto-close without merged-plan approval. Record a stable occurrence key and stop for manual direction. | `NEEDS_HUMAN` |
| `DIAGNOSED` merged but unapplied | Do not open another PR; wait for the merged revision. | `RECONCILING` |
| `DIAGNOSED` no conservative runbook | Record evidence and stop. | `NEEDS_HUMAN` |
| `REMEDIATION_RESULT` PR opened/updated | Verify the `open-pr` and `link-pr` external markers and record their results without repeating either artifact, then run targeted/full tests, prek, CI, and AI review. | `PR_OPEN` |
| `REMEDIATION_RESULT` healthy with merged PR | Do not open another PR; verify whether the merged revision is applied. | `RECONCILING` or `VERIFYING` |
| `REMEDIATION_RESULT` merged but unapplied | Do not open another PR; wait for the merged revision. | `RECONCILING` |
| `REMEDIATION_RESULT` no PR/no merge | Do not invoke post-merge verification or auto-close. Record the occurrence and stop for manual direction. | `NEEDS_HUMAN` |
| `PR_OPEN` | Run targeted/full tests, prek, CI, and AI review. | `CI_GREEN` or `CI_FAILED` |
| `CI_FAILED` | Reproduce and fix valid failures in the same PR; only a new direction or unavailable prerequisite goes to human. | `CI_GREEN` or `NEEDS_HUMAN` |
| `CI_GREEN` | **Before yielding**, require matching head-bound post-merge close/learn plans in both the PR body and ticket comment: exact operation, scope, preconditions, verification, and rollback/stop conditions. Missing/mismatched plans stop. Recheck the merged plan before close and lessons. | `WAIT_UPSTREAM_MERGE` for upstream or `WAIT_HUMAN_MERGE` for home-ops |
| `WAIT_UPSTREAM_MERGE` | After human merge, wait for release-please PR; do not reconcile home-ops. | `WAIT_RELEASE_PR_MERGE` |
| `WAIT_RELEASE_PR_MERGE` | After human merge of release-please, wait for signed multi-arch image publication. | `WAIT_IMAGE_PUBLICATION` |
| `WAIT_IMAGE_PUBLICATION` | Verify published image/digest, then create the home-ops PR. | `PR_OPEN` |
| `WAIT_HUMAN_MERGE` | After user confirms home-ops merge, update `main`, read the actual merge SHA, and confirm it is the merge of this PR and its approved head. Re-read the unchanged, matching head-bound plans and bind subsequent action records to the merge SHA; prune merged branches. Missing, changed, divergent, or wrong-head plans stop. | `RECONCILING` or `NEEDS_HUMAN` |
| `RECONCILING` | Reconcile source plus affected Kustomizations and inspect applied revision/rollout. | `PENDING_RECONCILE`, `EXECUTING_APPROVED_PLAN`, `VERIFYING`, or `NEEDS_HUMAN` on completed failure |
| `PENDING_RECONCILE` | Record next check and yield; never treat as healthy or completed failure. Resume only after new revision evidence. | `RECONCILING` |
| `EXECUTING_APPROVED_PLAN` | Before each non-disruptive operation, recheck the actual merge SHA/approved head and unchanged, matching plans; then check preconditions and execute with intent/result records. Missing, changed, divergent, or wrong-head plans stop. | `VERIFYING` or `NEEDS_HUMAN` on failed precondition/action or invalid approval |
| `VERIFYING` | Invoke `cluster-verification` and route its exact typed result with class-specific evidence. | `CLOSE_COMMENT_INTENT`, `OUTDATED_COMMENT_INTENT`, `PENDING_RECONCILE`, `PENDING_SCHEDULED_RUN`, `WAIT_OBSERVATION`, or `NEEDS_HUMAN` |
| `PENDING_SCHEDULED_RUN` | Record next scheduled time and yield; do not rerun an old prompt or invent a clean result. Resume after the current run. | `VERIFYING` |
| `WAIT_OBSERVATION` | Record `next_check_at` and yield until observation is complete; incomplete evidence loops here, never to success or failure. | `VERIFYING` |
| `CLOSE_COMMENT_INTENT` | Recheck the merged close/learn plan, then write one keyed closing comment with PR/evidence/root cause/timestamp. | `CLOSE_COMMENT_WRITTEN` |
| `OUTDATED_COMMENT_INTENT` | Write `<!-- aiops-outdated -->` plus the exact `<!-- aiops-action:<run_id>:<action_id>:<sha> -->` marker and a scope-specific reason. Recovery requires that exact action marker. | `CLOSE_COMMENT_WRITTEN` |
| `CLOSE_COMMENT_WRITTEN` | Close only after the exact keyed comment exists and the latest consumer event has not refired the incident. A refire supersedes the run and stops for human review. If already closed externally, skip only the close API mutation; learning still requires an already verified `TICKET_CLOSED` or rechecked merged-plan authorization and class-specific verification/refire checks. | `TICKET_CLOSING` or `NEEDS_HUMAN` on refire, otherwise `TICKET_CLOSED` |
| `TICKET_CLOSING` | Confirm closed state and recheck that no newer firing event superseded verification. | `TICKET_CLOSED` or `NEEDS_HUMAN` on refire |
| `TICKET_CLOSED` new root cause | Pass the full `aiops-action` key and `run_id` to the lessons workflow, record its workflow run ID, and verify a lesson containing that key in frontmatter. | `LESSON_CREATED` or `LEARN_PENDING` |
| `TICKET_CLOSED` recurrence | Add a keyed recurrence comment on the existing lesson's source ticket; skip new-file dispatch. | `LESSON_CREATED` |
| `TICKET_CLOSED` no reusable lesson | Persist successful `NO_LESSON`/`LESSON_SKIPPED` with the action key and workflow run ID; do not redispatch. | `DONE` |
| `LESSON_CREATED` | Verify the keyed lesson or recurrence comment is included in subsequent recall, then release the lease. | `DONE` or `LEARN_PENDING` on missing evidence |
| `LEARN_PENDING` | Resume only the missing lesson step; `NO_LESSON` transitions to `DONE`, other missing evidence resumes dispatch/checks. Never duplicate close or comments. | `LESSON_CREATED`, `DONE`, or `LEARN_PENDING` |
| `NEEDS_HUMAN` | Record `resume_stage` and the exact human decision. For `no_recommendation`, invoke `cluster-remediation` with the recorded human-selected direction and route its typed result through `REMEDIATION_RESULT`. Other resolved prerequisites resume at their recorded stage; an already approved non-disruptive action resumes through `EXECUTING_APPROVED_PLAN` after its plan recheck; a heavy action goes to `EXECUTING_HEAVY_PLAN` only after explicit approval; a human-performed action goes to `VERIFYING`. No automatic remediation. | `REMEDIATION_RESULT`, recorded `resume_stage`, `EXECUTING_APPROVED_PLAN`, `EXECUTING_HEAVY_PLAN`, or `VERIFYING` |
| `EXECUTING_HEAVY_PLAN` | Only after the `homelab-gitops` risk/recovery disclosure and `ask` confirmation, execute with intent/result records and the documented stop condition. | `VERIFYING` or `NEEDS_HUMAN` on failure/stop |

`READY_TO_CLOSE` requires the finding class's acceptance: Alert/Kyverno observation, a clean answer for ScheduledHealthCheck **or measurable before/after correction of the underlying condition**, or one green reconcile for config/docs. Do not force a scheduler invocation when the underlying-condition path already proves correction.

## 4. Human gates and approvals

- `WAIT_UPSTREAM_MERGE`, `WAIT_RELEASE_PR_MERGE`, and `WAIT_HUMAN_MERGE` stop with PR URL/head SHA. Do not merge, enable auto-merge, poll, or create another PR. After the relevant human merge, resume only the next stage.
- `NEEDS_HUMAN` is terminal blocked: no runbook, verification failure/regression, observation failure, conflicting evidence, missing prerequisite, unapproved live operation, or a newer firing event superseding verification. Record bounded evidence and stop without retrying or changing the fix. Its `resume_stage` and human decision are mandatory before continuing.
- Provider activation, Memory Space creation, scheduler invocation, and similar **non-disruptive** operations require the exact operation, scope, preconditions, verification, and rollback/stop condition in both the PR body and ticket comment before merge. If settings already match and there is no PR to merge, that case is unapproved and becomes `NEEDS_HUMAN`; do not invent approval.
- Node reboots, workload deletion/restart, force-delete, storage deletion, rollback, purge/restore, and other heavy-impact or service-breaking actions always become `NEEDS_HUMAN` with the `homelab-gitops` risk/recovery disclosure and `ask`. A PR merge alone never authorizes them.
- Evidence-gated operations, closure, and lessons dispatch are allowed only within the merged PR's explicit close/learn plan and the `infrastructure/forgejo` acceptance rules. Immediately before every plan-authorized operation, close, or lesson dispatch, confirm that the actual merge SHA is the merge of the approved PR head and that both unchanged plans still match that head. Missing, changed, divergent, or wrong-head plans become `NEEDS_HUMAN`. This preserves human control through the merged plan rather than an autonomous close.

## 5. Close and learn

- `READY_TO_CLOSE` follows the finding class's acceptance evidence; `OUTDATED` uses a marker and reason rather than a fixed claim.
- Generate one distilled lesson per distinct root cause in `learnings/`. A recurrence gets a keyed comment on the existing lesson's source ticket, not another file.
- `learnings/` is the sole long-term memory and recall source; no external memory service is used. Retain facts only: root cause, fix PR, verification query, and recurrence cue.
- Before resumed close or learning, compare issue state and the latest consumer event with the verified occurrence. A newer firing event supersedes the old run. External closure skips only the close API mutation: resume unfinished learning directly only from an already verified `TICKET_CLOSED`; otherwise recheck merged-plan authorization and invoke `cluster-verification` for class-specific acceptance and refire checks. Missing plan/merge metadata becomes `NEEDS_HUMAN`; incomplete evidence remains in verification or observation.
- The next `cluster-diagnosis` must recall matching tickets and `learnings/` before proposing another fix.

## 6. Report contract

Report in Chinese with ticket, `run_id`, stage, runbook, PR head/merge SHA, Flux revision, action idempotency key, evidence, and next state. Distinguish blocked on upstream/home-ops merge, observation, `NEEDS_HUMAN`, and learning. Record close/lesson state and every idempotency skip.

Never claim completion from PR creation, Pod readiness, an empty alert result, a quiet stream, or an intent record without the matching external artifact.
