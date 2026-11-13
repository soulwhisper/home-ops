# Application Catalog

73 application definition units across 10 namespaces, managed via Flux GitOps. Each Flux table entry links to one `ks.yaml` definition file; a unit may declare several Flux Kustomizations or include operators, shared storage, and configuration rather than a single workload. The NAS table at the end is outside Flux and links to compose stacks instead.

The [application source tree](https://github.com/soulwhisper/home-ops/tree/main/kubernetes/apps) has 10 first-level namespace directories. Together, those namespaces have 63 immediate child directories, including the `servitor-apps/mcp` grouping directory. Their 73 definition files declare 98 child Flux Kustomizations and lead to 72 HelmReleases. There are 48 OCIRepositories across the source tree: 47 application-local and one shared app-template source. These are source counts, not counts of running applications.

Definitions that are intentionally not deployed live under [`.archived/kubernetes`](https://github.com/soulwhisper/home-ops/tree/main/.archived/kubernetes); see the [archive index](https://github.com/soulwhisper/home-ops/blob/main/.archived/README.md) for why each definition is kept.

This catalog is documentation, not a deployment selector. Each namespace's linked `kustomization.yaml` is the current application selection and shared-resource entry point. Active definitions stay under `kubernetes/apps`; archived definitions live under `.archived/kubernetes`. See [Cluster Architecture](../infrastructure/kubernetes.md) and [Storage](../infrastructure/storage.md) for reconciliation and data boundaries.

[`.archived`](https://github.com/soulwhisper/home-ops/tree/main/.archived) contains historical implementations; archived definitions are reference-only and are not deployed.

## kube-system — Cluster Infrastructure (9)

[Namespace index](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/kube-system/kustomization.yaml)

| App | Purpose |
| --- | --- |
| [Cilium](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/kube-system/cilium/ks.yaml) | CNI, eBPF networking, and Hubble |
| [CoreDNS](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/kube-system/coredns/ks.yaml) | Cluster DNS |
| [Spegel](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/kube-system/spegel/ks.yaml) | P2P image distribution |
| [FRR-K8s](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/kube-system/frr-k8s/ks.yaml) | BGP peering with core switch |
| [Metrics Server](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/kube-system/metrics-server/ks.yaml) | Resource metrics for autoscaling |
| [Intel GPU Plugin](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/kube-system/intel-device-plugins/ks.yaml) | i915 GPU exposure for transcoding |
| [Reloader](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/kube-system/reloader/ks.yaml) | Restart workloads on ConfigMap/Secret changes |
| [Descheduler](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/kube-system/descheduler/ks.yaml) | Pod rebalancing |
| [Gateway API CRDs](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/kube-system/gateway-api-crds/ks.yaml) | Gateway API resource definitions |

## gitops-system — GitOps Engine (3)

[Namespace index](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/gitops-system/kustomization.yaml)

| App | Purpose |
| --- | --- |
| [Flux Operator](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/gitops-system/flux-operator/ks.yaml) | Flux Instance lifecycle management |
| [Flux Instance](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/gitops-system/flux-instance/ks.yaml) | GitOps controllers and synchronization |
| [System Upgrade Controller](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/gitops-system/system-upgrade-controller/ks.yaml) | Talos/Kubernetes upgrades with tuppr |

## security-system — Security (5)

[Namespace index](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/security-system/kustomization.yaml)

| App | Purpose |
| --- | --- |
| [External Secrets](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/security-system/external-secrets/ks.yaml) | 1Password to Kubernetes Secret synchronization |
| [1Password Connect](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/security-system/onepassword-connect/ks.yaml) | 1Password API bridge |
| [Authentik](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/security-system/authentik/ks.yaml) | SSO/OIDC provider |
| [Cert-Manager](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/security-system/cert-manager/ks.yaml) | TLS certificate automation |
| [Native Policies](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/security-system/native-policies/ks.yaml) | ValidatingAdmissionPolicies for critical namespace deletes and image-registry audit |

## networking-system — Network Services (5)

[Namespace index](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/networking-system/kustomization.yaml)

| App | Purpose |
| --- | --- |
| [Kgateway](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/networking-system/kgateway/ks.yaml) | Internal and external Envoy gateways |
| [Agent Gateway](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/networking-system/agentgateway/ks.yaml) | LLM routing and MCP gateway |
| [External DNS](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/networking-system/externaldns/ks.yaml) | AdGuardHome DNS automation |
| [Kgateway CRDs](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/networking-system/kgateway-crds/ks.yaml) | Kgateway control-plane resource definitions |
| [Forgejo Proxy](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/networking-system/forgejo-proxy/ks.yaml) | Internal HTTPS gateway for NAS-hosted Forgejo |

## storage-system — Storage (4)

[Namespace index](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/storage-system/kustomization.yaml)

| App | Purpose |
| --- | --- |
| [Rook-Ceph](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/storage-system/rook-ceph/ks.yaml) | Distributed storage: RBD, CephFS, and RGW |
| [kopiur](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/storage-system/kopiur/ks.yaml) | PVC snapshot backup and restore using Kopia and NAS S3 |
| [Snapshot Controller](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/storage-system/snapshot-controller/ks.yaml) | Volume snapshot management |
| [CSI Driver NFS](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/storage-system/csi-driver-nfs/ks.yaml) | Synology NFS mount CSI |

## database-system — Database Operators (2)

[Namespace index](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/database-system/kustomization.yaml)

| App | Purpose |
| --- | --- |
| [CloudNativePG](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/database-system/cnpg-operator/ks.yaml) | PostgreSQL operator and shared database cluster |
| [Dragonfly Operator](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/database-system/dragonfly-operator/ks.yaml) | Redis-compatible cache operator |

## monitoring-system — Observability (14)

[Namespace index](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/kustomization.yaml)

| App | Purpose |
| --- | --- |
| [VictoriaMetrics Cluster](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/victoria-metrics/ks.yaml) | Time-series metrics |
| [VictoriaLogs](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/victoria-logs/ks.yaml) | Log aggregation |
| [VictoriaTraces](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/victoria-traces/ks.yaml) | Distributed tracing |
| [OTEL Collector](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/opentelemetry-collector/ks.yaml) | Telemetry collection, processing, and export |
| [Node Exporter](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/node-exporter/ks.yaml) | Host-level metrics |
| [Kube-State-Metrics](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/kube-state-metrics/ks.yaml) | Kubernetes object state metrics |
| [Smartctl Exporter](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/smartctl-exporter/ks.yaml) | NVMe/SSD SMART monitoring |
| [VMware Exporter](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/vmware-exporter/ks.yaml) | ESXi host metrics |
| [Blackbox Exporter](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/blackbox-exporter/ks.yaml) | Endpoint probing |
| [Silence Operator](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/silence-operator/ks.yaml) | Alert silencing for maintenance |
| [Prometheus CRDs](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/prometheus-crds/ks.yaml) | Prometheus operator resource definitions |
| [Robusta](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/robusta/ks.yaml) | Alert enrichment, Holmes analysis, and scheduled health checks |
| [KRR](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/krr/ks.yaml) | Scheduled Kubernetes resource recommendations |
| [Webhook Relay](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/webhook-relay/ks.yaml) | Inbound webhook collection and Feishu fan-out |

## smarthome-apps — Smart Home (7)

[Namespace index](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/smarthome-apps/kustomization.yaml)

| App | Purpose |
| --- | --- |
| [Home Assistant](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/smarthome-apps/home-assistant/ks.yaml) | Home automation hub |
| [Home Assistant SGCC](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/smarthome-apps/home-assistant-sgcc/ks.yaml) | State Grid power integration |
| [Mosquitto](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/smarthome-apps/mosquitto/ks.yaml) | MQTT broker |
| [Zigbee2MQTT](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/smarthome-apps/zigbee2mqtt/ks.yaml) | Zigbee to MQTT bridge |
| [Frigate](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/smarthome-apps/frigate/ks.yaml) | AI NVR with Intel GPU acceleration |
| [Scrypted](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/smarthome-apps/scrypted/ks.yaml) | Video streaming with iGPU acceleration |
| [Smarthome-NFS](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/smarthome-apps/smarthome-nfs/ks.yaml) | Shared smart-home NFS storage |

## selfhosted-apps — Self-Hosted Services (8)

[Namespace index](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/selfhosted-apps/kustomization.yaml)

| App | Purpose |
| --- | --- |
| [TrendRadar](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/selfhosted-apps/trendradar/ks.yaml) | Scheduled AI news digest |
| [SearXNG](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/selfhosted-apps/searxng/ks.yaml) | Internal metasearch backend for Firecrawl |
| [Homepage](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/selfhosted-apps/homepage/ks.yaml) | Application dashboard |
| [Firecrawl](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/selfhosted-apps/firecrawl/ks.yaml) | Web scraping pipeline |
| [Bambuddy](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/selfhosted-apps/bambuddy/ks.yaml) | Bambu Lab 3D printer monitor |
| [Manyfold](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/selfhosted-apps/manyfold/ks.yaml) | 3D model library and digital asset manager |
| [Obico ML](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/selfhosted-apps/obico-ml/ks.yaml) | Internal CPU inference API for Obico |
| [Selfhosted-NFS](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/selfhosted-apps/selfhosted-nfs/ks.yaml) | Shared self-hosted NFS claims |

Manyfold mounts its NFS share at `/libraries/main`; create the initial library with that path after first login.

## NAS — Compose services

Managed by [doco-cd](https://github.com/soulwhisper/home-ops/tree/main/infrastructure/synology) from git, not by Flux: these definitions live outside `kubernetes/` and are not part of the Flux definition units above. Only application-facing stacks are listed — the directory also holds infrastructure stacks (`versitygw`, `forgejo`, `zotregistry`, `scrutiny`, `talos`).

| App | Purpose |
| --- | --- |
| [Hindsight](https://github.com/soulwhisper/home-ops/blob/main/infrastructure/synology/hindsight/docker-compose.yml) | AI memory service (moved out of the cluster; data lives on the NAS) |

## servitor-apps — AI Infrastructure (16)

[Namespace index](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/kustomization.yaml)

Five direct application definitions and 11 nested MCP definitions. ToolHive configures six VirtualMCP groups: `search`, `cluster`, `github-ro`, `agent`, `browser`, and `github-pr`.

| App | Purpose |
| --- | --- |
| [Covel](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/covel/ks.yaml) | Agentic AI role-playing framework |
| [DiceFrame](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/diceframe/ks.yaml) | Self-hosted AI tabletop RPG engine |
| [Open WebUI](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/open-webui/ks.yaml) | Human chat portal with search-group MCP |
| [ToolHive](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/toolhive/ks.yaml) | MCP operator, CRDs, and VirtualMCP configuration |
| [Playwright](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/playwright/ks.yaml) | Standalone Chromium browser runtime for MCP automation |

### MCP Definitions (11)

The [MCP index](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/kustomization.yaml) selects 11 definition files declaring 12 child Flux Kustomizations: GitHub has two identities and each other definition has one. These are not 12 individual backend server instances.

| Definition | Purpose |
| --- | --- |
| [Context](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/context/ks.yaml) | Context7 documentation retrieval |
| [Firecrawl](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/firecrawl/ks.yaml) | Web scraping tools |
| [FluxCD](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/fluxcd/ks.yaml) | Read-only Flux inspection |
| [Forgejo](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/forgejo/ks.yaml) | Operator ticket tools |
| [GitHub](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/github/ks.yaml) | Read-only search and separate branch/commit/pull-request tools |
| [Kubernetes](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/kubernetes/ks.yaml) | Kubernetes inspection tools |
| [Playwright MCP](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/playwright/ks.yaml) | Browser automation tools using the standalone browser runtime |
| [TrendRadar](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/trendradar/ks.yaml) | News retrieval tools |
| [VictoriaLogs](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/victoria-logs/ks.yaml) | Log query tools |
| [VictoriaMetrics](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/victoria-metrics/ks.yaml) | Metrics query tools |
| [VictoriaTraces](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/victoria-traces/ks.yaml) | Trace query tools |
