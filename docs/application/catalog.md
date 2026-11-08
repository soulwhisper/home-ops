# Application Catalog

96 application definition units across 12 namespaces, managed via Flux GitOps. Each table entry links to one `ks.yaml` definition file; a unit may declare several Flux Kustomizations or include operators, shared storage, and configuration rather than a single workload.

The [application source tree](https://github.com/soulwhisper/home-ops/tree/main/kubernetes/apps) has 12 first-level namespace directories. Together, those namespaces have 83 immediate child directories, including the `servitor-apps/mcp` grouping directory. Their 96 definition files declare 129 child Flux Kustomizations and lead to 93 HelmReleases. There are 53 OCIRepositories across the source tree: 52 application-local and one shared app-template source. These are source counts, not counts of running applications.

This catalog is documentation, not a deployment selector. Each namespace's linked `kustomization.yaml` selects application directories and shared resources. Every definition has a sibling application-local `kustomization.yaml` that sets its namespace and includes only `ks.yaml`; it can be referenced without the namespace index injecting the child Flux Kustomizations' namespace. Definitions remain in place, and the root Flux defaults still apply. See [Application Entrypoints](../infrastructure/kubernetes.md#application-entrypoints) and [Storage](../infrastructure/storage.md) for build and data boundaries.

[`.archived`](https://github.com/soulwhisper/home-ops/tree/main/.archived) contains historical implementations with old paths; it does not guarantee that an application can be redeployed or its data restored.

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
| [Kyverno](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/security-system/kyverno/ks.yaml) | Policy engine |

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

## database-system — Database Operators (3)

[Namespace index](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/database-system/kustomization.yaml)

| App | Purpose |
| --- | --- |
| [CloudNativePG](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/database-system/cnpg-operator/ks.yaml) | PostgreSQL operator and shared database cluster |
| [Dragonfly Operator](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/database-system/dragonfly-operator/ks.yaml) | Redis-compatible cache operator |
| [ClickHouse Operator](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/database-system/clickhouse-operator/ks.yaml) | Analytical database operator and cluster for Langfuse |

## monitoring-system — Observability (17)

[Namespace index](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/kustomization.yaml)

| App | Purpose |
| --- | --- |
| [VictoriaMetrics Cluster](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/victoria-metrics/ks.yaml) | Time-series metrics |
| [VictoriaLogs](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/victoria-logs/ks.yaml) | Log aggregation |
| [VictoriaTraces](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/victoria-traces/ks.yaml) | Distributed tracing |
| [Grafana](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/grafana/ks.yaml) | Dashboards and visualization |
| [OTEL Collector](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/opentelemetry-collector/ks.yaml) | Telemetry collection, processing, and export |
| [Node Exporter](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/node-exporter/ks.yaml) | Host-level metrics |
| [Kube-State-Metrics](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/kube-state-metrics/ks.yaml) | Kubernetes object state metrics |
| [Smartctl Exporter](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/smartctl-exporter/ks.yaml) | NVMe/SSD SMART monitoring |
| [VMware Exporter](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/vmware-exporter/ks.yaml) | ESXi host metrics |
| [Blackbox Exporter](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/blackbox-exporter/ks.yaml) | Endpoint probing |
| [Silence Operator](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/silence-operator/ks.yaml) | Alert silencing for maintenance |
| [Headlamp](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/headlamp/ks.yaml) | Kubernetes web UI |
| [Langfuse](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/langfuse/ks.yaml) | LLM observability |
| [Prometheus CRDs](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/prometheus-crds/ks.yaml) | Prometheus operator resource definitions |
| [Robusta](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/robusta/ks.yaml) | Alert enrichment, Holmes analysis, and scheduled health checks |
| [KRR](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/krr/ks.yaml) | Scheduled Kubernetes resource recommendations |
| [Webhook Relay](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/monitoring-system/webhook-relay/ks.yaml) | Inbound webhook collection and Feishu fan-out |

## smarthome-apps — Smart Home (8)

[Namespace index](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/smarthome-apps/kustomization.yaml)

| App | Purpose |
| --- | --- |
| [Home Assistant](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/smarthome-apps/home-assistant/ks.yaml) | Home automation hub |
| [Home Assistant SGCC](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/smarthome-apps/home-assistant-sgcc/ks.yaml) | State Grid power integration |
| [Mosquitto](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/smarthome-apps/mosquitto/ks.yaml) | MQTT broker |
| [Zigbee2MQTT](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/smarthome-apps/zigbee2mqtt/ks.yaml) | Zigbee to MQTT bridge |
| [Frigate](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/smarthome-apps/frigate/ks.yaml) | AI NVR with Coral TPU |
| [Frigate Vision](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/smarthome-apps/frigate-vision/ks.yaml) | Event-driven vision analysis and home alerts |
| [Scrypted](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/smarthome-apps/scrypted/ks.yaml) | Video streaming with iGPU acceleration |
| [Smarthome-NFS](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/smarthome-apps/smarthome-nfs/ks.yaml) | Shared smart-home NFS storage |

## media-apps — Media (9)

[Namespace index](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/media-apps/kustomization.yaml)

| App | Purpose |
| --- | --- |
| [Jellyfin](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/media-apps/jellyfin/ks.yaml) | Media streaming with iGPU transcoding |
| [Immich](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/media-apps/immich/ks.yaml) | Photo management and machine learning |
| [Navidrome](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/media-apps/navidrome/ks.yaml) | Subsonic-compatible music streaming |
| [Kavita](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/media-apps/kavita/ks.yaml) | Comic/eBook reader |
| [qBittorrent](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/media-apps/qbittorrent/ks.yaml) | Torrent client with QUI |
| [qBittorrentUI](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/media-apps/qbittorrent-ui/ks.yaml) | Alternate torrent web UI |
| [MeTube](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/media-apps/metube/ks.yaml) | Video downloader using yt-dlp |
| [MoviePilot](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/media-apps/moviepilot/ks.yaml) | Media automation |
| [Media-NFS](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/media-apps/media-nfs/ks.yaml) | Shared media NFS storage |

## selfhosted-apps — Self-Hosted Services (10)

[Namespace index](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/selfhosted-apps/kustomization.yaml)

| App | Purpose |
| --- | --- |
| [Stirling-PDF](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/selfhosted-apps/stirling-pdf/ks.yaml) | PDF toolkit |
| [TrendRadar](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/selfhosted-apps/trendradar/ks.yaml) | Scheduled AI news digest |
| [NetBox](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/selfhosted-apps/netbox/ks.yaml) | DCIM/IPAM |
| [SearXNG](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/selfhosted-apps/searxng/ks.yaml) | Privacy-focused metasearch |
| [Homepage](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/selfhosted-apps/homepage/ks.yaml) | Application dashboard |
| [Karakeep](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/selfhosted-apps/karakeep/ks.yaml) | Bookmark manager with browser capture and search |
| [Hindsight](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/selfhosted-apps/hindsight/ks.yaml) | AI memory service |
| [Firecrawl](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/selfhosted-apps/firecrawl/ks.yaml) | Web scraping pipeline |
| [Bambuddy](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/selfhosted-apps/bambuddy/ks.yaml) | Bambu Lab 3D printer monitor |
| [Dispatcharr](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/selfhosted-apps/dispatcharr/ks.yaml) | IPTV dispatch with iGPU transcoding |

## servitor-apps — AI Infrastructure (20)

[Namespace index](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/kustomization.yaml)

Six direct application definitions and 14 nested MCP definitions. ToolHive configures six VirtualMCP groups: `search`, `cluster`, `persona`, `agent`, `browser`, and `github-pr`.

| App | Purpose |
| --- | --- |
| [Hermes Agent](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/hermes-agent/ks.yaml) | AI agent suite with Feishu and scheduled automation |
| [DSH Web](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/dsh-web/ks.yaml) | Agent workbench |
| [DSH Tavern](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/dsh-tavern/ks.yaml) | Roleplay chat portal |
| [Open WebUI](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/open-webui/ks.yaml) | Human chat portal with search-group MCP |
| [ToolHive](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/toolhive/ks.yaml) | MCP operator, CRDs, and VirtualMCP configuration |
| [Playwright](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/playwright/ks.yaml) | Standalone Chromium browser runtime for MCP automation |

### MCP Definitions (14)

The [MCP index](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/kustomization.yaml) selects 14 definition files declaring 19 child Flux Kustomizations: GitHub has two identities, Hindsight has five, and each other definition has one. These are not 14 individual backend server instances.

| Definition | Purpose |
| --- | --- |
| [Context](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/context/ks.yaml) | Context7 documentation retrieval |
| [Firecrawl](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/firecrawl/ks.yaml) | Web scraping tools |
| [FluxCD](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/fluxcd/ks.yaml) | Read-only Flux inspection |
| [Forgejo](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/forgejo/ks.yaml) | Operator ticket tools |
| [GitHub](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/github/ks.yaml) | Read-only search and separate branch/commit/pull-request tools |
| [Grafana](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/grafana/ks.yaml) | Grafana observability tools |
| [Hindsight](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/hindsight/ks.yaml) | Memory proxies for home, persona, work, others, and ops banks |
| [Home Assistant](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/home-assistant/ks.yaml) | Home automation tools |
| [Kubernetes](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/kubernetes/ks.yaml) | Kubernetes inspection tools |
| [Playwright MCP](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/playwright/ks.yaml) | Browser automation tools using the standalone browser runtime |
| [TrendRadar](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/trendradar/ks.yaml) | News retrieval tools |
| [VictoriaLogs](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/victoria-logs/ks.yaml) | Log query tools |
| [VictoriaMetrics](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/victoria-metrics/ks.yaml) | Metrics query tools |
| [VictoriaTraces](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/servitor-apps/mcp/victoria-traces/ks.yaml) | Trace query tools |

## gaming-apps — Gaming (3)

[Namespace index](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/gaming-apps/kustomization.yaml)

| App | Purpose |
| --- | --- |
| [Crafty Controller](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/gaming-apps/crafty-controller/ks.yaml) | Minecraft server control panel |
| [FoundryVTT](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/gaming-apps/foundryvtt/ks.yaml) | Virtual tabletop RPG |
| [Gaming-NFS](https://github.com/soulwhisper/home-ops/blob/main/kubernetes/apps/gaming-apps/gaming-nfs/ks.yaml) | Shared game NFS storage |
