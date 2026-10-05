# Application Authentication

## OIDC via Authentik

14 applications use Authentik OIDC for SSO, managed declaratively via Blueprints (ConfigMap + Secret).

| App                  | OIDC Provider | Notes                                                                 |
| -------------------- | :-----------: | --------------------------------------------------------------------- |
| Grafana              |   Authentik   | SSO-protected                                                         |
| Headlamp             |   Authentik   | K8s dashboard with read-only SA                                       |
| Home Assistant       |   Authentik   | Requires `hass-openid` plugin + `/config/configuration.yaml` packages |
| Immich               |   Authentik   | Configure via Admin Settings                                          |
| Jellyfin             |   Authentik   | Install `jellyfin-plugin-sso` first, then web UI config               |
| Karakeep             |   Authentik   | SSO-protected                                                         |
| Kavita               |   Authentik   | Configure via Admin Settings                                          |
| NetBox               |   Authentik   | SSO-protected                                                         |
| Qbittorrent-UI (QUI) |   Authentik   | SSO-protected web UI                                                  |
| Stirling-PDF         |   Authentik   | SSO-protected                                                         |

New OIDC apps are added by creating a Blueprint Secret (`authentik-blueprints-oidc-<name>`) and referencing it in the Authentik HelmRelease.

## Built-in Authentication

These apps use their own authentication — no OIDC needed:

| App                 | Auth Method                                             |
| ------------------- | ------------------------------------------------------- |
| Bambuddy            | Bambu Lab account                                       |
| Crafty Controller   | Default admin credentials (retrieve via `kubectl exec`) |
| Dispatcharr         | Built-in user system                                    |
| Fast-Note-Sync      | Built-in user system                                    |
| FoundryVTT          | Built-in user system                                    |
| MoviePilot          | Built-in user system                                    |
| Navidrome           | Built-in user system                                    |
| Rook-Ceph Dashboard | Built-in auth (or SAML2 via manual setup)               |
| Scrypted            | Sign up as `admin`, ForwardAuth compatible              |

## No Authentication

| App            | Reason                                                                       |
| -------------- | ---------------------------------------------------------------------------- |
| MeTube         | Single-user download tool                                                    |
| God's Eye View | No built-in auth by design; protected by authentik forward-auth at the gateway |

## Forward Auth (embedded outpost)

Apps without built-in auth sit behind the authentik embedded outpost via `components/authentik` (ext-authz TrafficPolicy + `/outpost.goauthentik.io` route). Adding one takes **two** blueprint changes — both are required:

1. `blueprints/forward/<app>.yaml` — creates the app's `forward_domain` proxy provider (`external_host` = app URL, `cookie_domain: noirprime.com`).
2. `blueprints/core/outpost-proxy.yaml` — bind the new provider to the Embedded Outpost's `providers` list. The outpost maps host → provider via `x-forwarded-host`; an unbound provider makes the outpost fall back to an arbitrary bound provider, so logins redirect to a *different* app's domain (observed 2026-09 with `gods-eye-view`: spy.noirprime.com bounced to ai/traces/hubble/z2m).

The outpost route and TrafficPolicy are injected per-app by the kustomize component; no per-app wiring is needed beyond the flux `components:` entry and `APP_HOST` substitution.

## Rook-Ceph SAML2 (Manual)

If SAML2 SSO is needed for the Ceph dashboard:

```shell
openssl req -new -nodes -x509 \
  -subj "/O=Rook/CN=rook-ceph-mgr-dashboard.storage-system.svc.cluster.local" \
  -addext "subjectAltName=DNS:rook-ceph-mgr-dashboard.storage-system.svc.cluster.local" \
  -days 3650 -keyout dashboard.key -out dashboard.crt

kubectl -n storage-system create secret generic rook-ceph-dashboard-ca \
  --from-file=ca.crt=dashboard.crt

CERT=$(cat dashboard.crt) && kubectl rook-ceph ceph config-key set mgr/dashboard/crt "$CERT"
KEY=$(cat dashboard.key) && kubectl rook-ceph ceph config-key set mgr/dashboard/key "$KEY"

kubectl rook-ceph ceph mgr module disable dashboard
kubectl rook-ceph ceph mgr module enable dashboard

kubectl rook-ceph ceph dashboard sso setup saml2 \
  "https://rook.noirprime.com" \
  "https://auth.noirprime.com/application/saml/rook-ceph/metadata/" \
  "username"
```
