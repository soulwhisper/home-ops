# Synology Homepage

Standalone replacement or fallback for the [Kubernetes Homepage](../../../kubernetes/apps/selfhosted-apps/homepage).
It keeps the cluster dashboard's Status sidebar alongside one Service group
for NAS apps. The cluster page and its route are unchanged. This page needs
neither Flux nor Authentik.

- NAS, OpenWrt, UniFi, and Forgejo retain their status widgets. Forgejo's
  widget uses the NAS loopback API, not the cluster's Forgejo proxy.
- ESXi shows direct HTTPS reachability. ESXi metrics and the Talos utilization
  widget are not available without the in-cluster monitoring stack.

Service icons are served locally. Bambuddy and Hindsight reuse the Bambu Lab
and MetaBrainz icons from the former cluster cards. The other icons use
[Material Design Icons](https://pictogrammers.com/library/mdi/icon/cards-outline/),
[Dashboard Icons](https://github.com/homarr-labs/dashboard-icons/blob/main/svg/scrutiny-light.svg),
and the [MeshCentral favicon](https://github.com/Ylianst/MeshCentral/blob/master/public/favicon-32x32.png).

## NAS setup

Create `/volume3/docker/homepage/config` on Synology before deployment. It must
be writable by `1000:1000` for logs and generated config. The dashboard YAML,
CSS, and icons are read-only binds from the Doco CD checkout.

**Before merging, replace all seven encrypted example values** in
[`homepage.sops.env`](homepage.sops.env) using `sops edit` with the Doco CD age
identity. Doco CD decrypts the file before Compose starts Homepage. No separate
NAS secret directory is needed.

Use unquoted, single-line values. Compose reads them as raw dotenv; double any
apostrophes for Homepage's single-quoted YAML substitution.

| Variables | Purpose |
| --- | --- |
| `HOMEPAGE_VAR_SYNOLOGY_USERNAME`, `HOMEPAGE_VAR_SYNOLOGY_PASSWORD` | DSM DiskStation widget |
| `HOMEPAGE_VAR_OPENWRT_USERNAME`, `HOMEPAGE_VAR_OPENWRT_PASSWORD` | OpenWrt `pppoe-wan` widget |
| `HOMEPAGE_VAR_UNIFI_USERNAME`, `HOMEPAGE_VAR_UNIFI_PASSWORD` | UniFi Controller widget |
| `HOMEPAGE_VAR_FORGEJO_PAT` | Read-only PAT for the Forgejo ticket repository, without the `token ` prefix |

Homepage and Bambuddy listen on NAS loopback. Forward both ports via SSH and
open <http://127.0.0.1:8300/>. The Bambuddy card uses the second forward.

```sh
ssh -N -L 8300:127.0.0.1:8300 -L 8000:127.0.0.1:8000 sysadmin@nas.homelab.internal
```
