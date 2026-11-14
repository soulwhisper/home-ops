# Archived definitions

Historical definitions kept for reference. Nothing in this tree is reconciled:
Flux only reads `kubernetes/`, and no Kustomization applies an archived path.

- Archived `ks.yaml` files keep `spec.path` at the canonical
  `kubernetes/apps/...` value. Archived namespace directories drop the
  `-apps`/`-system` suffix, so restore to the path named by `spec.path`
  (for example `.archived/kubernetes/media/foo` →
  `kubernetes/apps/media-apps/foo`) and re-add it to that namespace index.
- Renovate path globs for the retired namespaces (`kubernetes/apps/{gaming,media}-apps/**`)
  were dropped from `.renovate/autoMerge.json5`, and the repository-root
  `renovate.json5` ignores this tree via `ignorePaths: [".archived/**"]`. Restoring an app from one of those namespaces also
  means putting its glob back, otherwise its minor updates stop auto-merging.
  Per-app Renovate entries that were removed are listed in that app's own
  `README.md` (`media/immich`, `servitor/hermes-agent`).
- Archived definitions are not a backup. Restoring one starts from its
  manifests only; PVC data, CNPG roles/databases and kopiur snapshots may need
  manual recovery.
- Homepage integration for archived apps is not retained. The `starrs`
  1Password item supplied the Jellyfin/Immich widget credentials; those
  template keys, the item dependency, and the archived app icons were removed.

## Index

### kubernetes

| Path | What | Why archived |
| --- | --- | --- |
| `kubernetes/networking/cloudflare-tunnel` | Cloudflare Tunnel ingress for public HTTPRoutes | Retired by the public-exposure decision; access is VPN-first |
| `kubernetes/networking/externaldns-cloudflare` | external-dns for Cloudflare public records | Retired with the same public-exposure decision |
| `kubernetes/servitor/dsh-tavern` | DSH Tavern roleplay portal | DSH appliances were retired |
| `kubernetes/servitor/dsh-web` | DSH Web agent workbench (NAS deployment) | DSH appliances were retired |
| `kubernetes/servitor/sillytavern` | SillyTavern chat UI | Replaced by dsh-tavern |
| `kubernetes/storage/openebs-localpv` | OpenEBS local hostPath provisioner | Retired with the Talos prod bring-up; Ceph backs the active storage classes |
| `kubernetes/database/clickhouse-operator` | ClickHouse operator, cluster and keeper | Langfuse was the only consumer; archived with it |
| `kubernetes/monitoring/langfuse` | LLM trace backend | Dropped almost every span after the OTel attribute change and saw no UI traffic, so it was retired together with ClickHouse |
| `kubernetes/monitoring/headlamp` | Kubernetes web UI with the Flux plugin and Authentik OIDC. Its blueprint is `.archived/kubernetes/monitoring/headlamp/blueprints/oidc/headlamp.yaml`; the Talos apiserver OIDC stanza is in `.archived/kubernetes/monitoring/headlamp/config/talos-oidc.yaml`. Restore the blueprint to `kubernetes/apps/security-system/authentik/app/blueprints/oidc/headlamp.yaml`, re-add the secret to the Authentik `blueprints.secrets`, and merge the Talos stanza into `infrastructure/talos/prod/10-general.yaml` | No gateway traffic observed; CLI and desktop clients cover the same view |
| `kubernetes/monitoring/grafana` | Grafana Operator, instance, datasources, vendir config, dashboard CRs/generators, and OIDC blueprint. Only the vendir-sourced `_sources/` cache and the Homepage icon were deleted; configuration notes and restore steps are in the folder `README.md`. The MCP server has its own row below | Native Victoria UIs and vmalert cover visualization and alerting; Grafana duplicated them and the MCP surface duplicated the Victoria query servers |
| `kubernetes/gaming/crafty-controller` | Minecraft server manager | Retired with the gaming stack |
| `kubernetes/gaming/foundryvtt` | Foundry virtual tabletop | Retired with the gaming stack |
| `kubernetes/gaming/gaming-nfs` | NFS PV/PVC binding for gaming data | Retired with the gaming stack; NAS files remain |
| `kubernetes/media/immich` | Photo and video library | Retired with the media stack |
| `kubernetes/media/jellyfin` | Media server | Retired with the media stack |
| `kubernetes/media/kavita` | Manga, comic and ebook server | Retired with the media stack |
| `kubernetes/media/media-nfs` | NFS PV/PVC binding for the media library | Retired with the media stack; NAS files remain |
| `kubernetes/media/metube` | Video downloader | Retired with the media stack |
| `kubernetes/media/moviepilot` | Media automation | Retired with the media stack |
| `kubernetes/media/navidrome` | Music streaming server | Retired with the media stack |
| `kubernetes/media/qbittorrent` | Torrent client | Retired with the media stack |
| `kubernetes/media/qbittorrent-ui` | Web UI for qBittorrent | Retired with the media stack |
| `kubernetes/security/authentik/blueprints` | Forward-auth and OIDC blueprints for archived applications | Kept so archived definitions mirror the active layout; only active-app blueprints are installed |
| `kubernetes/security/kyverno` | Policy engine: six audit policies and the namespace-delete guard | The namespace guard and image-registry audit are now `protect-critical-namespaces` and `audit-image-registries` in the `native-policies` Kustomization; the remaining audit rules were dropped because their reports were not consumed by alerts or dashboards |
| `kubernetes/selfhosted/dispatcharr` | IPTV proxy and DVR | Retired with the self-hosted stack |
| `kubernetes/selfhosted/hindsight` | AI memory service (app, egress CNP, EXTERNALSECRET, restart cronjob) | Moved to the NAS (`infrastructure/synology/hindsight`) so the one non-rebuildable dataset lives on the UPS-backed host. Consumers call `nas.homelab.internal:8888` directly. Restore steps — including the CNPG role and `Database` CR that were removed with it — are in this folder's `README.md`; its Authentik blueprint is at `.archived/kubernetes/security/authentik/blueprints/forward/hindsight.yaml`, and restoring it needs **both** auth changes — re-add the file to the `authentik-blueprints-forward` list and its provider to `outpost-proxy.yaml` — or the app comes back unserved by the outpost |
| `kubernetes/selfhosted/karakeep` | Bookmarks and read-later | Retired with the self-hosted stack |
| `kubernetes/selfhosted/netbox` | DCIM/IPAM | Retired with the self-hosted stack |
| `kubernetes/selfhosted/stirling-pdf` | PDF toolbox | Retired with the self-hosted stack |
| `kubernetes/servitor/hermes-agent` | In-cluster AI agent (gateway + dashboard, Feishu websocket, MCP tier consumers) | Archived 2026-11: the homelab runs one Hermes, the native instance on `nix-ops`. Its Authentik blueprint is archived alongside, and the kopiur-backed `/opt/data` PVC is pruned unless kept — restore steps and the data warning are in the folder `README.md` |
| `kubernetes/servitor/mcp/grafana` | Grafana MCP server and its service-account token sync | Retired with Grafana; Victoria query MCP servers cover the remaining read-only surface |
| `kubernetes/servitor/mcp/hindsight` | ToolHive MCP proxies for the hindsight persona and ops banks (base + both overlays) | Hindsight speaks MCP natively, so the proxy duplicated it; with the service on the NAS a consumer points at `nas.homelab.internal:8888/mcp/<bank>`. Archived with its `persona` MCP tier (group, vmcp, route, key) — see the hindsight app's archived `README.md` for the full restore list |
| `kubernetes/servitor/mcp/smarthome` | MCP smart-home control tier | Not restored with the core smart-home applications |
| `kubernetes/smarthome/frigate-vision` | Frigate alert forwarder to hermes-agent | The native Hermes instance has no GitOps-managed Frigate webhook route; the other core smart-home definitions were restored |
| `kubernetes/smarthome/zigbee2mqtt` | Zigbee2MQTT app manifests; its Authentik forward-auth blueprint is at `.archived/kubernetes/security/authentik/blueprints/forward/z2m.yaml` | Zigbee devices are managed by the Aqara Hub M3; the SLZB-06P10 coordinator is offline. Restore the folder to `kubernetes/apps/smarthome-apps/zigbee2mqtt`, copy the archived blueprint to `kubernetes/apps/security-system/authentik/app/blueprints/forward/z2m.yaml`, re-add `./zigbee2mqtt/ks.yaml` to the namespace index, re-add `./blueprints/forward/z2m.yaml` to the `authentik-blueprints-forward` list, and restore `z2m-proxy-provider` in `outpost-proxy.yaml`. The Homepage icon and generator entry were removed; restore them or remove the retained `gethomepage.dev/*` annotations from the HelmRelease. The `zigbee2mqtt` PVC and 1Password item remain |

### infrastructure

| Path | What | Why archived |
| --- | --- | --- |
| `infrastructure/talos/20-mount-hostpath.yaml` | Talos `UserVolumeConfig` for the local-cache disk | Retired from prod; the local-cache volume is unused |

### github

| Path | What | Why archived |
| --- | --- | --- |
| `.github/workflows/vendir.yaml` | Vendir dashboard sync workflow | Grafana dashboards were retired; kept as reference if vendir sync returns |

### pangolin

| Path | What | Why archived |
| --- | --- | --- |
| `pangolin/apps/pangolin-newt` | Pangolin Newt connector in the cluster | Retired with the Pangolin and network/switch rework |
| `pangolin/infra/pangolin` | NAS compose stack (Pangolin, Gerbil, Gatus, doco-cd) | Retired with the same rework |
