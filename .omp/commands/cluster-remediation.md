---
description: Implement evidence-backed fixes on Git branches and open PRs without merging
---

# Cluster remediation

Turn a current `cluster-diagnosis` finding or an explicit `runbook_id` into a reviewed GitHub PR. Make no live-cluster mutations of any kind, including reconciliation and workload restarts; this command is limited to Git and PR changes and never merges automatically.

## 1. Prerequisites and recommendation gate

1. Read `skill://homelab-gitops` and `skill://homelab-tickets`, then confirm the current branch, context, finding evidence, and existing related PRs. For ticket operations, use `F="${FORGEJO_URL:-http://nas.homelab.internal:9003}/api/v1/repos/${TICKETS_REPO:-soulwhisper/homelab-tickets}"` and `TOKEN_FILE="${FORGEJO_TOKEN_FILE:-$HOME/forgejo_tickets.key}"`.
2. Verify that the finding still exists and inspect both open PRs and recently merged PRs plus desired state on `main`. Whenever a corresponding merged PR is applied, do not create a branch or PR; return `VERIFYING` with merge/revision evidence and current behavior, including active or drifted findings. If the corresponding fix is merged but its revision is not applied, return `RECONCILING`; do not invoke verification. If current state is healthy/outdated without a corresponding merged PR, including after a human-performed no-PR action, return `HUMAN_MANAGED` with a stable occurrence key, `na` action key, evidence, reason, and no post-merge handoff. This is a finite terminal, not `DONE`: the master releases the lease, performs no close, lesson dispatch, or runtime mutation, and resume is a no-op. A human-performed action with a corresponding merged PR still returns `VERIFYING`. The master performs reconciliation and verification.
3. Select exactly one conservative runbook from the table. A matching runbook is the recommendation: proceed without calling `ask`.
4. If no runbook matches, or several materially different fixes have no boring/safe default, return `runbook_id: no_recommendation` and `NEEDS_HUMAN` with `resume_stage: DIAGNOSED` plus 2–5 evidence-backed options and their tradeoffs. The master owns the human decision; this subcommand does not call `ask`. Proceed with a generic evidence-backed minimal-PR plan only when the master supplies the selected direction.
5. If the required evidence or repository access is unavailable, finish all reachable work and state the exact prerequisite. Do not invent a runbook or silently narrow the request.

## 2. Current runbooks

| `runbook_id` | Required evidence | Recommended PR change |
| --- | --- | --- |
| `holmes-fixed-collector` | Model-generated queries or verdicts are nondeterministic; target data has fixed semantics | Use deterministic read-only collectors with coverage, fail/error distinction, bounded output, and behavior regressions. Preserve model guardrails for non-deterministic checks. |
| `holmes-rerun-uid` | Rerun fails with `KeyError: 'uid'` before executing the check | Use Kopf's `uid` when the update body omits `metadata.uid`; add a body-less-UID regression and bump the patch rollout revision. |
| `mcp-readonly-path` | Exact ENOENT path on a read-only root filesystem | Redirect only the affected path (`TMPDIR`, `XDG_CACHE_HOME`, or an existing writable volume). Keep `readOnlyRootFilesystem: true`; do not restart as a substitute for a path fix. |
| `dsh-mcp-reconnect` | Backend recovers but tools stay disconnected after the default retry budget | Share a non-fatal reconnect policy with bounded backoff and an explicit long-lived attempt budget. Do not force all of DSH to fail at startup. |
| `mcp-tool-allowlist` | A valid tool is absent from `tools/list` or denied by the gateway | Add only the named tool to the affected backend's registration and matching gateway CEL allowlist; for the GitHub PR backend, update `GITHUB_TOOLS`. Do not enable broad toolsets, merge, or unrelated writers. |
| `guardrail-retry-loop` | New tools/arguments are denied by `denied-tool-retry-loop` after an old triad | Make LoopRule match only the newest fingerprint; add stale-history and recovery regressions. Open/update the upstream source PR and return `PR_OPEN`; the master owns upstream/release-please merge waits and image-publication verification before the home-ops bump. Never disable the invariant or `FailClosed`. |
| `mnemon-home-space` | Provider is healthy but there is no active conversational Memory Space | Change only missing Git-managed provider settings and the pinned driver's home-only routes: health/discovery, home stats/entities/graph/list reads, home recall/retain, and PATCH soft-forget for one memory ID. Deny bank configuration/operations, `ops`-bank access, and PUT/DELETE. If those settings already match, do not open a no-op PR: report the operation as unapproved with its exact scope, preconditions, verification, and risk/stop details. Do not seed `state/memory-providers.json` or assume a native CLI exists. |
| `playwright-cpu-throttle` | Short proxy bursts are CFS-throttled despite low sustained use and large node headroom | Prefer no proxy CPU limit while retaining a small request and memory limit. Do not replace one arbitrary cap with another or remove limits from other containers. |

A generic plan is valid only after the master supplies the human-selected direction; otherwise return the typed `NEEDS_HUMAN` result above.

## 3. Implement

1. Start from a clean, current `main` and a focused branch. If a related PR is already open, update that branch rather than duplicating it.
2. Keep blast radius minimal and reuse existing patterns. Update affected call sites, rollout annotations, tests, and docs together. No secrets or raw credentials in code, logs, tests, or PR text.
3. Add regressions only for consumer-visible behavior, boundaries, and invariants. Prove new tests fail before the fix and pass after it; do not add source-text, mock-echo, or tautological tests.
4. Run targeted verification and the relevant full suite plus `prek run`. Exercise the changed behavior when a runtime is available; never weaken alerts, evidence gates, or guardrails to make a check pass.
5. For upstream fixes, keep the upstream PR separate and return `PR_OPEN` after opening or updating it. The master owns the upstream source-PR and release-please merge waits plus image-publication verification. When the master supplies the published image/digest evidence, accept that evidence, implement the home-ops image bump, and return `PR_OPEN` after opening or updating its PR. Do not assign or perform publication waits inside this subcommand.

## 4. Open the PR and hand off

1. Commit with a focused message and push. Open or update the PR with what, why, verification, linked incident IDs, and a **head-bound post-merge close/learn plan** covering exact operations, scope, preconditions, verification, and rollback/stop conditions. Include `<!-- aiops-action:<run_id>:open-pr:<head_sha> -->` in the PR body. Write the same plan once in each source-ticket PR-link comment immediately, including the PR URL and `<!-- aiops-action:<run_id>:link-pr:<head_sha> -->`. Use separate `open-pr` and `link-pr` intent/result records and check each exact external marker independently on retry. Adopt and update an existing related unmarked PR rather than duplicating it. Keep public text terse and free of secrets.
2. Before returning `PR_OPEN`, verify that the PR-body and ticket plans match exactly and are bound to the current head. If either is missing or mismatched, return `NEEDS_HUMAN`; do not declare `CI_GREEN` or wait for merge. The master rechecks the plans at its merge and post-merge boundaries.
3. Do not merge, enable auto-merge, apply the branch directly to the cluster, or repeat the ticket link. Return the PR URL, head SHA, local verification, external artifact references, and merge SHA as pending human merge. The master verifies the markers, drives CI/AI-review iterations, yields for human merge, and only then invokes reconciliation, verification, closure, and lessons in order.

## 5. Report contract

Report in Chinese:

- one typed result: `PR_OPEN`, `RECONCILING`, `VERIFYING`, `HUMAN_MANAGED`, or `NEEDS_HUMAN`; include the runbook and evidence used;
- files/repositories changed and regression/local verification proof;
- for `PR_OPEN`, the PR URL, head SHA, external marker references, and pending human merge; for `RECONCILING`/`VERIFYING`, the merge SHA and applied-revision evidence;
- for `HUMAN_MANAGED`, the stable occurrence key, `na` action key, evidence, and reason for the healthy/outdated or human-performed no-PR outcome; state that the master releases the lease without close, lesson dispatch, or runtime mutation and that resume is a no-op;
- for `NEEDS_HUMAN`, `resume_stage`, the exact decision or prerequisite, `no_recommendation` when applicable, and the evidence-backed options for the master; keep the no-runbook route available for the master selected-direction handoff to remediation;
- the next master action and anything blocked on human merge, release publication, live approval, or observation time.
