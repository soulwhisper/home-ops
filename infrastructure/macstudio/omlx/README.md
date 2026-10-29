# macstudio oMLX configuration (GitOps-tracked)

Tracked config for the oMLX LLM server running on the Mac Studio
(`studio.homelab.internal`, 10.10.0.210). The machine lives outside the
Kubernetes cluster, so these files are **not** reconciled by flux — they are
the source of truth for manual (re)deployment and drift reference.

## Files

| File | Deploys to | Purpose |
|---|---|---|
| `settings.json` | `~/.omlx/settings.json` | Global server settings (secrets stripped) |
| `model_settings.json` | `~/.omlx/model_settings.json` | Per-model overrides (e.g. `ornith-1.5-35b-a3b` set to `max_context_window: 65536`) |

Intentionally **not** tracked: `stats.json`, `usage.sqlite3`, `logs/`,
`cache/` (telemetry/runtime state, regenerable), `~/models/*` (weights,
re-downloadable from Hugging Face — see model ids in `docs/application/ai.md`).

## Shared-memory policy

The server shares unified memory with ComfyUI. Keep the `safe` memory guard,
prefill guard, chunked prefill, and decode fairness enabled. The concurrency
setting is a per-engine batch limit, not a global lock between models.

- Limit each engine to two concurrent requests. Serialize image generation
  (`batch_size=1`) and avoid overlapping it with long LLM prefills.
- Keep the SSD prefix cache enabled and the RAM hot cache disabled. GDN
  sidecars retain FP32 precision; speculative decoding and ANE offload remain
  disabled until separately measured.
- Keep embeddings and reranking pinned. MiniCPM-o unloads after five idle
  minutes; Ornith after fifteen; the chat model after ten.
- Default output budgets are 4K globally, 8K for chat, 4K for Ornith, and 2K
  for MiniCPM-o. Client-supplied output limits override these defaults.
- Preserve the 64K model ceiling for chat and Ornith; use a 32K client window
  for ordinary requests. A smaller ceiling does not reduce weight residency.
- ComfyUI keeps its five-minute idle unload, disabled previews, and 8 GiB
  headroom. Keep infrequent image weights demand-loaded rather than pinning
  every LLM and image model together.

## Initial restore

`settings.json` ships with `INJECT_AT_DEPLOY` placeholders, not usable
credentials. The oMLX desktop app auto-starts on login, so **inject secrets into
a private temp file first and install last**; never install the placeholder
file where the server can read it. All secrets live in 1Password (item `omlx`);
never commit them.

```bash
# on macstudio
install -m 600 model_settings.json ~/.omlx/model_settings.json

# 1. generate or fetch values
API_KEY="$(op item get omlx --fields api_key)"            # server API key (consumers: cluster ES studio-api-auth)
SECRET_KEY="$(op item get omlx --fields secret_key)"      # admin-session signing key (64 hex chars)
SUB_KEY="$(op item get omlx --fields sub_key)"            # admin sub-key shown in the dashboard

# a failed lookup must abort here, not install empty credentials over working ones
: "${API_KEY:?op lookup failed or empty}" "${SECRET_KEY:?op lookup failed or empty}" "${SUB_KEY:?op lookup failed or empty}"

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

## Apply after merge

Only deploy the merged revision. The desktop application must own the complete
server lifecycle. Use its menu-bar Start/Restart Server action, or the bundled
`~/.omlx/bin/omlx restart` command, which delegates to the desktop application's
private control socket. Do not start `python -m omlx.server`: that minimal entry
point does not wire the scheduler and SSD prefix cache from settings.
Do not install or enable a separate Brew service, LaunchAgent, or LaunchDaemon.
The normal `application.app.omlx.*` launchd entry for a desktop application is
expected and is not a separate server service.

Deployment order:

1. Read the live settings remotely and retain a private, mode-0600 backup of
   both JSON files on the host. Never copy live credentials into the repository
   or command arguments.
2. Merge the tracked non-secret settings with the live `auth.api_key`,
   `auth.secret_key`, and complete `auth.sub_keys` list. Abort if credentials
   are missing or contain `INJECT_AT_DEPLOY`; do not replace them with tracked
   placeholders. Preserve the tracked authentication enforcement flags.
3. Parse both candidates before installing either. Write mode-0600 temporary
   files beside the live files, then atomically replace them. Keep the backups
   until verification completes.
4. Drain active requests. A restart interrupts all inference lanes. If the
   port-8000 listener belongs to an unmanaged shell, terminate only that
   verified server process gracefully before starting the desktop-owned
   server. Do not kill every Python process.
5. Close duplicate desktop application instances, then use its Start/Restart
   Server action or the bundled `omlx restart` command. Do not fall back to a
   manual module process when the application cannot start; inspect the startup
   error instead.

Verify ownership as well as health:

- Exactly one port-8000 listener and one intended desktop application instance.
  Inspect the listener's executable and parent chain. Query the private
  `~/Library/Application Support/oMLX/control.sock` with
  `{"command":"status"}` followed by a newline: its running PID must match the
  listener. A visible menu-bar application or a healthy API alone is not proof
  of desktop ownership.
- The server uses the bundled full CLI `serve` path, not a Brew executable or
  the minimal `omlx.server` module. No standalone oMLX launchd service or Brew
  formula/cask owns the listener.
- The application can stop and start that listener, producing a new server PID
  without a second server appearing.
- Authenticated `/health` and `/v1/models` succeed; short inference, embedding,
  and reranking requests work. Test image generation separately in an idle
  window.
- Confirm effective scheduler/cache initialization, not just the JSON file.
  Repeat a sufficiently long stable prefix across cache/snapshot boundaries
  and observe actual cache reuse. Check memory pressure, swap growth, and
  prefill rejection while exercising the intended concurrency.

Rollback: stop the desktop-owned server, restore both private backups, and
restart through the desktop application. Stop deployment if authentication,
tool calls, or image generation regress, or if memory pressure/swap growth
worsens. Keep the memory and authentication guards enabled during rollback.

## Sync discipline

After changing settings on the server (Admin UI or
`PUT /admin/api/...`), copy the file back here and **re-strip** `auth.api_key`,
`auth.secret_key`, and `auth.sub_keys[].key` before committing.
