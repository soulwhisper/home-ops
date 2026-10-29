# macstudio ComfyUI configuration (GitOps-tracked)

Manual-deployment source for the clean ComfyUI server on Mac Studio
(`studio.homelab.internal`, 10.10.0.210). The host is outside Kubernetes, so
these files are not reconciled by Flux; they document and stage manual
redeployment.

## Layout

| File | Deploys to | Purpose |
|---|---|---|
| `sh.comfyui.plist` | `~/Library/LaunchAgents/sh.comfyui.plist` | ComfyUI WebUI/API on `0.0.0.0:8188` |
| `idle_offload.py` | `~/ComfyUI/tools/idle_offload.py` | Calls `/free` after five idle minutes |
| `sh.comfyui.idle-offload.plist` | `~/Library/LaunchAgents/sh.comfyui.idle-offload.plist` | Runs the idle offload check every 60s |
| `link_models.sh` | `~/ComfyUI/tools/link_models.sh` | Links Qwen Image weights into `~/ComfyUI/models/*` from `~/models` without copying |

Runtime state lives under the application checkout: `~/ComfyUI/data/user`,
`~/ComfyUI/data/*.log`, `~/ComfyUI/input`, and `~/ComfyUI/output`. Not
tracked: `~/ComfyUI` (upstream checkout), runtime data, generated images, and
model weights. The saved production workflow is imported from the prior
Desktop install into `~/ComfyUI/default_workflow.json`.

## Lifecycle and memory

- ComfyUI is an on-demand workload: the server stays light while idle; models
  load only on the first request.
- The idle-offload agent POSTs `/free` with `unload_models=true` and
  `free_memory=true` after both queue lists are empty for five minutes.
- ComfyUI starts with `--vram-headroom 8`, `--preview-method none`, and
  `--disable-assets`; launchd runs it at `Nice=10` with low-priority I/O.
- oMLX remains the production LLM service on port 8000 with
  `memory_guard_tier=safe` and `max_concurrent_requests=2` (see `../omlx/`).

The previous Comfy Desktop app was removed only after the clean install passed
an API generation. Its app and support directory were moved to
`~/Backups/comfy-desktop-removed-<timestamp>/`.
