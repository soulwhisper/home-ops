## OIDC

- authentik guides, [ref](https://integrations.goauthentik.io/applications/);

### Calibre

- must configure via WEB UI, [ref](https://github.com/crocodilestick/Calibre-Web-Automated/wiki/OAuth-Configuration);

### Home-assistant

- edit `/config/configuration.yaml` first;
- then install `hass-openid` plugin;

```yaml
# configuration.yaml
homeassistant:
  packages: !include_dir_named packages
```

### Jellyfin

- install plugin `9p4/jellyfin-plugin-sso` first;
- then configure via WEB UI, [ref](https://github.com/9p4/jellyfin-plugin-sso/blob/main/providers.md#authentik);

### Kavita

- must configure via WEB UI, [ref](https://wiki.kavitareader.com/guides/admin-settings/open-id-connect/);

### Rook Ceph Dashboard

- set saml2 manually, assume idp user is also `admin`;
- need `BackendConfigPolicy` to solve backend schema issues;

```shell
openssl req -new -nodes -x509 \
  -subj "/O=Rook/CN=rook-ceph-mgr-dashboard.storage-system.svc.cluster.local" \
  -addext "subjectAltName=DNS:rook-ceph-mgr-dashboard.storage-system.svc.cluster.local" \
  -days 3650 \
  -keyout dashboard.key \
  -out dashboard.crt

kubectl -n storage-system create secret generic rook-ceph-dashboard-ca \
  --from-file=ca.crt=dashboard.crt

CERT=$(cat dashboard.crt)
kubectl rook-ceph ceph config-key set mgr/dashboard/crt "$CERT"

KEY=$(cat dashboard.key)
kubectl rook-ceph ceph config-key set mgr/dashboard/key "$KEY"

kubectl rook-ceph ceph mgr module disable dashboard
kubectl rook-ceph ceph mgr module enable dashboard

kubectl rook-ceph ceph dashboard sso setup saml2 \
  "https://rook.noirprime.com" \
  "https://auth.noirprime.com/application/saml/rook-ceph/metadata/" \
  "username"

kubectl rook-ceph ceph dashboard sso status
```

## Other

### Astrbot

- use its own user system;

### Crafty-4

- login via `admin` and below password;

```shell
kubectl -n gaming-apps exec crafty-controller -- cat /crafty/app/config/default-creds.txt
```

### Dify

- use its own user system;

### Dispatcharr

- use its own user system;

### FoundryVTT

- use its own user system;

### Moviepilot

- use its own user system;

### Scrypted

- signup as `admin`, then forwardAuth works;
