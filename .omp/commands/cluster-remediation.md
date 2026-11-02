---
description: Implement evidence-backed fixes on Git branches and open PRs without merging
---

# Cluster remediation

Turn a current `cluster-diagnosis` finding or an explicit `runbook_id` into a reviewed GitHub PR. Make no live-cluster mutations of any kind, including reconciliation and workload restarts; this command is limited to Git and PR changes and never merges automatically.

## 1. Prerequisites and recommendation gate

1. Read `skill://homelab-gitops` and `skill://homelab-tickets`, then confirm the current branch, context, finding evidence, and existing related PRs.
2. Verify that the finding still exists and inspect both open PRs and recently merged PRs plus desired state on `main`. If current state already satisfies the runbook, do not create a branch or PR; run `cluster-verification` instead. If a fix is merged but its revision is not yet applied, do not create another PR—classify it as `PENDING_RECONCILE` and run `cluster-verification`.
3. Select exactly one conservative runbook from the table. A matching runbook is the recommendation: proceed without calling `ask`.
4. **Call the `ask` tool only when no conservative recommendation exists**—no matching runbook, or several materially different fixes with no boring/safe default. Ask once with 2–5 options that state the tradeoffs. Never use `ask` for information available from tools, for a standard runbook, or to disguise a guessed fix.
5. If the required evidence or repository access is unavailable, finish all reachable work and state the exact prerequisite. Do not invent a runbook or silently narrow the request.

## 2. Current runbooks

| `runbook_id` | Required evidence | Recommended PR change |
| --- | --- | --- |
| `holmes-fixed-collector` | Model-generated queries or verdicts are nondeterministic; target data has fixed semantics | Use deterministic read-only collectors with coverage, fail/error distinction, bounded output, and behavior regressions. Preserve model guardrails for non-deterministic checks. |
| `holmes-rerun-uid` | Rerun fails with `KeyError: 'uid'` before executing the check | Use Kopf's `uid` when the update body omits `metadata.uid`; add a body-less-UID regression and bump the patch rollout revision. |
| `mcp-readonly-path` | Exact ENOENT path on a read-only root filesystem | Redirect only the affected path (`TMPDIR`, `XDG_CACHE_HOME`, or an existing writable volume). Keep `readOnlyRootFilesystem: true`; do not restart as a substitute for a path fix. |
| `dsh-mcp-reconnect` | Backend recovers but tools stay disconnected after the default retry budget | Share a non-fatal reconnect policy with bounded backoff and an explicit long-lived attempt budget. Do not force all of DSH to fail at startup. |
| `mcp-tool-allowlist` | A valid tool is absent from `tools/list` or denied by the gateway | Add only the named tool to the affected backend's registration and matching gateway CEL allowlist; for the GitHub PR backend, update `GITHUB_TOOLS`. Do not enable broad toolsets, merge, or unrelated writers. |
| `guardrail-retry-loop` | New tools/arguments are denied by `denied-tool-retry-loop` after an old triad | Make LoopRule match only the newest fingerprint; add stale-history and recovery regressions. After human review, wait for the human to merge the upstream source PR and release-please PR and for image publication, then bump home-ops. Never disable the invariant or `FailClosed`. |
| `mnemon-home-space` | Provider is healthy but there is no active conversational Memory Space | Change only missing Git-managed provider settings and the pinned driver's home-only routes: health/discovery, home stats/entities/graph/list reads, home recall/retain, and PATCH soft-forget for one memory ID. Deny bank configuration/operations, `ops`-bank access, and PUT/DELETE. If those settings already match, do not open a no-op PR: report the operation as unapproved with its exact scope, preconditions, verification, and risk/stop details. Do not seed `state/memory-providers.json` or assume a native CLI exists. |
| `playwright-cpu-throttle` | Short proxy bursts are CFS-throttled despite low sustained use and large node headroom | Prefer no proxy CPU limit while retaining a small request and memory limit. Do not replace one arbitrary cap with another or remove limits from other containers. |

If none applies, use the generic evidence-backed minimal-PR plan only after `ask` selects a direction.

## 3. Implement

1. Start from a clean, current `main` and a focused branch. If a related PR is already open, update that branch rather than duplicating it.
2. Keep blast radius minimal and reuse existing patterns. Update affected call sites, rollout annotations, tests, and docs together. No secrets or raw credentials in code, logs, tests, or PR text.
3. Add regressions only for consumer-visible behavior, boundaries, and invariants. Prove new tests fail before the fix and pass after it; do not add source-text, mock-echo, or tautological tests.
4. Run targeted verification and the relevant full suite plus `prek run`. Exercise the changed behavior when a runtime is available; never weaken alerts, evidence gates, or guardrails to make a check pass.
5. For upstream fixes, keep the upstream PR separate. Wait for its merge, release-please PR, and successful signed multi-arch image publication before changing the home-ops image tag.

## 4. Open and finish the PR

1. Commit with a focused message and push. Open or update the PR with what, why, verification, linked incident IDs, and a **head-bound post-merge close/learn plan** covering exact operations, scope, preconditions, verification, and rollback/stop conditions. Write the same plan in the ticket comment immediately, including the PR URL. Keep public text terse and free of secrets.
2. Before declaring `CI_GREEN`, verify that the PR-body and ticket plans match exactly and are bound to the current head. If either is missing or mismatched, stop as `NEEDS_HUMAN`; do not wait for merge. Recheck the merged plan before close or lesson dispatch.
3. Watch every CI and AI-review check. Reproduce valid findings, fix them with regressions, and resolve/reply to threads. When a finding is wrong, reply with evidence instead of changing correct code.
4. Do not merge, enable auto-merge, or apply the branch directly to the cluster. Stop only after CI is green and unresolved review threads are zero.
5. Hand off with the PR head SHA and matching close/learn plan, and mark the merge SHA as pending human merge. After the human merges, `cluster-aiops resume` reconciles the merged revision and then invokes `cluster-verification`, closure, and lessons. Do not invoke those stages out of order.

## 5. Report contract

Report in Chinese:

- runbook and evidence used;
- files/repositories changed and regression proof;
- PR URL, head SHA, CI/review status;
- any `ask` decision required, or explicitly `no_recommendation` when it was used;
- what remains blocked on human merge, release publication, live approval, or observation time.
