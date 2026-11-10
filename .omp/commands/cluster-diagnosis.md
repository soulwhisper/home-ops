---
description: Read-only live cluster diagnosis with ticket correlation and prioritized fix plans
---

# Cluster diagnosis

Perform a read-only diagnosis of the live cluster. Do not edit cluster resources, machine configs, tickets, or local files. Report in Chinese.

## Required preparation

1. Read `skill://homelab-gitops` and `skill://homelab-tickets` first and follow their lifecycle and acceptance rules.
2. Read `.mise.toml` and `infrastructure/talos/version.yaml`. Confirm `kubectl config current-context` before collecting evidence.
3. Set `F="${FORGEJO_URL:-http://nas.homelab.internal:9003}/api/v1/repos/${TICKETS_REPO:-soulwhisper/homelab-tickets}"` and `TOKEN_FILE="${FORGEJO_TOKEN_FILE:-$HOME/forgejo_tickets.key}"`. These are environment defaults, not a second hardcoded repository or credential path.
4. **Recall before diagnosing**: search matching Forgejo tickets and the `homelab-tickets` repo's `learnings/` (via `$F/contents/learnings`) for the same alert, resource, and root-cause class. Record whether this is a recurrence, the prior fix and verification, and any lesson that changes the current runbook. Report recurrence evidence only; `cluster-aiops` decides whether to append a keyed recurrence comment to the existing lesson's source ticket.
5. Keep all queries bounded. Redact credentials, tokens, private keys, and Secret values. Do not dump complete logs or configuration payloads.

## Evidence collection

1. **Baseline status**
   - Nodes, Ready/scheduling state, non-ready/pending/restarting pods, Flux Kustomizations, Talos/Tuppr phase and versions, Ceph health, storage/CSI state, backup repository and queues.
   - Include recent upgrades, maintenance activity, and known incident context.

2. **Change and rollout history (PR merge history)**
   - Read the applied Flux revision and compare it with recent GitHub merges before interpreting any restart, stall, or storage flap: `kubectl -n "$FLUX_SYSTEM_NAMESPACE" get kustomizations`, `git log --first-parent --since="7 days ago" --pretty='%h %ci %s'`, and `gh pr list --state merged --limit 50 --json number,title,mergedAt,mergeCommit`.
   - Build a merge-to-rollout timeline from pod start times and image-pull counters: `kubectl get pods -A -o custom-columns=NS:.metadata.namespace,POD:.metadata.name,START:.status.startTime` and `increase(kubelet_image_pull_duration_seconds_count[5m])`.
   - When a `PodRestartStorm`, etcd proposal-failure/leader-change window, apiserver 5xx burst, Ceph OSD/mon down, or controller lease loss falls inside the same 30-minute window as a merge wave or mass pod start, record the PR numbers, merge times, and exact rollout window as candidate triggers. The rollout itself is expected; a control-plane or storage stall that coincides with it is the finding.
   - Do not attribute a stall to an application bug or an operator defect while the same window carries an upgrade/image-pull wave. Establish the pre-wave baseline and repeat the correlation across the retained alert window before assigning a root cause.
   - A merged PR is not applied until the Flux revision matches; record the applied revision and each affected HelmRelease's `status.observedGeneration`, never assume local `main`.

3. **Metrics**
   - Node/pod CPU and memory, Ceph PG/OSD state, etcd quorum and latency, PostgreSQL replication lag, Kopiur freshness and backlog, VictoriaMetrics scrape/rule errors, and ticket-delivery failure rates.
   - Prefer raw PromQL and exact timestamps over dashboard impressions.
   - When capacity or resource optimization is in scope, derive effective requests/limits from the admitted Pod spec, including LimitRange/admission defaults; a limit without a request is copied to the request only when no admission default applies. Aggregate all containers per workload, state whether totals are per-Pod or cluster-wide, and multiply by desired replicas for cluster-wide totals. Use 5m rate/working-set samples with no-data workloads marked unverified: CPU request = max(10m, ceil(1.2 × max(7d P95, 24h P95) / 10m) × 10m), capped at the current CPU limit when set; memory request = max(32Mi, ceil(max(1.15 × 7d P95, 1.05 × 7d P99) / 16Mi) × 16Mi), capped at the current memory limit when set. Also report a conservative variant (CPU 1.5 × P95; memory max(1.2 × P95, 1.5 × P99), both capped at their current limits when set). Report net CPU/memory deltas, top over/under-provisioned workloads, and the 7-day-window caveat. Do not edit resources during diagnosis.

4. **Logs and traces**
   - Recent Warning events, previous/current logs for failing workloads, Flux reconcile errors, controller/CSI/Talos errors, VolumeAttachment and other condition timelines.
   - When a tracing backend is available, query relevant error/latency traces by service and operation. Otherwise use events, conditions, and state transitions as the trace evidence and state that no trace backend was verified.

5. **Recent alerts**
   - Query Alertmanager for active, silenced, and inhibited alerts. Use vmsingle's retained `ALERTS` history for recently resolved/firing transitions and corroborate them with Forgejo ticket timelines; do not use Alertmanager as the historical source.
   - Never treat silence, inhibition, or an empty Alertmanager result as proof of healing.

6. **Forgejo tickets**
   - List open issues and inspect relevant comments/timelines. Use the public read-only API when possible; when authentication is required, load the token with `tr -d '[:space:]' < "${FORGEJO_TOKEN_FILE:-$HOME/forgejo_tickets.key}"` without printing it, using the skill's 1Password fallback only when no key file is readable.
   - Correlate related tickets and likely duplicate root causes. Do not create, modify, assign, or close tickets during diagnosis.

7. **AI-ops control plane and recovery evidence**
   - **Holmes**: compare the current `ScheduledHealthCheck.spec.query` with the executing child's query and result. An old child using an old prompt is stale evidence, not proof that a new fixed collector failed. Check the operator and worker patch revisions separately from target health.
   - **MCP tiers**: distinguish connection/authentication, `tools/list`, and an actual read-only `tools/call`. Inspect backend tool registration and gateway CEL allowlists independently. Do not repeat denied calls merely to see whether they recover.
   - **Guardrails**: record image version and the exact audit reason. A `denied-tool-retry-loop` for different tools/arguments is stale-history evidence only on versions with the old behavior; on the current 1.4.0 contract, treat it as a guardrail regression or configuration/version mismatch rather than dismissing it as content. Do not recommend disabling the invariant or `FailClosed`.
   - **DSH/browser**: check backend readiness and reconnect budget separately from writable paths (`TMPDIR`, `XDG_CACHE_HOME`, and any path named by an ENOENT error). A restart cannot fix a read-only filesystem path.
   - **Mnemon**: distinguish a healthy provider from an active Memory Space. Inspect enabled providers, space mappings and activation state, bank isolation, and existing retain/recall evidence. Do not seed provider registries or infer that provider discovery creates a Space.
   - Treat user-reported errors as ground-truth historical symptoms. Verify the desired state and current behavior from raw evidence, without rerunning solely to reproduce the same error.

## Report contract

- List findings from **HIGH to LOW severity**. For every finding include:
  - exact resource/scope and current impact;
  - evidence: query, metric value, log/event, trace, or ticket timeline with timestamps;
  - confidence and any explicitly unverified assumption;
  - minimal fix plan: Git PR versus one-off live action, verification steps, and rollback/stop condition.
  - when a conservative runbook applies, include `runbook_id`, `target_repo`, `pr_steps`, and `post_merge_verify`. Use IDs from `cluster-remediation.md`; otherwise emit `runbook_id: no_recommendation`.
  - include `aiops_stage: DIAGNOSED`, an idempotency key for `cluster-aiops resume`, and one `next_action`; diagnosis and verification stages are distinct from consumer fire/resolved transitions.
  - for an active finding that needs a new fix, has a conservative runbook, and has no corresponding open or merged PR, return `next_action: cluster-remediation`. If a corresponding open PR exists, return `next_action: cluster-remediation` with its head SHA and existing-PR evidence so the subcommand can adopt/update markers and plans instead of creating another PR or selecting a terminal. Whenever a corresponding merged PR is applied, return `next_action: VERIFYING` with merge/revision evidence and current behavior, including active or drifted findings; if the corresponding fix is merged on `main` but not applied, return `next_action: RECONCILING`. Never create a duplicate PR for a finding with a corresponding open or merged PR.
  - if current state is healthy/outdated without a corresponding open or merged PR, including after a human-performed no-PR action, return `next_action: HUMAN_MANAGED` with a stable occurrence key, `na` action key, evidence, and reason. This is a finite terminal, not `DONE`: the master releases the lease, performs no close, lesson dispatch, or runtime mutation, and resume is a no-op. Do not create a post-merge handoff without a merged PR; a human-performed action with a corresponding merged PR still follows the `VERIFYING` route above.
  - for an active finding with no conservative runbook and no corresponding open or merged PR, return `next_action: NEEDS_HUMAN` with `resume_stage: DIAGNOSED` and the evidence/options required for the master decision. The master routes a recorded human-selected direction to `cluster-remediation`; do not turn this route into `HUMAN_MANAGED` or create a post-merge handoff without a merged PR. Healthy/outdated findings always use the terminal route above, even when no runbook applies.
  - do not call `ask` or invoke another subcommand. The master invokes remediation/verification and owns every human question; heavy-impact execution always requires separate approval through `cluster-aiops` under `NEEDS_HUMAN`.
- Separate active failures, imminent risks, stale/noise/expected conditions, and already healthy evidence.
- For restart storms, control-plane stalls, and storage flaps, report the merge/rollout correlation window, the applied Flux revision, and the candidate PR numbers; distinguish expected upgrade restarts from the control-plane or storage stall they exposed.
- When capacity or resource optimization is in scope, include a resource estimate section: scope/method, current vs recommended totals, top over/under-provisioned workloads, confidence, and the 7-day-window limitation.
- Reproduce signals from raw data instead of trusting ticket text or model hypotheses. Do not default to disabling alerts, health checks, or LLM guardrails.
