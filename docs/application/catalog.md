# Application Catalog

80 applications across 13 namespaces, managed via Flux GitOps.

## kube-system — Cluster Infrastructure (11)

| App              | Purpose                                            |
| ---------------- | -------------------------------------------------- |
| Cilium           | CNI, eBPF, Hubble (netkit, BBR, BIGTCP, Maglev LB) |
| CoreDNS          | Cluster DNS                                        |
| Spegel           | P2P image distribution                             |
| FRR-K8s          | BGP peering with core switch (BFD)                 |
| Metrics Server   | Resource metrics for HPA/VPA                       |
| Intel GPU Plugin | i915 GPU exposure for transcoding                  |
| Reloader         | Auto-restart on ConfigMap/Secret change            |
| Descheduler      | Pod rebalancing                                    |
| K8tz             | Timezone injection (Asia/Shanghai)                 |
| Runtime Classes  | Kata Containers VM isolation                       |
| Gateway API CRDs | CRDs for kgateway                                  |

## gitops-system — GitOps Engine (3)

| App                       | Purpose                            |
| ------------------------- | ---------------------------------- |
| Flux Operator             | Flux Instance lifecycle management |
| Flux Instance             | GitOps controller                  |
| System Upgrade Controller | Talos/K8s version upgrades (tuppr) |

## security-system — Security (4)

| App               | Purpose                     |
| ----------------- | --------------------------- |
| External Secrets  | 1Password → K8s Secret sync |
| 1Password Connect | 1Password API bridge        |
| Authentik         | SSO/OIDC provider           |
| Cert-Manager      | TLS certificate automation  |

## networking-system — Network Services (3)

| App           | Purpose                                           |
| ------------- | ------------------------------------------------- |
| Kgateway      | Envoy Gateway API (internal + external)           |
| Agent Gateway | AI LLM routing (complex/omni/micro) + MCP gateway |
| External DNS  | AdGuardHome DNS automation                        |

## storage-system — Storage (5)

| App                 | Purpose                                  |
| ------------------- | ---------------------------------------- |
| Rook-Ceph           | Distributed storage (RBD + CephFS + RGW) |
| kopiur              | PVC backup (Kopia → Ceph S3)             |
| Snapshot Controller | Volume snapshot management               |
| OpenEBS LocalPV     | Node-local persistent storage            |
| CSI Driver NFS      | Synology NFS mount CSI                   |

## database-system — Database Operators (3)

| App                 | Purpose                                 |
| ------------------- | --------------------------------------- |
| CloudNativePG       | PostgreSQL operator (PGVector, Barman)  |
| Dragonfly Operator  | Redis-compatible cache operator         |
| ClickHouse Operator | Analytical database operator (Langfuse) |

## monitoring-system — Observability (14)

| App                     | Purpose                                                |
| ----------------------- | ------------------------------------------------------ |
| VictoriaMetrics Cluster | Time-series metrics (30d retention)                    |
| VictoriaLogs            | Log aggregation                                        |
| VictoriaTraces          | Distributed tracing                                    |
| Grafana                 | Dashboards (vendir-synced)                             |
| OTEL Collector          | Telemetry pipeline (credential redaction, dual export) |
| Node Exporter           | Host-level metrics                                     |
| Kube-State-Metrics      | K8s object state metrics                               |
| Smartctl Exporter       | NVMe/SSD SMART monitoring                              |
| Blackbox Exporter       | Endpoint probing (HTTP/TCP/ICMP)                       |
| Heartbeats              | CronJob heartbeat monitoring                           |
| Silence Operator        | Alert silencing for maintenance                        |
| Headlamp                | K8s Web UI (RBAC + OIDC)                               |
| Langfuse                | LLM observability (ClickHouse + CNPG + S3)             |
| Prometheus CRDs         | Operator CRDs                                          |

## smarthome-apps — Smart Home (8)

| App                 | Purpose                               |
| ------------------- | ------------------------------------- |
| Home Assistant      | Home automation hub (OIDC, HACS)      |
| Home Assistant SGCC | State Grid power integration          |
| Mosquitto           | MQTT broker (LoadBalancer IP)         |
| Zigbee2MQTT         | Zigbee → MQTT bridge                  |
| Frigate             | AI NVR (Coral TPU)                    |
| Frigate Vision      | Event → omni VLM → HA + hermes alerts |
| Scrypted            | Video streaming (iGPU QSV)            |
| Smarthome-NFS       | Shared NFS storage (500Gi)            |

## media-apps — Media (9)

| App           | Purpose                                    |
| ------------- | ------------------------------------------ |
| Jellyfin      | Media streaming (iGPU transcode)           |
| Immich        | Photo management (CNPG + ML)               |
| Navidrome     | Music streaming (Subsonic)                 |
| Kavita        | Comic/eBook reader (OIDC)                  |
| qBittorrent   | Torrent client (LoadBalancer IP + QUI)     |
| qBittorrentUI | Alternate torrent web UI                   |
| MeTube        | Video downloader (yt-dlp)                  |
| MoviePilot    | Media automation (CNPG + Dragonfly + iGPU) |
| Media-NFS     | Shared media storage                       |

## selfhosted-apps — Self-Hosted Services (14)

| App           | Purpose                                                        |
| ------------- | -------------------------------------------------------------- |
| Stirling-PDF  | PDF toolkit (50+ operations)                                   |
| TrendRadar    | AI news digest (RSS watch list, CronJob, omni lane)            |
| NetBox        | DCIM/IPAM (9 plugins, CNPG + Dragonfly)                        |
| SearXNG       | Privacy meta-search (Dragonfly, bot detection)                 |
| Homepage      | App dashboard                                                  |
| Karakeep      | Bookmark manager (Kata VM, Chrome + Meilisearch, omni lane)    |
| Hindsight     | AI memory (slim image; LLM + embeddings + rerank on MacStudio) |
| Open-Notebook | AI research notebook (SurrealDB)                               |
| Firecrawl     | Web scraping pipeline (Kata, 3 containers, MCP)                |
| SillyTavern   | AI character chat (AgentGateway)                               |
| Bambuddy      | 3D printer monitor (Bambu Lab)                                 |
| Dispatcharr   | IPTV dispatch (iGPU transcode)                                 |

## servitor-apps — AI Infrastructure (4 + 11 MCP servers)

| App          | Purpose                                                                                        |
| ------------ | ---------------------------------------------------------------------------------------------- |
| Hermes Agent | AI agent suite (Kata VM, Feishu, cron/automation)                                              |
| ToolHive     | MCP gateway (3 VirtualMCP tiers, semantic search)                                              |
| Onyx         | Enterprise chat + RAG (CNPG + Dragonfly + Ceph S3 + OpenSearch)                                |
| MCP Servers  | kubernetes/HA/hindsight/honcho/github/firecrawl/grafana/flux/vlogs/obsidian/forgejo/trendradar |

## gaming-apps — Gaming (3)

| App               | Purpose                               |
| ----------------- | ------------------------------------- |
| Crafty Controller | Minecraft server control panel        |
| FoundryVTT        | Virtual tabletop RPG (ExternalSecret) |
| Gaming-NFS        | Shared game storage                   |

## worker-apps — CI/CD (1)

| App        | Purpose           |
| ---------- | ----------------- |
| Woodpecker | Self-hosted CI/CD |
