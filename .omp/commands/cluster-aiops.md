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
- `resume` reads the latest lease, stage, and action records and continues from there. `DONE` and `HUMAN_MANAGED` are no-op terminal states. An unexpired run owned by another worker returns `ALREADY_RUNNING`.
- Claim with `taking` before new work and read the complete ticket/comment timeline before selecting a stage.
- Human interfaces are limited to **merging a PR** and **handling `NEEDS_HUMAN`**. Do not call `ask` for a known runbook or hide failure behind another approval prompt. Heavy-impact operations still follow `skill://homelab-gitops` and require an explicit risk disclosure plus `ask` as part of `NEEDS_HUMAN`.

Canonical incident state lives in the Forgejo ticket and the `homelab-tickets` repo's `learnings/`; no external memory service is used. Any local execution lock is advisory in the supervised model and is never authoritative state.

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
dispatch_state: not_sent | dispatching | unknown | accepted | rejected | done  # lesson dispatch only
supersedes: <previous workflow run ID with status failure/cancelled, when authorized>
dispatch_deadline: <UTC deadline for an accepted run to become discoverable>
execution_deadline: <UTC deadline for an adopted nonterminal run to finish or produce a valid artifact>
rejection_evidence: <bounded definitive response or independent human-verified non-creation evidence>
```

- `run_id` is mandatory and must be a canonical 26-character ULID whose first character is `0`–`7`. `action_id` is stable within the run (`open-pr`, `link-pr`, `reconcile`, `verify`, `close-comment`, `close`, `lesson`). Use head SHA before merge, merge SHA afterward, and `na` for a no-PR occurrence; never an empty key.
- For lesson dispatch, create the intent with `dispatch_state: not_sent`, then append `dispatching` immediately before the API call. Record `accepted` only when Forgejo accepts creation, `rejected` only when the response definitively says no run was created, and `unknown` on timeout/unknown outcome. A crash after `dispatching` without `accepted` is `unknown` on resume. Artifact verification sets both `state: done` and `dispatch_state: done`. Only `not_sent` or `rejected` may start the initial dispatch; `accepted` never implies lesson completion. Record any human-authorized same-key retry with `supersedes` and a new `not_sent` transition.
- On `accepted`, record `next_check_at` and a bounded `dispatch_deadline`. Zero matches before that deadline means `LEARN_PENDING`, not failure or permission to redispatch; after the deadline it becomes `NEEDS_HUMAN` with `resume_stage: LEARN_PENDING`. For `unknown` with zero matches, a human may record `rejected` only with independent evidence that no run was created, preserved in `rejection_evidence`; zero matches alone never qualifies. Resume that human decision through `LEARN_PENDING`, then dispatch from `rejected`/`not_sent` without inventing a superseded run ID.
- Once a run is discovered, a nonterminal `run.status` requires `next_check_at` and a bounded `execution_deadline`. Expiry becomes `NEEDS_HUMAN` with the run ID, current status, and bounded diagnostic evidence. Before resuming, first recheck status and artifacts: terminal runs or valid artifacts follow the normal completion paths. Any other return to `LEARN_PENDING` after expiry, including runner repair or an explicitly extended wait, must record fresh `next_check_at` and a new bounded `execution_deadline`. A human may alternatively cancel the run and use the existing failure/cancelled supersession path when no valid artifact exists. The master never cancels a run automatically.
- On resume, first look for the intent's deterministic marker in the external artifact. If it exists, record `done` without repeating the action. If absent, repeat only a safe idempotent action. Never infer success from intent alone.
- Recover `open-pr` and `link-pr` independently from their exact markers in the PR body and each source-ticket PR-link/plan comment. Adopt and update an existing related unmarked PR instead of duplicating it.
- Before any lesson redispatch, paginate `$F/actions/runs` and decode each `event_payload`; exact-match `workflow_id: lessons.yml`, `prettyref: main` (or payload `ref: refs/heads/main`), and the dispatch inputs `ticket`, `run_id`, and `action_key`. Adopt one matched run ID and inspect `actions/runs/<id>/jobs` or `actions/jobs/<job>/logs` only for diagnosis. Multiple matches are valid only when every earlier attempt has `run.status` of `failure` or `cancelled` and is recorded as superseded; adopt the latest human-authorized attempt. Any other multiple or undecodable/mismatched identity is ambiguous.
- A normal lesson is complete when its pushed Git frontmatter contains both the exact `aiops_action` and `aiops_run`; `NO_LESSON` is complete when one source-ticket comment contains `<!-- aiops-no-lesson -->`, the exact action marker, the exact `aiops_run: <RUN_ID>` line, and `aiops_workflow_run: <WORKFLOW_RUN_ID>`, with `comment.user.id == run.trigger_user.id` and `comment.created_at` between the run's `created` and `stopped` timestamps (when `stopped` is nonzero). These artifacts remain valid even if a later unrelated workflow step failed; record the run ID and `run.status` as evidence. A run whose `run.status` is `failure` or `cancelled` and which has no valid artifact becomes `NEEDS_HUMAN` with `resume_stage: LEARN_PENDING`; only an explicit human decision may authorize a same-key retry and record the earlier run as superseded. Unknown or ambiguous dispatch identity follows the same human state; zero matches after a timeout/unknown response is not proof of non-creation and must not trigger redispatch.
- Scope lookups to the current run, so reopened incidents and new heads are not suppressed by older keys.
- `READY_TO_CLOSE` must become `CLOSE_COMMENT_INTENT` → keyed comment → `CLOSE_COMMENT_WRITTEN` → close-only → `TICKET_CLOSED`. Do not conflate comment creation with ticket closure.

## 3. State machine

| Stage | Master action | Next state |
| --- | --- | --- |
| `INTAKE` | Recall matching tickets and the tickets repo's `learnings/`, then invoke `cluster-diagnosis`. | `DIAGNOSED` |
| `DIAGNOSED` needs a new fix with no corresponding open or merged PR | Invoke `cluster-remediation` and route the actual result, not an assumed PR. | `REMEDIATION_RESULT` |
| `DIAGNOSED` with a corresponding open PR | Invoke `cluster-remediation` with the existing-PR evidence to adopt/update its current head, exact `open-pr`/`link-pr` markers, and plans instead of creating another PR or selecting a terminal; route its typed result. | `REMEDIATION_RESULT` |
| `DIAGNOSED` with a corresponding merged PR | Do not open another PR. Reconcile if unapplied; otherwise verify current behavior, including active or drifted findings. | `RECONCILING` or `VERIFYING` |
| `DIAGNOSED` healthy/outdated without a corresponding open or merged PR | Do not invent PR/CI work or auto-close without merged-plan approval. Record a stable occurrence key, `na` action key, evidence, and reason, then release the lease. | `HUMAN_MANAGED` |
| `DIAGNOSED` active finding with no conservative runbook and no corresponding open or merged PR | Record evidence and stop for the human direction decision; healthy/outdated findings always use `HUMAN_MANAGED`, even without a runbook. | `NEEDS_HUMAN` |
| `REMEDIATION_RESULT` PR opened/updated | Verify the `open-pr` and `link-pr` external markers and record their results without repeating either artifact, then run targeted/full tests, prek, CI, and AI review. | `PR_OPEN` |
| `REMEDIATION_RESULT` with a corresponding merged PR | Do not open another PR. Reconcile if unapplied; otherwise verify current behavior, including active or drifted findings. | `RECONCILING` or `VERIFYING` |
| `REMEDIATION_RESULT` `HUMAN_MANAGED` | Record the stable occurrence key, `na` action key, evidence, and reason, then release the lease. Do not invoke post-merge verification, close, lessons, or runtime mutation. | `HUMAN_MANAGED` |
| `REMEDIATION_RESULT` `NEEDS_HUMAN` | Preserve the returned `resume_stage`, exact decision/prerequisite, and options; do not release the lease or convert this resumable result into a terminal state. | `NEEDS_HUMAN` |
| `PR_OPEN` | Run targeted/full tests, prek, CI, and AI review. | `CI_GREEN` or `CI_FAILED` |
| `CI_FAILED` | Invoke `cluster-remediation` with the validated failure and its conservative `runbook_id`, or the recorded human-selected direction when no runbook applies. Unsupported failures become `NEEDS_HUMAN` with `resume_stage: CI_FAILED` instead of forcing an unrelated runbook. Route a remediation result through `REMEDIATION_RESULT` for new-head markers, plans, CI, and AI review. | `REMEDIATION_RESULT` or `NEEDS_HUMAN` |
| `CI_GREEN` | **Before yielding**, require matching head-bound post-merge close/learn plans in both the PR body and ticket comment: exact operation, scope, preconditions, verification, and rollback/stop conditions. Missing/mismatched plans stop. Recheck the merged plan before close and lessons. | `WAIT_UPSTREAM_MERGE` for upstream or `WAIT_HUMAN_MERGE` for home-ops |
| `WAIT_UPSTREAM_MERGE` | After human merge, wait for release-please PR; do not reconcile home-ops. | `WAIT_RELEASE_PR_MERGE` |
| `WAIT_RELEASE_PR_MERGE` | After human merge of release-please, wait for signed multi-arch image publication. | `WAIT_IMAGE_PUBLICATION` |
| `WAIT_IMAGE_PUBLICATION` | Verify the published image/digest, then invoke `cluster-remediation` with that evidence for the home-ops bump and route its typed result. | `REMEDIATION_RESULT` |
| `WAIT_HUMAN_MERGE` | After user confirms home-ops merge, update `main`, read the actual merge SHA, and confirm it is the merge of this PR and its approved head. Re-read the unchanged, matching head-bound plans and bind subsequent action records to the merge SHA; prune merged branches. Missing, changed, divergent, or wrong-head plans stop. | `RECONCILING` or `NEEDS_HUMAN` |
| `RECONCILING` | Reconcile source plus affected Kustomizations and inspect applied revision/rollout. | `PENDING_RECONCILE`, `EXECUTING_APPROVED_PLAN`, `VERIFYING`, or `NEEDS_HUMAN` on completed failure |
| `PENDING_RECONCILE` | Record `next_check_at` plus target/applied revisions and yield; never treat as healthy or completed failure. For an unapplied merged revision, resume after new revision evidence. For an in-progress rollout, resume at `next_check_at` with fresh rollout-progress evidence even when the revision is unchanged. | `RECONCILING` |
| `EXECUTING_APPROVED_PLAN` | Before each non-disruptive operation, recheck the actual merge SHA/approved head and unchanged, matching plans; then check preconditions and execute with intent/result records. Missing, changed, divergent, or wrong-head plans stop. | `VERIFYING` or `NEEDS_HUMAN` on failed precondition/action or invalid approval |
| `VERIFYING` | Invoke `cluster-verification` and route its exact typed result with class-specific evidence. | `CLOSE_COMMENT_INTENT`, `OUTDATED_COMMENT_INTENT`, `PENDING_RECONCILE`, `PENDING_SCHEDULED_RUN`, `WAIT_OBSERVATION`, or `NEEDS_HUMAN` |
| `PENDING_SCHEDULED_RUN` | Record next scheduled time and yield; do not rerun an old prompt or invent a clean result. Resume after the current run. | `VERIFYING` |
| `WAIT_OBSERVATION` | Record `next_check_at` and yield until observation is complete; incomplete evidence loops here, never to success or failure. | `VERIFYING` |
| `CLOSE_COMMENT_INTENT` | Recheck the merged close/learn plan, then write one keyed closing comment with PR/evidence/root cause/timestamp. | `CLOSE_COMMENT_WRITTEN` |
| `OUTDATED_COMMENT_INTENT` | Write `<!-- aiops-outdated -->` plus the exact `<!-- aiops-action:<run_id>:<action_id>:<sha> -->` marker and a scope-specific reason. Recovery requires that exact action marker. | `CLOSE_COMMENT_WRITTEN` |
| `CLOSE_COMMENT_WRITTEN` | Close only after the exact keyed comment exists and the latest consumer event has not refired the incident. A refire supersedes the run and stops for human review. If already closed externally, skip only the close API mutation; learning still requires an already verified `TICKET_CLOSED` or rechecked merged-plan authorization and class-specific verification/refire checks. | `TICKET_CLOSING` or `NEEDS_HUMAN` on refire, otherwise `TICKET_CLOSED` |
| `TICKET_CLOSING` | Confirm closed state and recheck that no newer firing event superseded verification. | `TICKET_CLOSED` or `NEEDS_HUMAN` on refire |
| `TICKET_CLOSED` new root cause | First adopt the original workflow run by its exact dispatch inputs. Persist `not_sent → dispatching → accepted/rejected/unknown` for every dispatch. Start only from `not_sent`/`rejected`, or from a human-authorized same-key retry after an attempt whose `run.status` is `failure` or `cancelled` and which produced no valid artifact; a crash after `dispatching` without `accepted` is `unknown`, and zero matches cannot change that decision. Record and supersede earlier run IDs, then verify exact `aiops_action` and `aiops_run` in pushed lesson frontmatter or all four keyed `NO_LESSON` comment fields and their run-bound author/time metadata. | `LESSON_CREATED`, `DONE`, `LEARN_PENDING`, or `NEEDS_HUMAN` |
| `TICKET_CLOSED` recurrence | Add a keyed recurrence comment on the existing lesson's source ticket; skip new-file dispatch. | `LESSON_CREATED` |
| `TICKET_CLOSED` no reusable lesson | Adopt the original workflow run and verify one source-ticket comment containing `<!-- aiops-no-lesson -->`, the exact `aiops-action` marker, exact `aiops_run` and `aiops_workflow_run` lines, `comment.user.id == run.trigger_user.id`, and `comment.created_at` within that run's lifetime. Persist `NO_LESSON`/`LESSON_SKIPPED` with the action key, workflow run ID, and `run.status`; a later unrelated step failure does not invalidate the comment. Do not redispatch or treat it as long-term lesson content. | `DONE` |
| `LESSON_CREATED` | Verify the keyed lesson or recurrence comment is included in subsequent recall, then release the lease. | `DONE` or `LEARN_PENDING` on missing evidence |
| `LEARN_PENDING` | Recover using the persisted `dispatch_state` and original workflow/artifact identity. Exact `aiops_action` and `aiops_run` lesson frontmatter or a recurrence comment leads to `LESSON_CREATED`; all four keyed source-ticket `NO_LESSON` comment fields and their run-bound author/time metadata lead to `DONE`, even if a later unrelated step failed. `accepted` with zero matches remains pending only until `dispatch_deadline`, with `next_check_at`; after the deadline it becomes `NEEDS_HUMAN`. An adopted nonterminal run remains pending only until `execution_deadline` with fresh `next_check_at` and `run.status`; expiry becomes `NEEDS_HUMAN` with bounded diagnostics. A run with `run.status` of `failure` or `cancelled` and no valid artifact, or an `unknown`/ambiguous dispatch, also becomes `NEEDS_HUMAN` with `resume_stage: LEARN_PENDING`. Only `not_sent`/`rejected` may start an initial dispatch; a human-authorized same-key retry writes a new `not_sent` with `supersedes`. Zero matches after `dispatching`/`unknown`/`accepted` cannot authorize redispatch. | `LESSON_CREATED`, `DONE`, `LEARN_PENDING`, or `NEEDS_HUMAN` |
| `NEEDS_HUMAN` | Record `resume_stage` and the exact human decision. For `no_recommendation`, invoke `cluster-remediation` with the recorded human-selected direction and route its typed result through `REMEDIATION_RESULT`. For `unknown` dispatch, independent human-verified non-creation evidence records `rejected` plus `rejection_evidence` and resumes `LEARN_PENDING`; zero matches alone is insufficient. For `accepted` discovery deadline expiry, first recheck `actions/runs` and artifacts and adopt anything now present. To continue waiting, a human must record fresh `next_check_at` and a new bounded `dispatch_deadline`; independent non-creation evidence follows the `rejected` route above, while zero matches alone never authorizes redispatch. For `execution_deadline` expiry, first recheck status and artifacts; terminal runs or valid artifacts follow completion, while every other runner-repair or extended-wait resume through `LEARN_PENDING` requires fresh `next_check_at` and a new bounded `execution_deadline`. Human cancellation without a valid artifact follows the failure/cancelled supersession path. Other resolved prerequisites resume at their recorded stage; an already approved non-disruptive action resumes through `EXECUTING_APPROVED_PLAN` after its plan recheck; a heavy action goes to `EXECUTING_HEAVY_PLAN` only after explicit approval. A human-performed action with a corresponding merged PR goes to `VERIFYING`; without one, record the outcome as `HUMAN_MANAGED` rather than invoking merged-PR verification. No automatic remediation. | `REMEDIATION_RESULT`, recorded `resume_stage`, `EXECUTING_APPROVED_PLAN`, `EXECUTING_HEAVY_PLAN`, `VERIFYING`, or `HUMAN_MANAGED` |
| `HUMAN_MANAGED` | Terminal state for no-PR occurrences outside merged-plan authority. Record the stable occurrence key, `na` action key, evidence, and reason; release the lease. The master performs no close, lesson dispatch, or runtime mutation, and resume is a no-op. This is not `DONE`. | `HUMAN_MANAGED` |
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
- Generate one distilled lesson per distinct root cause in the `homelab-tickets` repo's `learnings/`. A recurrence gets a keyed comment on the existing lesson's source ticket, not another file.
- The tickets repo's `learnings/` is the sole long-term memory and recall source; no external memory service is used. Retain facts only: root cause, fix PR, verification query, and recurrence cue.
- Before resumed close or learning, compare issue state and the latest consumer event with the verified occurrence. A newer firing event supersedes the old run. External closure skips only the close API mutation: resume unfinished learning directly only from an already verified `TICKET_CLOSED`; otherwise recheck merged-plan authorization and invoke `cluster-verification` for class-specific acceptance and refire checks. Missing plan/merge metadata becomes `NEEDS_HUMAN`; incomplete evidence remains in verification or observation.
- The next `cluster-diagnosis` must recall matching tickets and the tickets repo's `learnings/` before proposing another fix.

## 6. Report contract

Report in Chinese with ticket, `run_id`, stage, runbook, PR head/merge SHA, Flux revision, action idempotency key, evidence, and next state. Distinguish blocked on upstream/home-ops merge, observation, `NEEDS_HUMAN`, learning, and terminal `HUMAN_MANAGED`. Record close/lesson state and every idempotency skip.

Never claim completion from PR creation, Pod readiness, an empty alert result, a quiet stream, or an intent record without the matching external artifact.
