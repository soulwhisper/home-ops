# Lessons learnt format

Distilled memory, written by whoever fixed the ticket (agent or human), at
ticket close. Lives in the `homelab-tickets` repository's `learnings/` —
plain markdown, half a page max, only what would make the next incident faster.

## Location

All `learnings/` paths in this document are relative to the
`soulwhisper/homelab-tickets` repository, alongside the tickets and this
workflow. Do not create a `learnings/` directory in `home-ops`.

## File

`learnings/YYYY-MM-DD-ticket<N>-<slug>.md`

```markdown
---
ticket: 42
pr: soulwhisper/home-ops#3999
root_cause_class: config-drift | capacity | upstream-bug | secret-rotation | other
confidence: verified | suspected
---

# <one-line lesson>

**Symptom**: what fired, in one line.
**Root cause**: the actual mechanism, not the surface error.
**Fix**: what changed (PR link), in one line.
**Faster next time**: the single thing that would have cut MTTR — a query, a
log line, a panel, a runbook step.
```

## Keyed workflow results

A supervised dispatch passes `ticket`, `run_id`, and the full `action_key`.
`run_id` must exactly match `[0-7][0-9A-HJKMNP-TV-Z]{25}`, for example
`01K8ZC3N4FQ4N6FJ3F3K8D5E6A`; `action_key` must exactly match
`<run_id>:lesson:<40 lowercase hex merge SHA>`. These are YAML-safe plain
strings. An ordinary lesson is successful only after its file is committed and
pushed to Git with both exact frontmatter fields:

```yaml
aiops_action: <run_id>:lesson:<merge_sha>
aiops_run: <run_id>
```

A manual dispatch with both identifiers omitted retains the unkeyed lesson
format above; supplying only one identifier is invalid. Manual `NO_LESSON` is
logs-only and writes no source-ticket comment.

If the model returns `NO_LESSON`, the keyed workflow writes no lesson file. It
posts at most one comment on the source ticket with this same-run evidence:

```text
<!-- aiops-no-lesson -->
<!-- aiops-action:<run_id>:lesson:<merge_sha> -->
aiops_run: <run_id>
aiops_workflow_run: <workflow_run_id>
No reusable lesson was found for this ticket; recorded for this run.
```

A repeat dispatch skips the write only when the same already-fetched comment
contains all four exact lines and its `user.id` equals the adopted run's
`trigger_user.id`, with `created_at` at or after the run's `created` and, only
when `stopped` is nonzero, at or before `stopped`. `NO_LESSON` recovery requires
this run-bound author/time evidence in addition to all four lines; marker text
alone cannot prove the workflow produced the result. Workflow success alone is
insufficient. The comment is evidence for this run only, not long-term lesson
content or a substitute recurrence record.

Either exact result artifact is authoritative over a later unrelated workflow
failure; retain `run.status` as evidence without discarding the pushed lesson
or keyed comment. A run whose `run.status` is `failure` or `cancelled` and
which has no valid artifact routes to `NEEDS_HUMAN(resume_stage=LEARN_PENDING)`,
not indefinite pending. An adopted nonterminal run without a settled artifact
records `next_check_at` and a bounded `execution_deadline`; expiry likewise
routes to `NEEDS_HUMAN(resume_stage=LEARN_PENDING)` with run ID, current
`run.status`, and bounded diagnostics. Before resuming, recheck status and
artifacts: terminal runs or valid artifacts follow normal completion. Every
other return to `LEARN_PENDING`, including runner repair or an explicitly
extended wait, requires fresh `next_check_at` and a new bounded
`execution_deadline`. Human cancellation without a valid artifact uses the
supersession path below. The master never cancels automatically.
Only explicit human approval permits a same-key retry after that artifact
check; the authorized retry writes a new `not_sent` action
with `supersedes` identifying the earlier attempt. Record earlier runs with
`run.status` of `failure` or `cancelled` as superseded and adopt only the
latest human-authorized attempt. Multiple exact-input runs are otherwise
ambiguous and stop recovery; never blindly retry.

Deterministic recovery applies only to keyed supervised dispatches. The
lesson-only action record persists `dispatch_state` and `supersedes`; allowed
dispatch states are `not_sent`, `dispatching`, `unknown`, `accepted`,
`rejected`, and `done`. Intent starts as `not_sent`; append `dispatching`
immediately before the API call. Creation
acceptance alone sets `accepted`; only a response definitively saying no run
was created sets `rejected`. Timeout or crash after `dispatching` without
`accepted` sets `unknown`; artifact completion sets both `state=done` and
`dispatch_state=done`. Only `not_sent`/`rejected` starts initial dispatch.
Zero matching runs after `dispatching`/`unknown` remains `UNKNOWN` with
`dispatch_state=unknown` and routes to
`NEEDS_HUMAN(resume_stage=LEARN_PENDING)`. `accepted` with zero matches remains
`LEARN_PENDING` with `next_check_at` only until `dispatch_deadline`, then routes
to the same human state. At that deadline, recheck `actions/runs` and artifacts
and adopt anything now present. Any continued wait requires fresh
`next_check_at` and a new bounded `dispatch_deadline`; independent
non-creation evidence follows the `rejected` path above. No zero-match result
authorizes redispatch. Only
independent human-verified non-creation evidence may later record `rejected`
plus `rejection_evidence` and resume `LEARN_PENDING`; zero matches alone never
proves non-creation. The human-approved retry after `run.status` is `failure`
or `cancelled` above is a separate allowed path through a new `not_sent` record
with `supersedes`.

Manual unkeyed unknown outcomes are operator-managed: identify the run by
ticket, dispatch time, and available run identity, then inspect jobs/logs or
the `homelab-tickets` repo's `learnings/YYYY-MM-DD-ticket<N>-<slug>.md` as applicable. They have no keyed
`DONE` guarantee and must never be automatically redispatched.

## Rules

- One lesson per distinct root cause. A repeat incident gets a comment on the
  existing lesson, not a new file.
- The `homelab-tickets` repo's `learnings/` and ticket comments are the record;
  the Hindsight `ops` bank is a recall index over them, never the source of
  truth. Hindsight left the cluster with its service, so the bank is called
  directly at `http://nas.homelab.internal:8888/mcp/ops` — native MCP, no
  ToolHive proxy tier and no `/mcp/agent` bank entry. It requires a bearer key:
  send `Authorization: Bearer <key>` (the operator holds it; a request without
  it gets `401`). If recall and the lesson file disagree, the lesson file wins.
- The bank was rebuilt empty when the service moved (it held test data only), so
  an empty recall means no memory yet, not no history — read `learnings/` before
  concluding anything.
- That endpoint is LAN-only, plain HTTP, and holds one shared key — treat write
  access as operator-equivalent anyway. The no-secrets rule below applies to it
  as strictly as to the repo.
- Recurrence recall includes matching source-ticket bodies and all comments.
  Full lesson recall reads the lesson file and its source ticket, including
  comments; listing `learnings/` filenames is discovery, not recall.
- No secrets, no credentials, no customer data. Hostnames and namespaces are
  fine — this repo never leaves the LAN.
- If the fix was "revert", the lesson says why it was wrong the first time.
