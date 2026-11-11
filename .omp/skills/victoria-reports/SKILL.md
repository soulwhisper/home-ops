---
name: victoria-reports
description: >
  Use for read-only evidence gathering and reporting from the Victoria
  observability stack: VictoriaMetrics metric queries, VictoriaLogs LogsQL
  grep, VictoriaTraces trace lookup, Flux/alert state, incident timelines, and
  one-file HTML reports. Trigger on "victoria", "vmsingle", "vmauth", "LogsQL",
  "query metrics", "grep logs", "trace lookup", "observability report",
  "incident timeline", "html report", "指标报告", "日志检索", "链路排查",
  "可观测性报告".
---

# Victoria stack reports

Turn an observability question into a bounded, read-only evidence set and one
self-contained HTML report. The report is the deliverable; raw JSON is not.

## Hard boundaries

- Read-only. No `kubectl apply/edit/delete/scale/restart`, no `flux reconcile`,
  no ticket or file mutations outside the report. Query APIs only.
- Never print Secret values, bearer tokens, API keys, passwords, or private
  keys. Redact matching log lines and state that redaction occurred.
- Bound every query: explicit time window, line/series limit, and a recorded
  reason for the window. Retained windows are metrics 30d, logs 90d, traces
  14d; an older range is not "no problem", it is "not retained".
- Empty is not healthy. Separate `no data`, `zero`, `not collected`, and
  `query failed`; check `up`, scrape health, and the selected window before
  drawing a conclusion.
- Every finding needs a timestamp, the exact query, and an observed value or
  bounded excerpt. Never invent a row, metric, log line, or trace.
- Do not treat silence, an empty Alertmanager response, or a quiet log stream
  as proof of healing.
- Write the report in Simplified Chinese (`lang="zh-CN"`): headings, verdicts,
  findings, prose, table headers, and chart labels. Keep identifiers, label
  keys, query text, and units verbatim.
- Write the report to `temp/<YYYYMMDD-HHMMSS>-<slug>.html` (create `temp/` if
  needed). `temp/` is gitignored; never commit a generated report.

## Access

These chapters are adapted from `homelab-gitops` so this skill works alone.
Run from the repo root so `.mise.toml` supplies the cluster environment.

```bash
kubectl config current-context           # confirm the cluster first
kubectl get nodes -o wide
kubectl -n monitoring-system get svc,httproute,pods
```

Port-forward the three backends in one shell. Capture each PID and clean both
the forwards and the private temp directory on exit:

```bash
TMP=$(mktemp -d)
pids=()
cleanup() { kill "${pids[@]}" 2>/dev/null || true; rm -rf "$TMP"; }
trap cleanup EXIT

kubectl -n monitoring-system port-forward svc/vmsingle-victoria-metrics-cluster 8428:8428 &
pids+=($!)
kubectl -n monitoring-system port-forward svc/victoria-logs-server 9428:9428 &
pids+=($!)
kubectl -n monitoring-system port-forward svc/victoria-traces 10428:10428 &
pids+=($!)
# optional: vmalert 8080, vmalertmanager 9093

# retry until the local forward binds; do not mistake startup latency for an outage
curl -fsS --retry 5 --retry-delay 1 --retry-connrefused \
  'http://127.0.0.1:8428/api/v1/query?query=1' >/dev/null
curl -fsS --retry 5 --retry-delay 1 --retry-connrefused \
  'http://127.0.0.1:9428/select/logsql/query?query=_time:1m&limit=1' >/dev/null
curl -fsS --retry 5 --retry-delay 1 --retry-connrefused \
  'http://127.0.0.1:10428/select/jaeger/api/services' >/dev/null
```

| Backend | Service (namespace `monitoring-system`) | Query surface | UI |
| --- | --- | --- | --- |
| Metrics | `vmsingle-victoria-metrics-cluster:8428` | Prometheus API `/api/v1/*` | VM UI through the gateway |
| Metrics proxy | `vmauth-victoria-metrics-cluster:8427` | `/api/v1/query.*`; `/api/v1/label/.*`; `/select/logsql/*` | — |
| Logs | `victoria-logs-server:9428` | LogsQL `/select/logsql/*` | Logs UI through the gateway |
| Traces | `victoria-traces:10428` | Jaeger API `/select/jaeger/*` | Traces UI through the gateway |
| Alerts | `vmalert-victoria-metrics-cluster:8080` | rules/alerts API | — |
| Alertmanager | `vmalertmanager-victoria-metrics-cluster:9093` | `/api/v2/*` | Alert UI through the gateway |

Port-forwarding bypasses gateway auth. Do not expose or share the forwarded
ports; do not use the public UIs for automated scraping.

## Label vocabulary humans care about

The archived Grafana boards (`basement-health.json`, `kopiur-slo.json`) are the
reference for the metric label rows (workload, alerts, HTTP/probes, storage,
Kopiur). The Flux, log, and trace rows were checked against live
`gotk_resource_info`, VictoriaLogs field names, and Jaeger process tags. Use
these in headings and `group by`; do not dump raw label maps.

| Signal | Labels that identify the thing a human cares about |
| --- | --- |
| Workload | `namespace`, `pod`, `container`, `node`, `service`, `job`, `instance` |
| Flux | `gotk_resource_info`: `exported_namespace`, `name`, `customresource_kind`, `ready`, `revision` |
| Alerts | `alertname`, `severity`, `alertstate`, `namespace` |
| HTTP / probes | `code`, `envoy_response_code_class`, `probe_success`, `up` |
| Storage | `persistentvolumeclaim`, `storageclass`, `pool`, `device`, `mountpoint` |
| Kopiur | `policy`, `name`, `kind`, `phase`; histograms carry `le` |
| Logs | `_time`, `_msg`, `_stream`, `kubernetes.pod_namespace`, `kubernetes.pod_name`, `kubernetes.container_name`, `kubernetes.pod_node_name`, `kubernetes.pod_labels.app.kubernetes.io/name`, `level` |
| Traces | `service.name`, `operationName`, `duration`, `status.code`, `span.kind` |

Aggregation rules:

- Group by the human entity, not the scrape target: `namespace`/`pod`/`service`
  before `instance`; `policy`/`name` before `pod`.
- `_stream` is a serialized label set; extract the named fields instead of
  printing it.
- `_msg` is high-cardinality. Aggregate first, then quote at most five redacted
  lines per finding.
- State the unit and window for every number (`5m rate`, `30d budget`, `bytes`,
  `µs`).

### Required label coverage and display

Every report must include a `标签覆盖` table and cover the custom-board label
domains. For each domain list the labels actually used, the query/population,
the chosen display, and an explicit `无数据`/`未采集` when empty:

| Domain | Labels to cover | Preferred display |
| --- | --- | --- |
| 工作负载 | `namespace`, `pod`, `container`, `node`, `service`, `job`, `instance`, `condition` | Table grouped by namespace/pod; top-N horizontal bar when comparing counts |
| 告警 | `alertname`, `severity`, `alertstate`, `namespace` | Table plus severity count cards |
| HTTP/探针 | `code`, `envoy_response_code_class`, `probe_success`, `up` | Table; line chart for a time series, bar for per-class counts |
| 存储 | `persistentvolumeclaim`, `storageclass`, `pool`, `device`, `mountpoint` | Table for current state; bar for top usage only when queried |
| Kopiur | `policy`, `name`, `kind`, `phase` | Table grouped by `policy`/`namespace` |
| Flux | `gotk_resource_info`: `exported_namespace`, `name`, `customresource_kind`, `ready`, `revision` | Table of not-Ready resources; count card when zero |
| 日志 | `_time`, `_msg`, `kubernetes.pod_namespace`, `kubernetes.pod_name`, `kubernetes.container_name`, `kubernetes.pod_node_name`, `kubernetes.pod_labels.app.kubernetes.io/name`, `level` | Top-N horizontal bar; bounded table/excerpts |
| 链路 | `service.name`, `operationName`, `duration`, `status.code`, `span.kind` | Table; latency/error bar only when spans were queried |
| 直方图 | `le` | Include in the query table when a histogram quantile is used; otherwise mark `未采集` |

Choose the display by data shape:

- Time series or trend → inline SVG line chart with time axis and units.
- Counts by category or top-N → horizontal bar chart, sorted, with values.
- Current state or mixed label dimensions → table.
- Empty result → an explicit `无数据` row; never render an empty chart.
- Inline SVG only: include `<title>`, `<desc>`, axis labels, a zero baseline,
  and no scripts or external chart libraries.

## Query cookbook

### Metrics

```bash
V=http://127.0.0.1:8428
START=$(date -u -d '6 hours ago' +%s)
END=$(date -u +%s)
curl -fsS --get "$V/api/v1/query" --data-urlencode 'query=sum(up)'
curl -fsS --get "$V/api/v1/query_range" \
  --data-urlencode 'query=sum by (namespace) (rate(container_cpu_usage_seconds_total[5m]))' \
  --data-urlencode "start=$START" --data-urlencode "end=$END" \
  --data-urlencode 'step=300'
curl -fsS --get "$V/api/v1/labels" \
  --data-urlencode "start=$START" --data-urlencode "end=$END"
curl -fsS --get "$V/api/v1/label/namespace/values" \
  --data-urlencode "start=$START" --data-urlencode "end=$END"
curl -fsS --get "$V/api/v1/series" \
  --data-urlencode 'match[]=gotk_resource_info' \
  --data-urlencode "start=$START" --data-urlencode "end=$END" \
  --data-urlencode 'limit=200'
```

- Use `query` for current verdicts and `query_range` for shape/trend. Estimate
  `series_count × range / step` and choose a step that keeps the response under
  ~1.5k points: 1m for ≤6h, 5m for ≤5d, 10m for 7d, 1h for 30d.
- Bound discovery too: pass the same `start`/`end` to labels and series, and
  cap `/api/v1/series` with `limit`.
- Use rate windows of at least 4× the scrape interval (scrapes are 30–60s);
  `[1m]` is usually noise.
- Flux state: `gotk_resource_info{ready="False"}` grouped by
  `exported_namespace`, `name`, `customresource_kind`. A stale `Ready` with an
  old `revision` is not convergence; compare the applied revision with the
  merge SHA.
- Alerts: `ALERTS{alertstate="firing"}` grouped by `alertname`, `severity`,
  `namespace`; use the retained series for history, not only current alerts.
- Missing series: check `up{job=...}` and scrape/rule health before concluding
  the workload is healthy. `RecordingRulesNoData` or a flat ingestion rate
  invalidates downstream conclusions.

### Logs (grep)

```bash
L=http://127.0.0.1:9428
Q='_time:1h kubernetes.pod_namespace:"selfhosted-apps" _msg:~"(?i)error|fail|timeout"'
curl -fsS --get "$L/select/logsql/query" --data-urlencode "query=$Q" --data-urlencode 'limit=200'

# field discovery, bounded to the same window
curl -fsS --get "$L/select/logsql/field_names" \
  --data-urlencode 'query=_time:1h' --data-urlencode 'limit=200'
curl -fsS --get "$L/select/logsql/stream_field_values" \
  --data-urlencode 'query=_time:1h' --data-urlencode 'field=kubernetes.pod_namespace' --data-urlencode 'limit=50'

# counts instead of raw lines
curl -fsS --get "$L/select/logsql/query" --data-urlencode \
  'query=_time:1h | stats by (kubernetes.pod_namespace, kubernetes.pod_name) count() as n | sort by (n desc) | limit 20' \
  --data-urlencode 'limit=20'
```

- LogsQL filters use `field:value`, `field:~"regex"` and `_time:<window>`.
  Start broad (`_time:15m`, namespace), then narrow by pod, container, and
  message pattern.
- `/select/logsql/query` returns JSON Lines; pipe through `jq -c` and count
  before reading. `/select/logsql/stats_query` returns a Prometheus-style
  vector; `/select/logsql/hits` returns timestamped counts for a histogram.
- `_time` is ingestion time; include the event time from `_msg` when the line
  carries one. Do not claim a cause from a line outside the chosen window.
- Logs may contain credentials. Bounded excerpts only; redact tokens, cookies,
  authorization headers, and connection strings before rendering.

### Traces

```bash
T=http://127.0.0.1:10428/select/jaeger
curl -fsS "$T/api/services"
curl -fsS "$T/api/services/<service>/operations"
curl -fsS --get "$T/api/traces" --data-urlencode 'service=<service>' \
  --data-urlencode "start=$(date -u -d '2 hours ago' +%s000000)" \
  --data-urlencode "end=$(date -u +%s000000)" --data-urlencode 'limit=20'
```

- Jaeger `start`/`end` are microseconds. `duration` is microseconds.
- Correlate a slow/error trace to logs by `service.name` and a ±1m span window;
  correlate to metrics with the same service and a ±2m window.
- No traces means "not sampled/collected", not "no failures" — tail sampling
  keeps errors, GenAI chat, and `tools/call` spans, plus a 10% baseline.

## Report contract

Write exactly one HTML file in Simplified Chinese with `lang="zh-CN"`. It must
open offline and contain no external CSS, JS, fonts, images, or fetches;
inline SVG is allowed. Support light/dark via `prefers-color-scheme` and print
with readable colors. Keep technical identifiers and label keys in their
original form.

Required sections, in order:

1. **标题与结论** — 标题、范围/问题、精确时间窗口（UTC 和本地）、生成时间、数据源、一句话结论与置信度。
2. **摘要** — 按严重度/状态和主要对象计数；数字必须与下方表格一致。
3. **图表** — 当数据形状适合时包含匹配图表：时间序列用折线图，Top-N/分类计数用横向条形图；当前状态/混合标签用表格；无数据时写“无数据”，不画空图。
4. **发现** — 按严重度从高到低排列。每行包含对象（使用人类可读标签）、严重度、观测值/状态、时间、置信度。
5. **证据** — 每个发现一段，包含精确查询、窗口、结果数和有界脱敏摘录；原始查询放在 `<details>` 中，禁止粘贴完整日志流或 JSON。
6. **标签覆盖** — 必显表格：标签域、实际使用的标签、查询/总体、展示方式，以及“无数据/未采集”。
7. **方法与限制** — 保留期、采样、缺失数据源、脱敏和未验证内容；区分 pending 与失败。
8. **附录** — 使用的标签和查询语句。仅在问题涉及时间演化时增加“时间线”。

Editing rules:

- Start from `assets/report.html`; replace every `{{PLACEHOLDER}}` (including
  `{{CHARTS}}` and `{{LABEL_COVERAGE_ROWS}}`) and repeat the marked
  table/detail blocks. Delete unused sections.
- HTML-escape all dynamic text (`&`, `<`, `>`, `"`). Do not inject query
  output as raw HTML.
- Prefer tables for current state and mixed labels; use inline SVG for shape
  (line/bar) with axes, units, a zero baseline, and `<title>`/`<desc>`. Do not
  draw decorative charts.
- Write the report to `temp/<YYYYMMDD-HHMMSS>-<slug>.html`; `temp/` is
  gitignored, so leave the generated artifact uncommitted. Report the path.
- If only one source answered, say so. Never present a metric-only hypothesis
  as confirmed by logs or traces.

## Workflow

1. State the question, window, entities, and what would count as evidence.
2. Confirm the context, open the port-forwards, and hit the three health
   probes. If a backend is down, report that first and use the remaining
   sources.
3. Discover labels/fields, then query narrow. Save raw outputs and exact
   commands under `$TMP`; keep only bounded, redacted excerpts in the report.
4. Cross-check: corroborate every high-severity finding with a second signal
   where possible; record the check that failed to corroborate.
5. Render one Chinese HTML file from the template, choosing a chart or table
   for each label domain.
6. Verify: row counts match raw results; timestamps lie inside the window;
   no unresolved placeholders; no external references; HTML parses; secrets
   absent; units and limits stated; every custom-board label domain appears in
   `标签覆盖` with a display or an explicit `无数据`. Open it in a browser when
   available.
7. Let the `EXIT` trap kill the port-forwards and remove `$TMP`; deliver the
   path, verdict, and limits in chat.

## Presentation principles

Adapted from the public `archify` skill: standalone HTML, inline SVG, no
external dependencies, theme-aware colors, semantic sections, and a
self-review before delivery. The report is static evidence, not an app: no
scripts, no animations, no interactive state.

## Extracted from homelab-gitops

- **Always-first commands** — context, nodes, non-ready pods, Flux state.
- **Reading resources** — `kubectl get/describe/logs/events`, restart counts
  and `lastState` before blaming resources.
- **Secrets** — never echo decrypted values; treat any `*.sops.yaml`,
  Secret payload, or token-bearing log line as sensitive.
- **Session rule 1 (eval means eval)** — investigation and reporting only;
  findings and recommendations, no edits or live mutations.

`homelab-gitops` remains the authority for mutations, storage, Talos, and
reconciliation. This skill is read-only and self-contained for evidence work.
