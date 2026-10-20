# dsh-web (Synology)

DeepSeek Harness agent workbench, deployed via doco-cd.

- **Access**: `http://nas.homelab.internal:9400`
- **First login**: `docker logs dsh-web` shows the startup-token URL (replace
  the loopback host with the NAS address); the baked `dsh-ui-auth` plugin
  creates the admin account on first boot and writes credentials to
  `workspace/dsh-ui-auth-bootstrap.txt` (mounted at
  `/volume3/docker/dsh-web/workspace`). Change the password immediately.
  After that, the ui-auth login page is the entry; sessions survive restarts.
- **Model**: Settings → 模型 → OpenAI-compatible, base URL
  `https://api.noirprime.com/v1`, key = 1Password `agentgateway.llm_agent`
  (agent lane; omni reachable via cross-lane enrollment). Persisted on the
  data volume (`/volume3/docker/dsh-web/dsh-home`).
- **Plugins**: runtime installs allowed (`dshmarket` baked in the image);
  bundled pins in `containers/apps/dsh-web` only cover the first boot.
- **Data**: `/volume3/docker/dsh-web/{dsh-home,workspace}` — covered by the
  volume3 btrfs snapshot convention (same as scrutiny).
