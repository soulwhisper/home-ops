# Basement alerting — design and coverage map

Companion to `basement-health.json`. Core rule: **the board visualizes; alerts
already exist.** Nothing on the board gets a new alert unless a real gap exists.
"Do not recreate" includes longer-duration variants, shorter-window variants,
and peak/off-hours-scoped variants of existing rules (an off-hours pattern
already exists in `ai-behavior-rules`; don't clone it).

## Panel → alert coverage

| Board panel | Existing alert(s) | New alert? |
|---|---|---|
| Critical / Warning / Pending rows | self-referential (reads `ALERTS`) | no |
| Scrape targets down | `TargetDown` | no |
| API server avail | `KubeAPIDown`, `KubeAPIInstanceUnreachable`, `KubeAPITerminatedRequests` + SLI recording rules | **YES — burn-rate (only real gap)** |
| Gateway avail | none anywhere in the ruleset | **YES — gateway 5xx burn-rate** |
| Ceph healthy time / bad PGs | ~50 `Ceph*` rules (`CephHealthWarning/Error`, `CephPGs*`, `CephOSD*`, mon quorum, MDS, pool fill, device prediction) | no |
| etcd leader flips | `etcdHighNumberOfLeaderChanges` (+ ~20 etcd rules: fsync, quota, fragmentation, member down) | **no — explicitly not recreated** |
| Backup freshness / oldest age | `KopiurBackupStale`, `KopiurLastBackupFailed`, `KopiurBackupConsecutiveFailures` (+12 more) | no |
| VM ingestion | vm-health family (vmsingle down, `RemoteWriteErrors`, `PersistentQueue*`, `RecordingRulesNoData`) | no |
| Basement pods not-ready | `KubePodNotReady` | no |
| Basement restarts | `KubePodCrashLooping` | no |
| Probes failing | `BlackboxProbeFailed` (+ `MacStudioModelServiceDown` for studio lanes) | no |
| Flux drift (not a panel) | `HelmReleaseReconciliationFailure`, `KustomizationReconciliationFailure` | no |

## The two justified additions

### 1. `SLOApiserverErrorBudgetBurn` (the only true gap)

Confirmed absent: `apiserver_request:burnrate*` = 0 series, no
`KubeAPIErrorBudgetBurn` in the ruleset. SLI recording rules exist
(`apiserver_request_sli_*`), nothing consumes them for paging.

- SLI: non-5xx ratio over `apiserver_request_total` (server-side; metrics-server
  re-exports lookalike client-side SLI series — always filter `job="apiserver"`)
- Target: 99.9% / 30d
- Fast: `burnrate5m > 14.4 and burnrate1h > 14.4` → critical
- Slow: `burnrate30m > 3 and burnrate6h > 3` → warning
- The 23:03Z apiserver-500 incident would have paged this in ~5 min

### 2. `SLOGateway5xxBurnRateSlow`

Zero alert coverage on the envoy datapath today. Gateway traffic is modest, so
**slow window only** initially:

- SLI: non-5xx ratio over `envoy_http_downstream_rq_xx`
  (label is `envoy_response_code_class`)
- Slow: `burnrate30m > 3 and burnrate6h > 3` → warning
- Rate gate: `and sum(rate(envoy_http_downstream_rq_xx[1h])) > 0.1` — avoids
  low-traffic jitter paging at 3AM
- Add a fast window only after the slow one proves quiet for a month

## Rollout protocol

1. `slo-rules.yaml` recording rules only → soak 24h, sanity-check against raw
2. Slow-burn as **warning** → soak 1 week
3. Fast-burn as **critical**
4. Basement board exprs swapped from raw to `slo:*` series

Rules must read recording rules — never board exprs. If the board breaks, the
signal path is unaffected.

## Deferred / rejected

- **ClickHouse log volume** (keeper 5.5M + server 2.8M lines/24h, ~95 lines/s):
  root cause of the recurring `TooManyLogs`. Fix is `logger.level=warning` on
  `ClickHouseCluster/default` (database-system) — deferred: needs an
  operator-driven restart of the shared stateful cluster; not a drive-by.
  Collector-side `excludeFilter` is metadata-only and would drop ERROR logs
  too — rejected.
- **etcd flips SLO / 24h variants**: covered by `etcdHighNumberOfLeaderChanges`;
  the board panel is the trend view of that alert, not a new one.
- **Backup 48h-stale variant**: covered by `KopiurBackupStale`; a second,
  longer window is alert spam, not coverage.
- **Per-app SLOs (`*-apps`)**: never. Alerts cover the app plane; renovate
  restarts are expected state, not budget burn.
