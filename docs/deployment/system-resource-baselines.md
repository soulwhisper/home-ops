# System namespace resource baselines

Reference only. **No `*-system` HelmRelease values were changed by this
document.** Use it when diagnosing `KubeCPUOvercommit`, missing requests, or
unexpected evictions; apply changes separately with a rollout plan.

- Measured: 2026-11-09, 7-day VictoriaMetrics history
- Scope: HelmReleases in `gitops-system`, `storage-system`,
  `monitoring-system`, `database-system`, `security-system`,
  `networking-system`, and `kube-system`
- Chart values: `helm show values` at the pinned `OCIRepository` tag
- Usage: CPU P95 and max working-set memory per pod owner/container

## Why this exists

The first request-tuning pass intentionally skipped `*-system` namespaces.
The audit found two different failure modes:

1. Several charts expose `resources` but the HelmRelease leaves it at `{}`.
2. Chart examples are not safe defaults for this cluster. Cilium's commented
   example caps the agent at `4Gi`, while the live agent working set is about
   `9Gi` on every node.

Requests affect scheduling and `KubeCPUOvercommit`; limits are optional and
must not be copied from chart examples without checking measured peaks.

## Chart support matrix

`empty` means the key exists but the chart default is `{}` (often with a
commented example). `none` means the HelmRelease does not set it. A non-empty
chart default applies even when Git shows `none`.

### database-system

| App | Chart | Resource key(s) | Chart default / example | Current Git |
| --- | --- | --- | --- | --- |
| `clickhouse-operator` | `clickhouse-operator@0.0.8` | `manager.resources` | requests `10m/64Mi`, limits `500m/128Mi` | requests `10m/64Mi`, limits `500m/256Mi` |
| `cnpg-operator` | `cloudnative-pg@0.29.1` | `resources` | empty; commented `100m/200Mi` | none |
| `cnpg-barman` | `plugin-barman-cloud@0.8.1` | `resources` | empty | none |
| `dragonfly-operator` | `dragonfly-operator@v1.7.1` | `manager.resources` | empty | none |

### gitops-system

| App | Chart | Resource key(s) | Chart default / example | Current Git |
| --- | --- | --- | --- | --- |
| `flux-instance` | `flux-instance@0.62.1` | `healthcheck.resources` | requests `100m/64Mi`, limits `1/1Gi` | none; Flux controllers are not exposed as per-controller resources by this chart |
| `flux-operator` | `flux-operator@0.62.1` | `resources` | requests `100m/64Mi`, limits `2/1Gi` | none |
| `system-upgrade-controller` | `tuppr@0.5.13` | `resources` | empty | none |

### kube-system

| App | Chart | Resource key(s) | Chart default / example | Current Git |
| --- | --- | --- | --- | --- |
| `cilium` | `cilium@1.20.4` | `resources` (agent), `cni.resources`, `nodeinit.resources`, `encryption.ztunnel.resources`, plus hubble/certgen paths | agent empty; commented requests `100m/512Mi`, limits `4/4Gi` (unsafe here: measured ~9Gi) | none |
| `coredns` | `coredns@1.50.2` | `resources` | requests/limits `100m/128Mi` | requests `100m/128Mi`, memory limit `256Mi` |
| `descheduler` | `descheduler@0.37.0` | `resources` | requests/limits `500m/256Mi` | none (chart default applies) |
| `frr-k8s` | `frr-k8s@0.0.27` | `resources` (controller), `frr.resources`, `reloader.resources`, `frrMetrics.resources`, `frrStatus.resources`, init-container paths | all empty | none |
| `intel-device-plugins-operator` | `intel-device-plugins-operator@0.36.0` | `resources` | requests `100m/100Mi`, limits `100m/120Mi` | none |
| `intel-device-plugins-gpu` | `intel-device-plugins-gpu@0.37.1` | not exposed | — | none |
| `metrics-server` | `metrics-server@3.14.0` | `resources`, `addonResizer.resources` | requests `100m/200Mi`; addonResizer `40m/25Mi` | none |
| `reloader` | `reloader@2.2.19` | `deployment.resources` | empty | none |
| `spegel` | `spegel@0.8.1` | `resources` | requests/limits memory `128Mi`; no CPU | none (memory default applies) |
| `gateway-api-crds` | `gateway-api-crds@1.6.2` | CRD-only | — | — |

### monitoring-system

| App | Chart | Resource key(s) | Chart default / example | Current Git |
| --- | --- | --- | --- | --- |
| `blackbox-exporter` | `prometheus-blackbox-exporter@11.21.1` | `resources`, `configReloader.resources` | configReloader `10m/20Mi` + `50Mi` limit; main empty | none |
| `grafana-operator` | `grafana-operator@5.25.0` | `resources` | empty | none |
| `headlamp` | `headlamp@0.46.0` | `resources` | empty | none |
| `kube-state-metrics` | `kube-state-metrics@9.0.0` | `resources` | empty | none |
| `langfuse` | `app-template@5.3.0` | `controllers.{app,worker}.containers.*.resources` | no chart defaults | app `1` CPU + `2Gi` limit; worker `1` CPU + `4Gi` limit |
| `node-exporter` | `prometheus-node-exporter@5.0.0` | `resources` | empty; commented `100m/64Mi` | requests `23m`; memory limit `64M` |
| `opentelemetry-collector` | `opentelemetry-collector@0.178.2` | `resources` | empty | requests `10m/512Mi`, memory limit `1Gi` |
| `prometheus-crds` | `prometheus-operator-crds@33.0.1` | CRD-only | — | — |
| `robusta` | `robusta@0.54.0` | `kubewatch.resources`, `runner.resources`, `holmes.resources`, `kube-prometheus-stack.*` | non-empty example defaults | runner `50m/256Mi` + `1Gi`; holmes `100m/1Gi` + `2Gi` |
| `silence-operator` | `silence-operator@0.22.0` | `resources` | requests `50m/50Mi`, limits `50m/100Mi` | none (chart default applies) |
| `smartctl-exporter` | `prometheus-smartctl-exporter@0.19.1` | `resources` | empty; commented `100m/128Mi` | none |
| `victoria-logs-server` | `victoria-logs-single@0.13.11` | `server.resources`, `vector.resources` | empty; commented `500m/512Mi` | init container `50m/64Mi` + `256Mi`; main none |
| `victoria-logs-collector` | `victoria-logs-collector@0.3.8` | `resources` | empty; commented `100m/128Mi` | none |
| `victoria-metrics-crds` | `victoria-metrics-operator-crds@0.15.2` | CRD-only | — | — |
| `victoria-metrics-cluster` | `victoria-metrics-k8s-stack@0.97.1` | `vmsingle.*`, `vmagent.spec.resources`, `alertmanager.*`, `vlselect.*`, `vlinsert.*` | mostly empty/commented | vmagent `200m/256Mi` + `2/512Mi`; init `50m/64Mi`; vmsingle storage only |
| `victoria-metrics-operator` | `victoria-metrics-operator@0.68.2` | `cleanup.resources`, `upgrade.resources` | cleanup `100m/56Mi` + `500m/256Mi`; upgrade empty | none |
| `victoria-traces` | `victoria-traces-single@0.1.12` | `server.resources` | empty; commented `500m/512Mi` | init container only; main none |
| `vmware-exporter` | `app-template@5.3.0` | `controllers.*.containers.*.resources` | no chart defaults | `10m/64Mi` + `256Mi` |
| `webhook-relay` | `app-template@5.3.0` | `controllers.*.containers.*.resources` | no chart defaults | app `10m` + `128Mi`; tickets `10m/32Mi` + `256Mi` |

### networking-system

| App | Chart | Resource key(s) | Chart default / example | Current Git |
| --- | --- | --- | --- | --- |
| `agentgateway` | `agentgateway@1.7.0` | `resources` | requests `100m/128Mi` | none (chart default applies) |
| `mcp-guardrails` | `app-template@5.3.0` | `controllers.*.containers.*.resources` | no chart defaults | `2/512Mi` + `6/4Gi` |
| `externaldns-adguard` | `external-dns@1.23.0` | `resources`, `webhook.resources` | empty | `16m`; memory limit `90M` |
| `kgateway` | `kgateway@2.6.0-main` | `resources` | empty | none |
| `agentgateway-crds`, `kgateway-crds` | CRD-only | — | — | — |

### security-system

| App | Chart | Resource key(s) | Chart default / example | Current Git |
| --- | --- | --- | --- | --- |
| `authentik` | `authentik@2026.8.5` | `server.resources`, `worker.resources` | empty | none |
| `cert-manager` | `cert-manager@v1.21.3` | `resources`, `webhook.resources`, `cainjector.resources` | empty; commented examples per component | none |
| `external-secrets` | `external-secrets@2.14.0` | `resources`, `webhook.resources`, `certController.resources` | empty | `10m/64Mi` + `256Mi`; webhook `10m/32Mi` + `128Mi` |
| `kyverno` | `kyverno@3.9.2` | `admissionController.resources`, `backgroundController.resources`, `cleanupController.resources`, `reportsController.resources`, plus test/init paths | non-empty per-controller defaults | all four controllers set |
| `onepassword-connect` | `connect@2.4.3` | `connect.api.resources`, `connect.sync.resources` | api `200m` + `128Mi` limit; sync empty | api `200m/128Mi` + `256Mi`; sync `50m/64Mi` + `128Mi` |

### storage-system

| App | Chart | Resource key(s) | Chart default / example | Current Git |
| --- | --- | --- | --- | --- |
| `csi-driver-nfs` | `csi-driver-nfs@4.13.6` | `controller.resources`, `node.resources`, `externalSnapshotter.resources` | non-empty per-sidecar defaults | none |
| `kopiur` | `kopiur@0.10.18` | `resources`, `webhook.resources`, `ui.resources` | non-empty per-component defaults | `100m`; memory limit `2Gi` |
| `rook-ceph` | `rook-ceph@1.21.2` | `resources` (operator) | requests `200m/128Mi`; limit `512Mi` | none (chart default applies) |
| `rook-ceph-cluster` | `rook-ceph-cluster@1.21.2` | `cephClusterSpec.resources`, `toolbox.resources`, filesystem/object gateway resources | non-empty examples | mgr limit `2Gi`; osd limit `4Gi`; prepareosd `500m/50Mi`; metadata `100m/1Gi` + `4Gi`; gateway `100m` + `1Gi` |
| `rook-ceph-drivers` | `ceph-csi-drivers@1.1.0` | `controllerPlugin.*`, `nodePlugin.*` | empty; commented per-sidecar examples | attacher/omap/plugin/registrar/provisioner set |
| `snapshot-controller` | `snapshot-controller@5.4.0` | `controller.resources`, `webhook.resources` | empty | none |

## Suggested values for current gaps

These are the only pod owners whose live workload spec has a missing CPU
request, memory request, or memory limit. Values are **per container** and are
suggestions, not applied. CPU request = P95 × 1.2 rounded up to 5m (minimum
10m). Memory request = peak × 1.2 rounded up to 16Mi. Memory limit = 2× peak,
rounded up to 64Mi with a 64Mi floor, and is optional.

| Owner | Container | Current req / limit | P95 CPU | Peak mem | Suggested requests | Suggested limit | Chart value path |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `kube-system/cilium` | `cilium-agent` | none | 313m | 9089Mi | `380m / 10912Mi` | no limit (CNI) | `resources` |
| `monitoring-system/victoria-logs-server` | `vlsingle` | none | 124m | 1915Mi | `150m / 2304Mi` | `3840Mi` | `server.resources` |
| `monitoring-system/victoria-logs-collector` | `vlagent` | none | 47m | 273Mi | `60m / 336Mi` | `576Mi` | `resources` |
| `monitoring-system/victoria-traces` | `vtsingle` | none | 18m | 257Mi | `25m / 320Mi` | `576Mi` | `server.resources` |
| `kube-system/frr-k8s` | `controller` | none | 2m | 73Mi | `10m / 96Mi` | `192Mi` | `resources` |
| `kube-system/spegel` | `registry` | `0m/128Mi`, limit `128Mi` | 20m | 65Mi | `25m`; keep memory `128Mi` | keep `128Mi` | `resources` |
| `kube-system/frr-k8s` | `frr` | none | 2m | 47Mi | `10m / 64Mi` | `128Mi` | `frr.resources` |
| `kube-system/frr-k8s` | `frr-metrics` | none | 5m | 35Mi | `10m / 48Mi` | `128Mi` | `frrMetrics.resources` |
| `monitoring-system/smartctl-exporter-0` | `main` | none | 2m | 32Mi | `10m / 48Mi` | `64Mi` | `resources` |
| `kube-system/frr-k8s` | `frr-status` | none | 2m | 24Mi | `10m / 32Mi` | `64Mi` | `frrStatus.resources` |
| `monitoring-system/vmalertmanager-victoria-metrics-cluster` | `config-reloader` | `10m/25Mi`, no limit | 1m | 21Mi | `10m / 32Mi` | `64Mi` | `VMAlertmanager.spec.configReloaderResources` (CRD, not chart values) |
| `monitoring-system/node-exporter` | `node-exporter` | `23m/0Mi`, limit `61Mi` | 6m | 17Mi | `10m / 32Mi` | keep `64Mi` | `resources` |
| `kube-system/frr-k8s` | `reloader` | none | 0m | 7Mi | `10m / 32Mi` | `64Mi` | `reloader.resources` |

### Notes on the suggestions

- **Cilium:** the chart example (`4Gi` limit) is below the measured working
  set. Do not use it. A ~10.9Gi request per node is the measured requirement;
  omit the memory limit unless node capacity is checked.
- **VRAM/CNI and Ceph data paths:** prefer requests first and no hard memory
  limits; limit-induced OOM restarts are worse than a temporary overcommit.
- **vlagent / vtsingle:** the chart exposes `resources`; the app currently sets
  only init-container resources.
- **vmalertmanager config-reloader:** generated by the VictoriaMetrics
  operator, not the k8s-stack chart. Set it through the VMAlertmanager CRD
  field `spec.configReloaderResources`, not the Helm chart values.
- **Chart-default-only apps:** `descheduler`, `silence-operator`,
  `agentgateway`, `rook-ceph`, `spegel` already receive a non-empty chart
  default; Git showing `none` does not mean the pod has no requests.

## Tooling: flate and the parked tree

`kubernetes/parked/` contains archived Kustomizations whose `spec.path` still
points at the active tree. flate scans the whole Git tree, so a full
`flate build hr` used to fail on those paths even though they are not deployed.

The repo-root `.krmignore` now excludes `kubernetes/parked/`:

```text
kubernetes/parked/
```

Verification: `flate build hr --no-progress` renders the full tree with
`rc=0` (37,085 lines). The ignore file must be committed; flate reads the
Git tree, not untracked working-tree files.
