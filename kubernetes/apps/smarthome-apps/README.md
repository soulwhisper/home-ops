## Smarthome-apps

### Home-assistant

- first time boot, edit `/config/configuration.yaml` first;
- then install `hass-openid` plugin;

```
homeassistant:
  packages: !include_dir_named packages
```
