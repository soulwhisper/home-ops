## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/2699_fe0f/512.gif" alt="⚙" style="width: 20px; height: 20px; vertical-align: middle;"> Hardware

| Device | Count | CPU | RAM | OS Disk | Data Disk | NIC | OS | Role |
|--------|:-----:|-----|:---:|---------|-----------|-----|:--:|------|
| Miniforum MS-01 | 3 | i9-13900H | 96GB | 512GB SSD | 2TB NVMe (P41, OSD) | Intel X710 2×10G SFP+ | Talos | K8s control-plane + worker |
| N305 IPC | 1 | N305 | 24GB | 1TB SSD | — | 2.5G RJ45 | ESXi 8 | OpenWrt edge router |
| H3C S6520-24S-SI | 1 | — | — | — | — | 24×10G SFP+ | Comware 7 | L3 core switch |
| SANTAK TG-Box 850 | 1 | — | — | — | — | USB | — | UPS (NUT) |
| Synology DS923+ | 1 | Ryzen R1600 | 16GB | — | 4×HDD (SHR) + NVMe cache | 2×1G RJ45 (LACP) | DSM 7 | NAS (NFS/S3/Docker) |

### Node Details

Each MS-01 node runs Talos Linux with:
- **LACP bond** (802.3ad, MTU 9000) on Intel X710 10G NICs
- **NVMe OSD**: SK Hynix P41 2TB, 2 OSDs per device for Rook-Ceph
- **Additional NVMe slots**: WD Black SN850X 8TB, Kioxia RC20 2TB (available for future expansion)
- **GPU**: Intel Iris Xe (i915) — exposed via Intel GPU Plugin for media transcoding
- **Boot**: sd-boot, Talos factory image with custom schematic (Kata Containers, i915, NUT, Intel microcode)


### Watch Points

- **MS-01 system SSD write stalls (observed 2026-09-13)**: etcd on exarch-02 logged `slow fdatasync` up to 15.4s (5 events within ~1.5h; exarch-01/03 had 1–2 isolated events). One episode stalled raft agreement long enough to trip cluster-wide leader-election loss — 9 controllers (incl. kube-controller-manager, kube-scheduler) exited and recovered within seconds. etcd WAL lives on the EPHEMERAL partition (`/var/lib/etcd`, `nvme1n1p4`). If stalls recur, check drive health via smartctl-exporter and consider I/O isolation for etcd. Note: Talos `diskSelector` targets a 256GB-class drive (SQF-C3AV1-256GDEDM) while the table above says 512GB — reconcile on next hardware audit.

### Future Plans

- **UPS (NUT) monitoring**: the SANTAK TG-Box 850 is attached and Talos runs the NUT extension, but no exporter/alerting exists yet — power events are currently invisible. Not yet migrated to a real implementation; candidate: NUT exporter on the NAS or a small in-cluster daemon scraping the UPS, plus a vmalert rule for on-battery / low-charge.
### Network Topology

```
                         ┌──────────┐
                         │ Internet │
                         └────┬─────┘
                              │
                         ┌────▼─────┐
                         │ OpenWrt  │
                         │ N305 IPC │
                         │NTP/DNS/  │
                         │VPN/TProxy│
                         └──┬───┬───┘
                            │   │
              ┌─────────────▼┐ ┌▼─────────────┐
              │  ESXi Host   │ │ 10G Transit  │
              │    (VMs)     │ │  VLAN 1000   │
              └──────────────┘ └──────┬───────┘
                                      │
                         ┌────────────▼────────────┐
                         │  H3C S6520-24S-SI       │
                         │  Core Switch (AS 65000) │
                         │  BGP + BFD + LACP       │
                         └──┬──────┬──────┬──────┬─┘
                            │      │      │      │
              ┌─────────────▼┐ ┌───▼───┐ ┌──▼──┐ ┌▼──────────┐
              │  exarch-01   │ │exarch │ │exarch│ │ Synology  │
              │    .101      │ │ -02   │ │ -03  │ │ NAS .100  │
              │ 2×10G LACP   │ │ .102  │ │ .103 │ │2×1G LACP  │
              └──────────────┘ └───────┘ └──────┘ └───────────┘
              └────────── VLAN 100 (10.10.0.0/24) ──────────┘
```

