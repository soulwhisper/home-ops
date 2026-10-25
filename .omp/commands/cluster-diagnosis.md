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

## Report contract

- List findings from **HIGH to LOW severity**. For every finding include:
  - exact resource/scope and current impact;
  - evidence: query, metric value, log/event, trace, or ticket timeline with timestamps;
  - confidence and any explicitly unverified assumption;
  - minimal fix plan: Git PR versus one-off live action, verification steps, and rollback/stop condition.
- Separate active failures, imminent risks, stale/noise/expected conditions, and already healthy evidence.
- Reproduce signals from raw data instead of trusting ticket text or model hypotheses. Do not default to disabling alerts, health checks, or LLM guardrails.
