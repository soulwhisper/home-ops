# Acceptance criteria by finding class

"Fixed" is only real with evidence. Each class has its own bar — run the
verification and paste the one-line result into the closing comment.

## Alert ticket (robusta / alertmanager)

Root cause eliminated AND the raw rule condition is normal for the same
resource/labels. Record the metric/log before-and-after and a matching Robusta
resolution (`failure: false` or `ends_at`) in the incident timeline. Honor any
`keep_firing_for`, scrape/evaluation, and notification delays.

Alertmanager's v2 API exposes `active`, `suppressed`, and `unprocessed`, **not**
a retained `resolved` state. Inspect the exact alert/fingerprint rather than
grep-counting a substring:

```bash
kubectl get --raw '/api/v1/namespaces/monitoring-system/services/http:vmalertmanager-victoria-metrics-cluster:9093/proxy/api/v2/alerts?active=true&silenced=true&inhibited=true&unprocessed=true' | \
  jq --arg name '<alertname>' --arg fp '<fingerprint>' \
    '[.[] | select(.labels.alertname == $name and .fingerprint == $fp) |
      {fingerprint, status: .status.state, silencedBy: .status.silencedBy,
       inhibitedBy: .status.inhibitedBy, startsAt, endsAt}]'
```

Suppression is not healing. An empty API result alone is not proof of resolution
or of a healthy detector. Do not close without the condition and resolution
evidence; closure remains human-controlled.

## ScheduledHealthCheck finding

Re-ask the same question (same toolset scope) and get a clean answer, or the
underlying condition measurably changed (e.g. pool growth rate back under
threshold). Paste the before/after numbers.

## Kyverno audit ticket

For CREATE/UPDATE findings, inspect the live PolicyReport and remediate the
violating object. A DELETE PolicyReport can disappear with its Pod, so it is
**not** historical evidence for `audit-unexpected-pod-deletes`.

After a port-forward to `svc/victoria-logs-server` (`9428:9428`), query the durable
PolicyViolation stream for the observation window:

```bash
curl -fsSG http://127.0.0.1:9428/select/logsql/query \
  --data-urlencode 'query=_time:24h "audit-unexpected-pod-deletes" | fields _time,_msg,object.metadata.uid,object.eventTime,object.series.lastObservedTime,object.series.count'
```

The note carries the policy/rule, actor, and target namespace/name. Compare event
UID plus event/series timestamps/counts: collector restart recovery can replay
an event, and Kubernetes can aggregate repeated occurrences. Paste the relevant
records and before/after action evidence; do not equate delivery count with
distinct deletes.

Before treating a quiet 24h window as evidence, establish collector/leader and
VictoriaLogs health with no collection gaps, and verify intended actors still
work. A zero-result query alone cannot prove compliance. Event TTL, in-memory
queue/retry limits, and collector downtime can lose events; this stream does not
replace a complete API audit backend.

## Config / docs ticket

Render + lint + CI all green, and every reference site agrees (no half-renames):

```bash
just k8s render-ks <ns> <ks> | kubectl diff -f -
prek run
```

## Observation window

Alert and kyverno classes: re-check after 24h before calling it durable.
Config classes: one green reconcile is enough.
