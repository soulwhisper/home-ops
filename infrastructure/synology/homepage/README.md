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

Before merging the Compose stack into `main`, provision these bind sources on
Synology so Doco CD can start the container:

- `/volume3/docker/homepage/config`: writable by `1000:1000` for logs and
  generated config. The dashboard YAML, CSS, and icons are read-only binds
  from the Doco CD checkout.
- `/volume3/docker/homepage/secrets`: owned by `1000:1000`, mode `0700`. Put
  the read-only widget credentials in the following files, each owned by
  `1000:1000` with mode `0600`. Use one line without a trailing newline; double
  any apostrophe inside a value for Homepage's single-quoted YAML substitution.
  Do not commit these files.

| Files | Purpose |
| --- | --- |
| `synology_username`, `synology_password` | DSM DiskStation widget |
| `openwrt_username`, `openwrt_password` | OpenWrt `pppoe-wan` widget |
| `unifi_username`, `unifi_password` | UniFi Controller widget |
| `forgejo_pat` | Read-only PAT for the Forgejo ticket repository, without the `token ` prefix |

Homepage and Bambuddy listen on NAS loopback. Forward both ports via SSH and
open <http://127.0.0.1:8300/>. The Bambuddy card uses the second forward.

```sh
ssh -N -L 8300:127.0.0.1:8300 -L 8000:127.0.0.1:8000 sysadmin@nas.homelab.internal
```
