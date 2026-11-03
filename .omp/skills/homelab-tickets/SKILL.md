---
name: homelab-tickets
description: Use whenever the request involves ai-ops tickets — checking, triaging or working Forgejo homelab-tickets issues, fixing/verifying/closing an incident, writing a lesson (learnings/), or recalling incident memory from Forgejo. Trigger for "check tickets", "work the ticket queue", "what's open in homelab-tickets", "close #N", "write the lesson", "did we see this before".
---

# homelab-tickets: check → fix → verify → learn → remember

The ai-ops work queue lives in `${TICKETS_REPO:-soulwhisper/homelab-tickets}` on
`${FORGEJO_URL:-http://nas.homelab.internal:9003}` (intranet-only, plain HTTP, public repo —
both accepted). The **law** for tickets is `infrastructure/forgejo/skills/` in
this repo — read `README.md` (anatomy, lifecycle) and `acceptance.md`
(per-class verification bar) locally before working a ticket. The tickets
repo holds a synced copy (`just forgejo sync`) for its own workflows; if the
two differ, this repo is authoritative and the copy is stale. This skill is
the operator procedure; on conflict, the law wins.

Pair with `homelab-gitops` for every cluster read/change.

## Pipeline facts (don't rediscover)

- Alertmanager → Robusta → `webhook-relay` route `robusta-tickets`
  (MEDIUM/HIGH; `warning` alerts arrive as HIGH via `custom_severity_map`) →
  serialized consumer
  (`kubernetes/apps/monitoring-system/webhook-relay/app/ticket_consumer.py`).
- **One issue per alert + affected workload**: first body line is
  `<!-- aiops-incident:<sha256(source, alertname, scope)> -->`, where scope is
  the namespace/workload/node/container labels with Deployment pod hashes
  stripped. A rollout's new pods and a rule-error storm across many rule
  groups land on the same ticket. Never edit or remove the marker.
- Only Alertmanager-sourced (`PROMETHEUS`) findings are ticketed; Robusta's
  builtin OOM/CrashLoop/ImagePull/Evicted findings go to Feishu only.
- **Comments** are per-instance state transitions (fire / resolve /
  re-fire). 12h re-notifications of the same state are suppressed. A new
  failure reopens a closed issue; a resolution never closes one.
- **Holmes** posts a `**Holmes investigation**` comment (marker
  `<!-- aiops-holmes -->`) on create, and on reopen at most once per 6h. It is
  a hypothesis: confirm its evidence yourself; it may be absent if Holmes
  timed out.
- Labels in the repo: none by default. Only add `flap` (repeated transitions)
  — don't invent a taxonomy.

## 1. Check the queue

Reads need no token (public repo):

```bash
F="${FORGEJO_URL:-http://nas.homelab.internal:9003}/api/v1/repos/${TICKETS_REPO:-soulwhisper/homelab-tickets}"
# paginate: Forgejo caps pages at 50; loop until a short page
for p in $(seq 1 100); do
  page=$(curl -fsS "$F/issues?state=open&type=issues&limit=50&page=$p")
  echo "$page" | jq -r '.[] | [.number, .updated_at[:16], .comments, .title] | @tsv'
  [ "$(echo "$page" | jq length)" -lt 50 ] && break
done
curl -fsS "$F/issues/<N>" | jq -r .body                 # finding + markers
for p in $(seq 1 100); do                                # full comment timeline
  page=$(curl -fsS "$F/issues/<N>/comments?limit=50&page=$p")
  echo "$page" | jq -r '.[] | .created_at[:16] + "\n" + .body + "\n---"'
  [ "$(echo "$page" | jq length)" -lt 50 ] && break
done
```

Triage order: HIGH before MEDIUM, then oldest. For each, decide in one line:
real / noise (rule threshold wrong) / duplicate root cause of another open
ticket. A burst of tickets in one window (e.g. many controllers restarting) is
usually **one** root cause — work the earliest, link the rest.

## 2. Claim

Writes need `pat_tickets` (never echo it):
Honor `FORGEJO_TOKEN_FILE` when set; otherwise prefer `~/forgejo_tickets.key`.
If no key file is readable, fall back to 1Password `pat_tickets`. Never print either value.


```bash
TOKEN_FILE="${FORGEJO_TOKEN_FILE:-$HOME/forgejo_tickets.key}"
if [[ -r "$TOKEN_FILE" ]]; then
  export FORGEJO_TOKEN="$(tr -d '[:space:]' < "$TOKEN_FILE")"
else
  export FORGEJO_TOKEN="$(op item get forgejo --fields pat_tickets --reveal)"
fi
fj() { curl -fsS -H "Authorization: token $FORGEJO_TOKEN" -H 'Content-Type: application/json' "$@"; }
fj -X POST "$F/issues/<N>/comments" -d '{"body":"taking"}'
```

Duplicates: comment `duplicate of #<survivor>` and close the loser
(`fj -X PATCH "$F/issues/<N>" -d '{"state":"closed"}'`). Do not touch markers.

## 3. Recall before diagnosing

Search incident history only in Forgejo: matching issues/comments and
`learnings/`. Do not use Hindsight/ops-bank or another external memory service.
Use the public read API where possible and the default token path
`${FORGEJO_TOKEN_FILE:-$HOME/forgejo_tickets.key}` when writes are authorized.

```bash
F="${FORGEJO_URL:-http://nas.homelab.internal:9003}/api/v1/repos/${TICKETS_REPO:-soulwhisper/homelab-tickets}"
# Read the lesson index and relevant source tickets/comments for the same
# alert, namespace/workload, symptom and root-cause class.
response=$(curl -sS -w '\n%{http_code}' "$F/contents/learnings") || exit $?
status="${response##*$'\n'}"
case "$status" in
  200) printf '%s\n' "${response%$'\n'*}" | jq -r '.[].name' ;;
  # A 404 learnings/ listing means no lessons retained yet — not an error.
  404) ;;
  *) printf 'Forgejo returned HTTP %s\n' "$status" >&2; exit 1 ;;
esac
```

For a recurrence, read the existing lesson file and its full source ticket,
including every page of source-ticket comments, before choosing a runbook.
Listing `learnings/` filenames is only discovery, not full lesson recall.
Report the recurrence; the orchestrator decides whether to append a keyed
recurrence comment to the existing lesson's ticket.

## 4. Diagnose and fix

- Reproduce the signal from **raw data** (VictoriaMetrics query, logs), not
  from the ticket text. Record the query; it becomes verification.
- The fix is a git change in `home-ops`, on a branch, as a GitHub PR. Public
  PR text stays terse: what + one-line why + `homelab-tickets#<N>`. Incident
  detail stays in the ticket.
- Agents propose, the human merges. No `kubectl apply/edit/delete` of
  Flux-managed objects. One-off live actions (rollout restart to clear state)
  need explicit user approval and must be recorded in the ticket.
- Comment the PR link on the ticket as soon as it exists.

## 5. Verify (after merge + reconcile)

Apply `acceptance.md` for the ticket's class. Minimum for alert tickets:

1. The raw rule expression is normal for the ticket's scope (same alert,
   namespace and workload; every instance, not just one pod).
2. A `**Event:** resolved` comment from the consumer exists (or explain why
   the alert cannot resolve yet, e.g. `for:` window).
3. Alert/kyverno classes: re-check after 24h before calling it durable.

Silence, inhibition or an empty Alertmanager result is **not** healing.

## 6. Close

One closing comment, then close:

```text
Fixed by soulwhisper/home-ops#<PR>.
Verification: <query> → <before> → <after> (<timestamp>).
Root cause: <one line>.
```

## 7. Learn (lesson file)

For a distinct root cause, dispatch the lessons workflow (writes
`learnings/YYYY-MM-DD-<slug>.md` per `skills/lessons.md`). A supervised run
passes all three inputs; `action_key` is the full occurrence key:

```bash
fj -X POST "$F/actions/workflows/lessons.yml/dispatches" -d '{"ref":"main","inputs":{"ticket":"<N>","run_id":"<RUN_ID>","action_key":"<RUN_ID>:lesson:<MERGE_SHA>"}}'
```

A manual dispatch with both `run_id` and `action_key` omitted retains the
unkeyed behavior; supplying only one is invalid. A keyed `run_id` must exactly
match `[0-7][0-9A-HJKMNP-TV-Z]{25}`, for example
`01K8ZC3N4FQ4N6FJ3F3K8D5E6A`, and `action_key` must be exactly
`<RUN_ID>:lesson:<40 lowercase hex merge SHA>`. Dispatch is operator-only: the
Forgejo MCP allowlist deliberately excludes it (the NAS runner is
root-capable). Repeat incident of a known root cause → comment on the existing
lesson's ticket instead of a new lesson.

The lesson-only master action record persists `dispatch_state` and
`supersedes`; allowed dispatch states are `not_sent`, `dispatching`, `unknown`,
`accepted`, `rejected`, and `done`. Intent starts as `not_sent`; append
`dispatching` immediately before the API call. Set `accepted` only on creation
acceptance and `rejected` only when the
response definitively says no run was created. A timeout or crash after
`dispatching` without `accepted` becomes `unknown`. Artifact completion sets
both `state=done` and `dispatch_state=done`. Only `not_sent` or `rejected`
starts an initial dispatch; `dispatching` and `unknown` never authorize one.
On `accepted`, record `next_check_at` and a bounded `dispatch_deadline`. Zero
matches before that deadline means `LEARN_PENDING`; after the deadline it
becomes `NEEDS_HUMAN(resume_stage=LEARN_PENDING)`. It never authorizes another
dispatch. For `unknown` with zero matches, independent human-verified evidence
that no run was created may record `rejected` plus `rejection_evidence` and
resume `LEARN_PENDING`; zero matches alone never qualifies.

### Deterministic recovery for keyed supervised dispatches

After a timeout, process restart, or unknown dispatch result, recover the
original run before considering another dispatch:

1. Paginate `GET $F/actions/runs?limit=50&page=<P>` until a short page. Read
   the `workflow_runs` entries (accept a bare array on older Forgejo
   responses). For every run whose `workflow_id` is exactly `lessons.yml`,
   decode the JSON string in `event_payload` with `jq fromjson`.
2. Exact-match the run's `prettyref` to `main` (or the decoded `ref` to
   `refs/heads/main`) and decoded `inputs.ticket`, `inputs.run_id`, and
   `inputs.action_key` to the original dispatch values. Dispatch inputs and
   ticket comparisons are strings. Record each matching run's `id` as the
   workflow run ID, not its display/run number or a job ID, together with
   `run.status`. Adopt a single match. Multiple exact-input runs are valid only
   when every earlier run is at logical terminal failure (`status` is `failure`
   or `cancelled`) and recorded as superseded; adopt the latest
   human-authorized attempt. Any other multiple match is ambiguous and stops
   recovery.
3. Verify the result artifact and treat it as authoritative over a later
   workflow failure. Ordinary lesson success requires a file pushed to Git
   whose frontmatter has both the exact `aiops_action` and exact `aiops_run`.
   `NO_LESSON` success requires all four of these in the **same**
   source-ticket comment: `<!-- aiops-no-lesson -->`, the exact
   `<!-- aiops-action:<RUN_ID>:lesson:<MERGE_SHA> -->`, the exact line
   `aiops_run: <RUN_ID>`, and `aiops_workflow_run: <WORKFLOW_RUN_ID>`. The
   comment's `user.id` must equal the adopted run's `trigger_user.id`, and its
   `created_at` must be at or after the run's `created` and, only when `stopped`
   is nonzero, at or before `stopped`. Marker text without this run-bound
   author/time evidence is not proof that the workflow produced `NO_LESSON`. Either exact artifact remains
   valid even after a later unrelated workflow failure; record `run.status` as
   evidence. This comment is same-run recovery evidence, not long-term lesson
   content.
4. Inspect `GET $F/actions/runs/<WORKFLOW_RUN_ID>/jobs` and, only when job
   detail is needed to explain an inconclusive run or missing artifact,
   `GET $F/actions/jobs/<JOB_ID>/logs`. A green job alone does not replace
   the Git-frontmatter or keyed-comment evidence above. A run at logical
   terminal failure (`status` is `failure` or `cancelled`) without a valid
   artifact becomes `NEEDS_HUMAN(resume_stage=LEARN_PENDING)`; do not leave it
   pending forever. An adopted nonterminal run without a settled artifact must
   record `next_check_at` and a bounded `execution_deadline`. Expiry becomes
   `NEEDS_HUMAN(resume_stage=LEARN_PENDING)` with the run ID, current
   `run.status`, and bounded diagnostics. Before resuming, recheck status and
   artifacts: terminal runs or valid artifacts follow normal completion. Every
   other return to `LEARN_PENDING`, including runner repair or an explicitly
   extended wait, requires fresh `next_check_at` and a new bounded
   `execution_deadline`. Human cancellation without a valid artifact uses step
   5's supersession path. The master never cancels a run automatically.
5. A human may explicitly approve a same-key retry only after a run reaches
   logical terminal failure (`status` is `failure` or `cancelled`) and its lack
   of a valid artifact is confirmed. Record the earlier `run.status` and
   superseded state, then write a new `not_sent` action whose `supersedes`
   identifies that earlier attempt. Dispatch the identical
   ticket/run_id/action_key through the lifecycle above, record the newly
   authorized attempt, and recover its workflow run ID. Never blindly retry.

Zero matching runs after `dispatching`/`unknown` is **UNKNOWN**, retains
`dispatch_state=unknown`, and routes to
`NEEDS_HUMAN(resume_stage=LEARN_PENDING)`. `accepted` with zero matches instead
remains `LEARN_PENDING` with `next_check_at` only until `dispatch_deadline`,
then routes to the same human state. At that deadline, first recheck
`actions/runs` and artifacts and adopt anything now present. Any continued wait
requires fresh `next_check_at` and a new bounded `dispatch_deadline`;
independent non-creation evidence follows the `rejected` path above. No
zero-match result authorizes another dispatch. Multiple matches outside the supersession rule above and
undecodable/mismatched payloads likewise stop as unknown dispatch identity.
Only independent human-verified non-creation evidence may later record
`rejected` plus `rejection_evidence` and resume `LEARN_PENDING`; zero matches
alone never proves non-creation. Record bounded evidence and never blindly
redispatch. The human-approved same-key retry in step 5 remains a separate
allowed path only after logical terminal failure (`status` is `failure` or
`cancelled`) without an artifact.

### Manual unkeyed unknown outcomes

Keyed deterministic recovery and its `DONE` guarantee do not apply to manual
unkeyed dispatches. The operator identifies an unknown outcome by ticket,
dispatch time, and available run identity, then inspects the matching run's
jobs/logs or `learnings/YYYY-MM-DD-ticket<N>-<slug>.md` as applicable. Manual
`NO_LESSON` writes no keyed source-ticket comment and remains logs-only. Never
automatically redispatch an unknown manual outcome.

## 8. Remember (incident memory in `learnings/`)

Use `learnings/` and ticket comments as the only incident memory and recall
backend; do not use Hindsight/ops-bank or another external memory service.
Verify a supervised keyed lesson file exists with exact `aiops_action` and
`aiops_run` frontmatter. For a manual unkeyed lesson, verify the expected
`learnings/YYYY-MM-DD-ticket<N>-<slug>.md` path exists and its content matches
the source ticket's evidence; keyed frontmatter is not required. In either
case, verify a recurrence comment on the existing lesson's source ticket when
applicable. A keyed `NO_LESSON` comment only closes recovery for its own run;
it is not retained lesson content. On the next diagnosis, recall matching lesson
files plus full source tickets and all comments by alert, namespace/workload,
and root-cause class. Keep only facts and verification queries, no secrets or
raw log dumps.

## Don'ts

- Don't close on Holmes' word, on a silence, or before the fix reconciled.
- Don't create tickets by hand for alerts — the consumer owns intake;
  hand-made tickets lack the marker and will be duplicated.
- Don't rsync or delete `learnings/` files you did not write.
- Don't paste tokens, kubeconfig or Secret values into tickets, PRs or memory.
