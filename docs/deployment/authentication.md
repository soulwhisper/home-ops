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

### N8N

- must configure via WEB UI, [ref](https://docs.n8n.io/user-management/oidc/setup/);

## Other

### Crafty-4

- login via `admin` and below password;

```shell
kubectl -n gaming-apps exec crafty-controller -- cat /crafty/app/config/default-creds.txt
```

### Dispatcharr

- use its own user system;

### Moviepilot

- use its own user system;

### Rook Ceph Dashboard

- login via `admin` and below password;

```shell
kubectl -n storage-system get secret rook-ceph-dashboard-password -o jsonpath="{['data']['password']}" | base64 --decode && echo
```

### Scrypted

- signup as `admin`, then forwardAuth works;
