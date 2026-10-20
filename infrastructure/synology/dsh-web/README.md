# dsh-web (Synology)

DeepSeek Harness agent workbench, deployed via doco-cd.

## One-time NAS setup (Synology ACL)

Bind mounts under `/volume3/docker` carry a Synology ACL that grants
`everyone` **read-only** regardless of the unix mode bits (777 included) —
the container's writes fail with EACCES and the pod restart-loops
(`cp: ... Permission denied`). Grant write to the `users` group once
(matches `group_add: 100` in the compose):

```sh
/usr/syno/bin/synoacltool -add /volume3/docker/dsh-web/data "group:users:allow:rwxpdDaARWc--:fd--"
/usr/syno/bin/synoacltool -add /volume3/docker/dsh-web/workspace "group:users:allow:rwxpdDaARWc--:fd--"
```

(skip once the dirs already carry the entry — check with
`synoacltool -get <dir>`)

- **Access**: `http://nas.homelab.internal:9400` (plain HTTP on the trusted
  LAN — same accepted pattern as forgejo on :9003).
- **First login (token in transit caveat)**: the startup-token URL is a
  bearer credential; do the ONE-TIME token exchange through an SSH tunnel so
  it never crosses the LAN in cleartext:
  `ssh -L 9400:127.0.0.1:9400 nas.homelab.internal`, then open
  `http://127.0.0.1:9400/?token=…` (token from `docker logs dsh-web`).
  The exchange yields a signed ui-auth session cookie; afterwards the normal
  login page is the entry. Later logins go through the ui-auth form (password
  over LAN HTTP is the accepted intranet risk, same as forgejo).
  The baked `dsh-ui-auth` plugin creates the admin account on first boot and
  also writes credentials to `workspace/dsh-ui-auth-bootstrap.txt` (mounted
  at `/volume3/docker/dsh-web/workspace`). Change the password immediately.
- **Model**: Settings → Model → OpenAI-compatible, base URL
  `https://api.noirprime.com/v1`, key = 1Password `agentgateway.llm_agent`
  (agent lane; omni reachable via cross-lane enrollment). Persisted on the
  data volume (`/volume3/docker/dsh-web/dsh-home`).
- **MCP**: Settings → MCP → add `https://api.noirprime.com/mcp/search`
  (streamable HTTP), bearer = 1Password `agentgateway.mcp_search` — this is
  open-webui's former set: the search tier (firecrawl, context7, trendradar,
  github-ro), CEL-allowlisted at the gateway and behind the mcp-guardrails
  sidecar.
- **Plugins**: runtime installs allowed (`dshmarket` baked in the image);
  bundled pins in `containers/apps/dsh-web` only cover the first boot.
- **Data**: `/volume3/docker/dsh-web/{dsh-home,workspace}` — covered by the
  volume3 btrfs snapshot convention (same as scrutiny).
