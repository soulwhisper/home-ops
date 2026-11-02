---
description: Read-only live cluster diagnosis with ticket correlation and prioritized fix plans
---

# Cluster diagnosis

Perform a read-only diagnosis of the live cluster. Do not edit cluster resources, machine configs, tickets, or local files. Report in Chinese.

## Required preparation

1. Read `skill://homelab-gitops` and `skill://homelab-tickets` first and follow their lifecycle and acceptance rules.
2. Read `.mise.toml` and `infrastructure/talos/version.yaml`. Confirm `kubectl config current-context` before collecting evidence.
3. Keep all queries bounded. Redact credentials, tokens, private keys, and Secret values. Do not dump complete logs or configuration payloads.

## Evidence collection

1. **Baseline status**
   - Nodes, Ready/scheduling state, non-ready/pending/restarting pods, Flux Kustomizations, Talos/Tuppr phase and versions, Ceph health, storage/CSI state, backup repository and queues.
   - Include recent upgrades, maintenance activity, and known incident context.

2. **Metrics**
   - Node/pod CPU and memory, Ceph PG/OSD state, etcd quorum and latency, PostgreSQL replication lag, Kopiur freshness and backlog, VictoriaMetrics scrape/rule errors, and ticket-delivery failure rates.
   - Prefer raw PromQL and exact timestamps over dashboard impressions.

3. **Logs and traces**
   - Recent Warning events, previous/current logs for failing workloads, Flux reconcile errors, controller/CSI/Talos errors, VolumeAttachment and other condition timelines.
   - When a tracing backend is available, query relevant error/latency traces by service and operation. Otherwise use events, conditions, and state transitions as the trace evidence and state that no trace backend was verified.

4. **Recent alerts**
   - Query Alertmanager for active, silenced, and inhibited alerts. Use vmsingle's retained `ALERTS` history for recently resolved/firing transitions and corroborate them with Forgejo ticket timelines; do not use Alertmanager as the historical source.
   - Never treat silence, inhibition, or an empty Alertmanager result as proof of healing.

5. **Forgejo tickets**
   - List open issues and inspect relevant comments/timelines. Use the public read-only API when possible; when authentication is required, load the token with `tr -d '[:space:]' < "${FORGEJO_TOKEN_FILE:-$HOME/forgejo_tickets.key}"` without printing it, using the skill's 1Password fallback only when no key file is readable.
   - Correlate related tickets and likely duplicate root causes. Do not create, modify, assign, or close tickets during diagnosis.

6. **AI-ops control plane and recovery evidence**
   - **Holmes**: compare the current `ScheduledHealthCheck.spec.query` with the executing child's query and result. An old child using an old prompt is stale evidence, not proof that a new fixed collector failed. Check the operator and worker patch revisions separately from target health.
   - **MCP tiers**: distinguish connection/authentication, `tools/list`, and an actual read-only `tools/call`. Inspect backend tool registration and gateway CEL allowlists independently. Do not repeat denied calls merely to see whether they recover.
   - **Guardrails**: record image version and the exact audit reason. `denied-tool-retry-loop` with different tools/arguments indicates stale history poisoning, not a content violation. Do not recommend disabling the invariant or `FailClosed`.
   - **DSH/browser**: check backend readiness and reconnect budget separately from writable paths (`TMPDIR`, `XDG_CACHE_HOME`, and any path named by an ENOENT error). A restart cannot fix a read-only filesystem path.
   - **Mnemon**: distinguish a healthy provider from an active Memory Space. Inspect enabled providers, space mappings and activation state, bank isolation, and existing retain/recall evidence. Do not seed provider registries or infer that provider discovery creates a Space.
   - Treat user-reported errors as ground truth. Verify the desired-state and current behavior, not whether the same error can be reproduced again.

## Report contract

- List findings from **HIGH to LOW severity**. For every finding include:
  - exact resource/scope and current impact;
  - evidence: query, metric value, log/event, trace, or ticket timeline with timestamps;
  - confidence and any explicitly unverified assumption;
  - minimal fix plan: Git PR versus one-off live action, verification steps, and rollback/stop condition.
  - when a conservative runbook applies, include `runbook_id`, `target_repo`, `pr_steps`, and `post_merge_verify`. Use IDs from `cluster-remediation.md`; otherwise emit `runbook_id: no_recommendation`.
  - if the current state already satisfies the runbook, classify it as healthy and recommend `cluster-verification`, never a duplicate PR. If the fix is merged on `main` but not yet applied, classify it as `PENDING_RECONCILE`, never a duplicate PR.
  - do not call `ask` during diagnosis. `ask` is reserved for `cluster-remediation` only when no conservative recommendation exists.
- Separate active failures, imminent risks, stale/noise/expected conditions, and already healthy evidence.
- Reproduce signals from raw data instead of trusting ticket text or model hypotheses. Do not default to disabling alerts, health checks, or LLM guardrails.
