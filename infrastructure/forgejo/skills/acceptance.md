# Acceptance criteria by finding class

"Fixed" is only real with evidence. Each class has its own bar — run the
verification and paste the one-line result into the closing comment.

## Alert ticket (robusta / alertmanager)

Root cause eliminated AND the alert is `resolved` in vmalertmanager
(`vmalertmanager-victoria-metrics-cluster.monitoring-system:9093`) within the
rule's `for:` window + one scrape interval — not silenced, not absent from
the payload.

```bash
kubectl -n monitoring-system exec deploy/vmalertmanager-victoria-metrics-cluster -- \
  wget -qO- http://localhost:9093/api/v2/alerts | grep -c '<alertname>'
```

## ScheduledHealthCheck finding

Re-ask the same question (same toolset scope) and get a clean answer, or the
underlying condition measurably changed (e.g. pool growth rate back under
threshold). Paste the before/after numbers.

## Kyverno audit ticket

The violating object class is remediated AND the corresponding PolicyReport
shows zero new entries for the policy over one audit cycle:

```bash
kubectl get policyreport -A -o json | \
  jq '[.items[].results[] | select(.policy=="<policy>" and .result=="fail")] | length'
```

## Config / docs ticket

Render + lint + CI all green, and every reference site agrees (no half-renames):

```bash
just k8s render-ks <ns> <ks> | kubectl diff -f -
prek run
```

## Observation window

Alert and kyverno classes: re-check after 24h before calling it durable.
Config classes: one green reconcile is enough.
