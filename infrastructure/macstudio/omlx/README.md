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

Intentionally **not** tracked: `stats.json`, `usage.sqlite3`, `logs/`,
`cache/` (telemetry/runtime state, regenerable), `~/models/*` (weights,
re-downloadable from Hugging Face — see model ids in `docs/application/ai.md`).

## Deploy / restore

`settings.json` ships with `INJECT_AT_DEPLOY` placeholders — the server will
not authenticate anything until real values are written. The oMLX desktop app
auto-starts on login, so **inject secrets into a private temp file first and
install last**; never install the placeholder file where the server can read
it. All secrets live in 1Password (item `omlx`); never commit them.

```bash
# on macstudio
install -m 600 model_settings.json ~/.omlx/model_settings.json

# 1. generate or fetch values
API_KEY="$(op item get omlx --fields api_key)"            # server API key (consumers: cluster ES studio-api-auth)
SECRET_KEY="$(op item get omlx --fields secret_key)"      # admin-session signing key (64 hex chars)
SUB_KEY="$(op item get omlx --fields sub_key)"            # admin sub-key shown in the dashboard

# 2. inject into a private temp file (not ~/.omlx), without touching the repo
#    copy; secrets travel via stdin pipe (printf is a shell builtin) so they
#    never appear in process arguments visible to `ps`
tmp="$(mktemp -t omlx-settings)" && chmod 600 "$tmp"

# 3. install only on a clean python exit — a failed injection removes $tmp
#    and leaves the live settings.json untouched
if printf '%s\n' "$API_KEY" "$SECRET_KEY" "$SUB_KEY" | python3 -c '
import json, sys
api_key, secret_key, sub_key = [l.rstrip("\n") for l in sys.stdin]
d = json.load(open("settings.json"))
d["auth"]["api_key"], d["auth"]["secret_key"] = api_key, secret_key
for sk in d["auth"].get("sub_keys", []):
  sk["key"] = sub_key
json.dump(d, sys.stdout, indent=2)
' > "$tmp"; then
  install -m 600 "$tmp" ~/.omlx/settings.json && rm -f "$tmp"
else
  rm -f "$tmp"
  echo "injection failed — ~/.omlx/settings.json left untouched" >&2
fi
```

If the 1Password item is lost, rotate instead of recover: `uuidgen` for
`api_key`, `openssl rand -hex 32` for `secret_key`, then update the cluster
ExternalSecret item (`studio-api-auth`) and every consumer key.

## Apply

```bash
# restart from the oMLX desktop app (menu bar -> Restart Server)
curl -H "Authorization: Bearer $API_KEY" http://127.0.0.1:8000/v1/models
```

## Sync discipline

After changing settings on the server (Admin UI or
`PUT /admin/api/...`), copy the file back here and **re-strip** `auth.api_key`,
`auth.secret_key`, and `auth.sub_keys[].key` before committing.
