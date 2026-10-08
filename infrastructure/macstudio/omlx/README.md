# macstudio oMLX configuration (GitOps-tracked)

Tracked config for the oMLX LLM server running on the Mac Studio
(`studio.homelab.internal`, 10.10.0.210). The machine lives outside the
Kubernetes cluster, so these files are **not** reconciled by flux — they are
the source of truth for manual (re)deployment and drift reference.

## Files

| File | Deploys to | Purpose |
|---|---|---|
| `settings.json` | `~/.omlx/settings.json` | Global server settings (secrets stripped) |
| `model_settings.json` | `~/.omlx/model_settings.json` | Per-model overrides (e.g. `qwen-agentworld-35b-a3b` pinned to `max_context_window: 65536`) |
| `sh.brew.omlx.plist` | `~/Library/LaunchAgents/sh.brew.omlx.plist` | launchd unit (`omlx serve`, KeepAlive) |

Intentionally **not** tracked: `stats.json`, `usage.sqlite3`, `logs/`,
`cache/` (telemetry/runtime state, regenerable), `~/models/*` (weights,
re-downloadable from Hugging Face — see model ids in `docs/application/ai.md`).

## Deploy / restore

```bash
# on macstudio
install -m 600 settings.json       ~/.omlx/settings.json
install -m 600 model_settings.json ~/.omlx/model_settings.json
install -m 644 sh.brew.omlx.plist  ~/Library/LaunchAgents/sh.brew.omlx.plist
```

## Injecting secrets after deploy (REQUIRED)

`settings.json` ships with `INJECT_AT_DEPLOY` placeholders — the server will
not authenticate anything until real values are written. All secrets live in
1Password (item `omlx`); never commit them.

```bash
# 1. generate or fetch values
API_KEY="$(op item get omlx --fields api_key)"            # server API key (consumers: cluster ES studio-api-auth)
SECRET_KEY="$(op item get omlx --fields secret_key)"      # admin-session signing key (64 hex chars)
SUB_KEY="$(op item get omlx --fields sub_key)"            # admin sub-key shown in the dashboard

# 2. inject without touching the rest of the file
python3 - "$API_KEY" "$SECRET_KEY" "$SUB_KEY" <<'EOF'
import json, os, sys
p = os.path.expanduser("~/.omlx/settings.json")
d = json.load(open(p))
d["auth"]["api_key"], d["auth"]["secret_key"] = sys.argv[1], sys.argv[2]
for sk in d["auth"].get("sub_keys", []):
    sk["key"] = sys.argv[3]
json.dump(d, open(p, "w"), indent=2)
EOF
chmod 600 ~/.omlx/settings.json
```

If the 1Password item is lost, rotate instead of recover: `uuidgen` for
`api_key`, `openssl rand -hex 32` for `secret_key`, then update the cluster
ExternalSecret item (`studio-api-auth`) and every consumer key.

## Apply

```bash
launchctl kickstart -k gui/$(id -u)/sh.brew.omlx   # restart via launchd
# or: omlx restart
curl -H "Authorization: Bearer $API_KEY" http://127.0.0.1:8000/v1/models
```

## Sync discipline

After changing settings on the server (Admin UI or
`PUT /admin/api/...`), copy the file back here and **re-strip** `auth.api_key`,
`auth.secret_key`, and `auth.sub_keys[].key` before committing.
