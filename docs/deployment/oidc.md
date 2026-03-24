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
