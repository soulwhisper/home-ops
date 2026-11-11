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

> **Pre-#4564 snapshot.** This document records the values used for the
> measurement. PR #4564 applies a subset of these requests (and no limits);
> for current scheduling, use Git HEAD or `kubectl get ... -o yaml`.

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

| App | Chart | Resource key(s) | Chart default / example | Git at measurement (2026-11-09) |
| --- | --- | --- | --- | --- |
| `cnpg-operator` | `cloudnative-pg@0.29.1` | `resources` | empty; commented `100m/200Mi` | none |
| `cnpg-barman` | `plugin-barman-cloud@0.8.1` | `resources` | empty | none |
| `dragonfly-operator` | `dragonfly-operator@v1.7.1` | `manager.resources` | empty | none |

### gitops-system

| App | Chart | Resource key(s) | Chart default / example | Git at measurement (2026-11-09) |
| --- | --- | --- | --- | --- |
| `flux-instance` | `flux-instance@0.62.1` | `healthcheck.resources`; controller resources via `instance.kustomize.patches` | healthcheck requests `100m/64Mi`, limits `1/1Gi` | patches set source-controller `100m/256Mi` + `1Gi`, kustomize-controller `100m/256Mi` + `2Gi`, helm-controller `100m/256Mi` + `2Gi`; notification-controller none |
| `flux-operator` | `flux-operator@0.62.1` | `resources` | requests `100m/64Mi`, limits `2/1Gi` | none |
| `system-upgrade-controller` | `tuppr@0.5.13` | `resources` | empty | none |

### kube-system

| App | Chart | Resource key(s) | Chart default / example | Git at measurement (2026-11-09) |
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

| App | Chart | Resource key(s) | Chart default / example | Git at measurement (2026-11-09) |
| --- | --- | --- | --- | --- |
| `blackbox-exporter` | `prometheus-blackbox-exporter@11.21.1` | `resources`, `configReloader.resources` | configReloader `10m/20Mi` + `50Mi` limit; main empty | none |
| `kube-state-metrics` | `kube-state-metrics@9.0.0` | `resources` | empty | none |
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
| `victoria-metrics-operator` | `victoria-metrics-operator@0.68.2` | `resources`, `cleanup.resources`, `upgrade.resources` | operator empty; cleanup `100m/56Mi` + `500m/256Mi`; upgrade empty (commented `80m/120Mi` + `120m/320Mi`) | none |
| `victoria-traces` | `victoria-traces-single@0.1.12` | `server.resources` | empty; commented `500m/512Mi` | init container only; main none |
| `vmware-exporter` | `app-template@5.3.0` | `controllers.*.containers.*.resources` | no chart defaults | `10m/64Mi` + `256Mi` |
| `webhook-relay` | `app-template@5.3.0` | `controllers.*.containers.*.resources` | no chart defaults | app `10m` + `128Mi`; tickets `10m/32Mi` + `256Mi` |

### networking-system

| App | Chart | Resource key(s) | Chart default / example | Git at measurement (2026-11-09) |
| --- | --- | --- | --- | --- |
| `agentgateway` | `agentgateway@1.7.0` | `resources` | requests `100m/128Mi` | none (chart default applies) |
| `mcp-guardrails` | `app-template@5.3.0` | `controllers.*.containers.*.resources` | no chart defaults | `2/512Mi` + `6/4Gi` |
| `externaldns-adguard` | `external-dns@1.23.0` | `resources`, `webhook.resources` | empty | `16m`; memory limit `90M` |
| `kgateway` | `kgateway@2.6.0-main` | `resources` | empty | none |
| `agentgateway-crds`, `kgateway-crds` | CRD-only | — | — | — |

### security-system

| App | Chart | Resource key(s) | Chart default / example | Git at measurement (2026-11-09) |
| --- | --- | --- | --- | --- |
| `authentik` | `authentik@2026.8.5` | `server.resources`, `worker.resources` | empty | none |
| `cert-manager` | `cert-manager@v1.21.3` | `resources`, `webhook.resources`, `cainjector.resources` | empty; commented examples per component | none |
| `external-secrets` | `external-secrets@2.14.0` | `resources`, `webhook.resources`, `certController.resources` | empty | `10m/64Mi` + `256Mi`; webhook `10m/32Mi` + `128Mi` |
| `onepassword-connect` | `connect@2.4.3` | `connect.api.resources`, `connect.sync.resources` | api `200m` + `128Mi` limit; sync empty | api `200m/128Mi` + `256Mi`; sync `50m/64Mi` + `128Mi` |

### storage-system

| App | Chart | Resource key(s) | Chart default / example | Git at measurement (2026-11-09) |
| --- | --- | --- | --- | --- |
| `csi-driver-nfs` | `csi-driver-nfs@4.13.6` | `controller.resources`, `node.resources`, `externalSnapshotter.resources` | non-empty per-sidecar defaults | none |
| `kopiur` | `kopiur@0.10.18` | `resources`, `webhook.resources`, `ui.resources` | non-empty per-component defaults | `100m`; memory limit `2Gi` |
| `rook-ceph` | `rook-ceph@1.21.2` | `resources` (operator) | requests `200m/128Mi`; limit `512Mi` | none (chart default applies) |
| `rook-ceph-cluster` | `rook-ceph-cluster@1.21.2` | `cephClusterSpec.resources`, `toolbox.resources`, filesystem/object gateway resources | non-empty examples | mgr limit `2Gi`; osd limit `4Gi`; prepareosd `500m/50Mi`; metadata `100m/1Gi` + `4Gi`; gateway `100m` + `1Gi` |
| `rook-ceph-drivers` | `ceph-csi-drivers@1.1.0` | `controllerPlugin.*`, `nodePlugin.*` | empty; commented per-sidecar examples | attacher/omap/plugin/registrar/provisioner set |
| `snapshot-controller` | `snapshot-controller@5.4.0` | `controller.resources`, `webhook.resources` | empty | none |

## Suggested values for current gaps

Values are fills only; do not reduce an existing request just because the
P95 is lower. Requests are preferred; limits are optional and the memory
limit column keeps any existing limit.

All pod owners in the audited namespaces that could be mapped to a live
workload and that have at least one missing CPU request, memory request, or
memory limit are listed below.
CRD-generated pods without a Deployment/StatefulSet/DaemonSet owner are not in
this table. Values are **per container** and are suggestions, not applied.
Existing values are kept; suggestions only fill missing fields. CPU request = P95 × 1.2 rounded up to 5m (minimum
10m). Memory request = peak × 1.2 rounded up to 16Mi. Memory limit = 2× peak,
rounded up to 64Mi with a 64Mi floor, and is optional.

| Owner | Container | Requests / limit at measurement | P95 CPU | Peak memory | Suggested requests / limit |
| --- | --- | --- | --- | --- | --- |
| `kube-system/cilium` | `cilium-agent` | 0m / 0Mi / — | 313m | 9101Mi | 380m / 10928Mi / no limit |
| `monitoring-system/victoria-logs-server` | `vlsingle` | 0m / 0Mi / — | 124m | 1915Mi | 150m / 2304Mi / 3840Mi |
| `security-system/authentik-server` | `server` | 0m / 0Mi / — | 58m | 889Mi | 70m / 1072Mi / 1792Mi |
| `security-system/authentik-worker` | `worker` | 0m / 0Mi / — | 62m | 423Mi | 75m / 512Mi / 896Mi |
| `monitoring-system/victoria-logs-collector` | `vlagent` | 0m / 0Mi / — | 47m | 375Mi | 60m / 464Mi / 768Mi |
| `monitoring-system/kube-state-metrics` | `kube-state-metrics` | 0m / 0Mi / — | 17m | 286Mi | 25m / 352Mi / 576Mi |
| `storage-system/rook-ceph-rgw-ceph-objectstore-a` | `rgw` | 100m / 0Mi / 1024Mi | 14m | 259Mi | 100m / 320Mi / 1024Mi |
| `monitoring-system/victoria-traces` | `vtsingle` | 0m / 0Mi / — | 18m | 257Mi | 25m / 320Mi / 576Mi |
| `kube-system/cilium-operator` | `cilium-operator` | 0m / 0Mi / — | 13m | 234Mi | 20m / 288Mi / no limit |
| `networking-system/kgateway` | `controller` | 0m / 0Mi / — | 43m | 232Mi | 55m / 288Mi / 512Mi |
| `monitoring-system/victoria-metrics-operator` | `operator` | 0m / 0Mi / — | 198m | 160Mi | 240m / 192Mi / 320Mi |
| `networking-system/agentgateway` | `controller` | 100m / 128Mi / — | 14m | 155Mi | 100m / 128Mi / 320Mi |
| `security-system/cert-manager-cainjector` | `cert-manager-cainjector` | 0m / 0Mi / — | 4m | 148Mi | 10m / 192Mi / 320Mi |
| `kube-system/reloader` | `reloader` | 0m / 0Mi / — | 25m | 141Mi | 30m / 176Mi / 320Mi |
| `database-system/cnpg-operator` | `manager` | 0m / 0Mi / — | 17m | 113Mi | 25m / 144Mi / 256Mi |
| `security-system/external-secrets-cert-controller` | `cert-controller` | 0m / 0Mi / — | 4m | 111Mi | 10m / 144Mi / 256Mi |
| `gitops-system/system-upgrade-controller` | `manager` | 0m / 0Mi / — | 13m | 108Mi | 20m / 144Mi / 256Mi |
| `security-system/cert-manager` | `cert-manager-controller` | 0m / 0Mi / — | 2m | 102Mi | 10m / 128Mi / 256Mi |
| `kube-system/metrics-server` | `metrics-server` | 100m / 200Mi / — | 14m | 98Mi | 100m / 200Mi / 256Mi |
| `networking-system/externaldns-adguard` | `external-dns` | 16m / 0Mi / 86Mi | 2m | 83Mi | 16m / 112Mi / 86Mi |
| `storage-system/snapshot-controller` | `snapshot-controller` | 0m / 0Mi / — | 6m | 83Mi | 10m / 112Mi / 192Mi |
| `database-system/dragonfly-operator` | `manager` | 0m / 0Mi / — | 4m | 80Mi | 10m / 96Mi / 192Mi |
| `storage-system/storage-system.rbd.csi.ceph.com-ctrlplugin` | `csi-rbdplugin` | 0m / 512Mi / 1024Mi | 9m | 79Mi | 15m / 512Mi / 1024Mi |
| `kube-system/frr-k8s` | `controller` | 0m / 0Mi / — | 2m | 73Mi | 10m / 96Mi / 192Mi |
| `storage-system/storage-system.cephfs.csi.ceph.com-ctrlplugin` | `csi-cephfsplugin` | 0m / 512Mi / 1024Mi | 0m | 69Mi | 10m / 512Mi / 1024Mi |
| `kube-system/spegel` | `registry` | 0m / 128Mi / 128Mi | 20m | 65Mi | 25m / 128Mi / 128Mi |
| `kube-system/hubble-relay` | `hubble-relay` | 0m / 0Mi / — | 1m | 65Mi | 10m / 80Mi / 192Mi |
| `database-system/cnpg-barman` | `barman-cloud` | 0m / 0Mi / — | 2m | 62Mi | 10m / 80Mi / 128Mi |
| `security-system/cert-manager-webhook` | `cert-manager-webhook` | 0m / 0Mi / — | 1m | 58Mi | 10m / 80Mi / 128Mi |
| `kube-system/hubble-ui` | `backend` | 0m / 0Mi / — | 0m | 58Mi | 10m / 80Mi / 128Mi |
| `monitoring-system/webhook-relay` | `app` | 10m / 0Mi / 128Mi | 1m | 56Mi | 10m / 80Mi / 128Mi |
| `kube-system/frr-k8s-statuscleaner` | `frr-k8s-statuscleaner` | 0m / 0Mi / — | 5m | 54Mi | 10m / 80Mi / 128Mi |
| `networking-system/externaldns-adguard` | `webhook` | 0m / 0Mi / — | 1m | 52Mi | 10m / 64Mi / 128Mi |
| `kube-system/frr-k8s` | `frr` | 0m / 0Mi / — | 2m | 47Mi | 10m / 64Mi / 128Mi |
| `storage-system/kopiur-webhook` | `webhook` | 25m / 64Mi / — | 2m | 41Mi | 25m / 64Mi / 128Mi |
| `kube-system/frr-k8s` | `frr-metrics` | 0m / 0Mi / — | 5m | 36Mi | 10m / 48Mi / 128Mi |
| `monitoring-system/node-exporter` | `node-exporter` | 23m / 0Mi / 61Mi | 6m | 34Mi | 23m / 48Mi / 61Mi |
| `monitoring-system/blackbox-exporter` | `blackbox-exporter` | 0m / 0Mi / — | 3m | 34Mi | 10m / 48Mi / 128Mi |
| `monitoring-system/smartctl-exporter-0` | `main` | 0m / 0Mi / — | 2m | 32Mi | 10m / 48Mi / 64Mi |
| `kube-system/frr-k8s` | `frr-status` | 0m / 0Mi / — | 2m | 24Mi | 10m / 32Mi / 64Mi |
| `kube-system/hubble-ui` | `frontend` | 0m / 0Mi / — | 0m | 22Mi | 10m / 32Mi / 64Mi |
| `monitoring-system/vmauth-victoria-metrics-cluster` | `config-reloader` | 10m / 25Mi / — | 2m | 21Mi | 10m / 25Mi / 64Mi |
| `monitoring-system/vmalertmanager-victoria-metrics-cluster` | `config-reloader` | 10m / 25Mi / — | 1m | 21Mi | 10m / 25Mi / 64Mi |
| `monitoring-system/vmagent-victoria-metrics-cluster` | `config-reloader` | 10m / 25Mi / — | 2m | 21Mi | 10m / 25Mi / 64Mi |
| `monitoring-system/vmalert-victoria-metrics-cluster` | `config-reloader` | 10m / 25Mi / — | 1m | 18Mi | 10m / 25Mi / 64Mi |
| `kube-system/frr-k8s` | `reloader` | 0m / 0Mi / — | 0m | 7Mi | 10m / 16Mi / 64Mi |

### Notes on the suggestions

- **Cilium:** the chart example (`4Gi` limit) is below the measured working
  set. Do not use it. A ~10.9Gi request per node is the measured requirement;
  omit the memory limit unless node capacity is checked.
- **CNI and Ceph data paths:** prefer requests first and no hard memory
  limits; limit-induced OOM restarts are worse than a temporary overcommit.
- **vlagent / vtsingle:** the chart exposes `resources`; the app currently sets
  only init-container resources.
- **VM operator config reloaders:** the `vmauth`, `vmagent`, `vmalert`, and
  `vmalertmanager` config-reloaders are generated by the VictoriaMetrics
  operator. Set them through each CRD's `spec.configReloaderResources`, not
  the Helm chart values.
- **Chart-default-only apps:** `descheduler`, `silence-operator`,
  `agentgateway`, `rook-ceph`, `spegel` already receive a non-empty chart
  default; Git showing `none` does not mean the pod has no requests.

## Tooling: flate and the archived tree

`.archived/` holds retired definitions outside `kubernetes/`. Flux and flate
only read the active cluster path, so archived manifests are never rendered and
need no ignore file.

Verification: `flate test all --base main` renders the active tree without
archived manifests.
