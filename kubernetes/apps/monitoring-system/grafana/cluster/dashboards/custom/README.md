# Custom dashboards — design notes

Repo-owned Grafana boards (not vendir-managed). Vendored boards decay by metric-name
drift against the running software (measured 2026-09: kopiur 45%, cert-manager 24%,
hubble ~15% fresh coverage); these boards are reviewed in PR like code.

## The two-plane model

| Plane | Namespaces | Signal path |
|---|---|---|
| **Basement** (must stay stable) | kube-system, networking-system, storage-system, database-system, monitoring-system, security-system, gitops-system | SLO budgets + this board + burn-rate alerts (planned) |
| **App plane** (`*-apps`) | selfhosted/media/smarthome/servitor/worker/gaming-apps | **Alerts only, no SLOs.** Apps churn (renovate rollouts, OOM, dev breakage) and self-heal; per-app SLOs would page noise. Kube* alerts with `for:` durations encode "sustained breakage only". |

Nothing in `*-apps` ever lands on the basement board. Renovate restarts are expected
state, not budget burn.

## `basement-health.json` — "Basement — Failure Revealing"

The Default-folder headline board. Five-second verdict: **is anything in the
basement suspicious?** Red panel → drilldown board (the curated 17-board set) or
hand to an agent. Three rows:

1. **On fire right now** — live alert state from vmalert's `ALERTS` series:
   criticals, warnings, pending (earliest suspicion), scrape targets down.
2. **SLO budgets (30d)** — apiserver availability, gateway availability, ceph
   healthy-time, backup freshness, etcd leader flips, VM ingestion continuity
   (the meta-SLO: if ingestion flatlines, every other panel lies).
3. **Weak signals** — erosion before it pages: basement pods not-ready, bad ceph
   PGs, oldest backup age, probe failures, restart waves, etcd flips/h.

Row 3 reads raw metrics (not alert state), so silenced alerts can't blind it.

### Panel → drilldown map

| Panel | Drilldown |
|---|---|
| API server avail | Kubernetes / System / API Server (`k8s_system_apisrv`) |
| Gateway avail | Envoy Global (`heHhNSFf6Na8vIZWRs8H`) |
| Ceph panels | Ceph Cluster (`tbO9LAiZK`) |
| Backup panels | Kopiur — Backup SLO (`kopiur-slo`) |
| Pod/restart panels | Kubernetes / Views / Namespaces (`k8s_views_ns`) |
| VM ingest | metrics.noirprime.com (vmui) |

## `kopiur-slo.json` — backup SLO

Replaces the vendored kopiur 0.10.9 board, which references metric families the
0.10.9 operator does not emit. Tracks staleness, consecutive failures, repo
health, backup size/duration/files, controller reconcile p95 from the 35 live
`kopiur_*` families.

### Known data caveats

- **API server latency panels** (in the vendored k8s-system-api-server board)
  read `apiserver_request_sli_*` series re-exported by **metrics-server**
  (client-side view of its own calls) — the server-side buckets are dropped at
  vmagent for cardinality (~18k series) and the trade-off is kept deliberately.
  Burn-rate SLOs use `apiserver_request_total{job="apiserver"}` (unaffected).
- **Probes failing panel**: while the MacStudio is down it reads the number of
  studio probes (3 after the 8001/8002 media-lane retirement; 5 before).
  Post-recovery, any value > 0 is a consumed lane down and actionable.
- **Ceph healthy-time gauge** is alert-derived (% of 30d hours with no
  `CephHealth*` alert firing), not metric-derived: `ceph_health_status`
  carries stale series from dead mgr pods that poison naive `avg_over_time`.

## Gaps (explicitly deferred)

- **No `slo:*` recording rules yet.** The board queries raw metrics; planned rules
  (`slo-rules.yaml` in `victoria-metrics/cluster/`) will record
  `slo:<domain>:burnrate5m/1h/6h/3d` and error-budget series. Board exprs then
  swap 1:1 to the recorded names — alerts read the rules, never the board.
- **No burn-rate alerting yet.** Confirmed missing: `apiserver_request:burnrate*`
  (0 series), no `KubeAPIErrorBudgetBurn`. Multi-window design: fast
  (14.4× budget, 1h+5m → critical) + slow (3×, 6h+30m → warning).
- **Gateway SLO jitter at low RPS.** Ratio SLOs on low-traffic gateways may need
  `> 0.1 req/s` gating or 1h-minimum windows when rules land.
- **Flux health not on the board** — ksm exports only `gotk_resource_info` (no
  condition series); covered indirectly by `HelmReleaseReconciliationFailure` in
  Row 1.
- **30d windows run on ~11d of retention** — gauges read "so far", honest only
  after 30d of history.

## Risks

- **Wrong-denominator alerts page at 3AM** → recording rules soak 24h before any
  alert is attached; slow-burn ships as warning first, fast-burn a week later.
- **Board sprawl** → one headline board only; drilldowns stay in the curated set.
  New panels require a "what alert covers this otherwise?" answer.
- **Metric drift** → these boards are repo-owned and PR-reviewed; every expr was
  validated against live vmsingle before commit (all 16 pass).
- **Silence-hidden rot** → Row 3 bypasses alert state by design; a silenced rule
  (e.g. current TooManyLogs/TooManyScrapeErrors silences) still shows up as raw
  counts.

## Rollout

1. ✅ `basement-health.json` + `kopiur-slo.json` + this doc (PR #3753)
2. `slo-rules.yaml` recording rules → soak 24h, sanity-check against raw
3. Slow-burn alerts (warning) → soak 1 week
4. Fast-burn alerts (critical)
5. Board exprs swapped to `slo:*` recorded series
