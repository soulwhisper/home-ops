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

## Upstream release

`~/ComfyUI` is a Git checkout of [Comfy-Org/ComfyUI](https://github.com/Comfy-Org/ComfyUI)
at [`v0.46.0`](https://github.com/Comfy-Org/ComfyUI/releases/tag/v0.46.0)
(`a277b5bf213e8a44fa34817b7770b54f86ef4cea`). The existing `origin` uses
`comfyanonymous/ComfyUI`, which redirects to the same repository.

Run this from the logged-in ComfyUI user's Mac Studio session, with the
LaunchAgents installed at the paths above. Run the steps in order and stop on
any error.

1. Pause new WebUI and API submissions. Wait for both `queue_running` and
   `queue_pending` to be empty in `http://127.0.0.1:8188/queue`. Then unload
   both agents; the server's `KeepAlive` would otherwise restart it, and
   the idle helper uses the same `.venv`.

   ```bash
   launchctl bootout "gui/$(id -u)/sh.comfyui.idle-offload" &&
     launchctl bootout "gui/$(id -u)/sh.comfyui"
   ```

   Confirm both jobs are absent with `launchctl print` and port 8188 is no
   longer listening before touching the checkout or `.venv`.

2. Keep the checkout at `~/ComfyUI`. Record the old commit and back up the
   working environment and user data. Do not reset or clean the checkout:
   leave `data/`, saved workflows, `input/`, `output/`, and model links in
   place. Save the backup path printed on success for rollback.

   ```bash
   cd "$HOME/ComfyUI" &&
     mkdir -p "$HOME/Backups" &&
     backup="$(mktemp -d "$HOME/Backups/comfyui-release.XXXXXX")" &&
     git rev-parse HEAD > "$backup/commit" &&
     ditto .venv "$backup/.venv" &&
     ditto data/user "$backup/user" &&
     printf '%s\n' "$backup"
   ```

3. Switch to the recorded release and install from its requirements file
   into the exact interpreter used by launchd.

   ```bash
   cd "$HOME/ComfyUI" &&
     git fetch origin tag v0.46.0 &&
     test "$(git rev-parse 'v0.46.0^{commit}')" = a277b5bf213e8a44fa34817b7770b54f86ef4cea &&
     git switch --detach v0.46.0 &&
     uv pip install --python "$HOME/ComfyUI/.venv/bin/python" --compile-bytecode -r requirements.txt
   ```

4. Bootstrap the server first:

   ```bash
   launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/sh.comfyui.plist"
   ```

   Once `http://127.0.0.1:8188/queue` responds, bootstrap the helper:

   ```bash
   launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/sh.comfyui.idle-offload.plist"
   ```

   Check both jobs with `launchctl print` and run a saved workflow before
   resuming submissions.

**Rollback:** Keep submissions paused. Drain and boot out either agent still
loaded, then verify neither job is loaded and port 8188 is no longer listening.
Use the exact backup directory printed in step 2; confirm it contains
`commit`, `.venv`, and `user` before changing anything. In `~/ComfyUI`, switch
back to the commit recorded there, move the failed `.venv` aside, and restore
the backup's `.venv` with `ditto`. If the new version changed user data, move
`data/user` aside and restore the backup's `user` to `data/user`. Bootstrap
the same installed plists in the order above and verify the old release
before resuming submissions.

## Lifecycle and memory

- ComfyUI is an on-demand workload: the server stays light while idle; models
  load only on the first request.
- The idle-offload agent POSTs `/free` with `unload_models=true` and
  `free_memory=true` after both queue lists are empty for five minutes.
- ComfyUI starts with previews and asset scanning disabled. launchd runs it
  at `Nice=10` with low-priority I/O. DynamicVRAM is not active on MPS;
  ComfyUI does not reserve a fixed share of unified memory for oMLX.
- oMLX remains the production LLM service on port 8000 with a 50 GiB custom
  memory guard and `max_concurrent_requests=2` (see `../omlx/`).

The previous Comfy Desktop app was removed only after the clean install passed
an API generation. Its app and support directory were moved to
`~/Backups/comfy-desktop-removed-<timestamp>/`.
