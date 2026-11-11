# Archived definitions

Historical definitions kept for reference. Nothing in this tree is reconciled:
Flux only reads `kubernetes/`, and no Kustomization applies an archived path.

- Archived `ks.yaml` files keep `spec.path` at the canonical
  `kubernetes/apps/...` value. Archived namespace directories drop the
  `-apps`/`-system` suffix, so restore to the path named by `spec.path`
  (for example `.archived/kubernetes/media/foo` →
  `kubernetes/apps/media-apps/foo`) and re-add it to that namespace index.
- Archived definitions are not a backup. Restoring one starts from its
  manifests only; PVC data, CNPG roles/databases and kopiur snapshots may need
  manual recovery.

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
| `kubernetes/selfhosted/karakeep` | Bookmarks and read-later | Retired with the self-hosted stack |
| `kubernetes/selfhosted/netbox` | DCIM/IPAM | Retired with the self-hosted stack |
| `kubernetes/selfhosted/stirling-pdf` | PDF toolbox | Retired with the self-hosted stack |
| `kubernetes/servitor/mcp/smarthome` | MCP smart-home control tier | Retired with the smart-home stack |
| `kubernetes/smarthome/frigate` | Frigate NVR | Retired with the smart-home stack |
| `kubernetes/smarthome/frigate-vision` | Frigate alert forwarder to hermes-agent | Retired with the smart-home stack |
| `kubernetes/smarthome/home-assistant` | Home automation | Retired with the smart-home stack |
| `kubernetes/smarthome/home-assistant-sgcc` | Home Assistant with the SGCC (State Grid) bridge | Retired with the smart-home stack |
| `kubernetes/smarthome/mosquitto` | MQTT broker | Retired with the smart-home stack |
| `kubernetes/smarthome/scrypted` | Scrypted camera/NVR platform | Retired with the smart-home stack |
| `kubernetes/smarthome/smarthome-nfs` | NFS PV/PVC binding for home-automation data | Retired with the smart-home stack; NAS files remain |
| `kubernetes/smarthome/zigbee2mqtt` | Zigbee bridge | Retired with the smart-home stack |

### infrastructure

| Path | What | Why archived |
| --- | --- | --- |
| `infrastructure/talos/20-mount-hostpath.yaml` | Talos `UserVolumeConfig` for the local-cache disk | Retired from prod; the local-cache volume is unused |

### pangolin

| Path | What | Why archived |
| --- | --- | --- |
| `pangolin/apps/pangolin-newt` | Pangolin Newt connector in the cluster | Retired with the Pangolin and network/switch rework |
| `pangolin/infra/pangolin` | NAS compose stack (Pangolin, Gerbil, Gatus, doco-cd) | Retired with the same rework |
