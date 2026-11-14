# Omni audio service

Standalone MiniCPM-O 4.5 audio service for the pinned
`~/Library/Application Support/omni-audio/model` checkout, outside oMLX's
`~/models` scan root. It uses `mlx-vlm` directly rather than oMLX's VLM
audio-message routing or its `STTEngine` gate.

The service loads Omni once at startup and keeps it resident. It listens on
`0.0.0.0:8010`; oMLX remains on port 8000 for the other models. Do not run both
Omni engines after cutover.

## Capabilities

- `POST /v1/chat/completions` — OpenAI-compatible text, inline image, and inline
  audio chat for existing Omni consumers.
- `POST /v1/audio/transcriptions` — multilingual audio-to-text using the
  official MiniCPM-O ASR prompts.
- `POST /v1/audio/speech` — text to 24 kHz WAV speech.
- `POST /v1/audio/conversation` — audio input, response text, and base64 WAV
  speech output in one response.
- `GET /v1/models/omni` — authenticated model discovery.
- `GET /healthz` — process and model-load health.
- `WEBSOCKET /v1/audio/realtime` — PCM16 input events, text/audio response
  events, commit, cancellation, and disconnect cleanup.

Realtime clients can authenticate with the forwarded HTTP `Authorization` header
or with `start.api_key` for direct connections. The `start` message also accepts
optional `voice` and `language` fields. Clients then send base64 PCM16
`input_audio_buffer.append` and `input_audio_buffer.commit` events.
Responses contain `response.text.delta`, base64 PCM16
`response.audio.delta`, and `response.done`. Audio output is chunked after the
current non-streaming `generate_audio()` call completes; this is not the
upstream TDM full-duplex implementation. Cancellation suppresses the response
but cannot preempt an already-running MLX generation.

All model inference is serialized, with at most four waiting requests. Audio
inputs are limited to 100 MiB and ten minutes.

## Authentication

The service reads the upstream key from `OMNI_API_KEY` or the existing
`auth.api_key` in `~/.omlx/settings.json`. It also requires
`OMNI_LANE_API_KEY`, containing the consumer-facing `llm_omni` credential for
requests forwarded by agentgateway. The LaunchAgent's `run.sh` reads that field
from 1Password without storing it in the plist or logging it. Direct upstream
calls and forwarded lane calls are checked independently; realtime connections
accept either the forwarded header or the initial `start.api_key`. No credential
is copied into this repository.

## Voices

Optional named voices are read from `~/.omlx/voices/<name>.wav`. Names use
lowercase letters, digits, `_`, and `-`. Unknown names are rejected. If no voice
is supplied, the model's normal speech default applies. Voice selection never
accepts a client-provided filesystem path.

## Install after merge

Use Python 3.12 or newer. Run these steps on the Mac Studio only after the PR
is merged. Unload Omni from oMLX first, then move its checkout before installing
the LaunchAgent. `RunAtLoad` and `KeepAlive` require the destination model to
exist before bootstrap:

```sh
(
set -eu
test -d "$HOME/models/minicpm-o-4.5"
test ! -e "$HOME/Library/Application Support/omni-audio/model"
install -d "$HOME/Library/Application Support/omni-audio"
mv "$HOME/models/minicpm-o-4.5" \
  "$HOME/Library/Application Support/omni-audio/model"
install -m 644 omni_audio.py requirements.txt \
  "$HOME/Library/Application Support/omni-audio/"
install -m 755 run.sh "$HOME/Library/Application Support/omni-audio/"
uv venv --python 3.13 "$HOME/Library/Application Support/omni-audio/venv"
uv pip install \
  --python "$HOME/Library/Application Support/omni-audio/venv/bin/python" \
  -r "$HOME/Library/Application Support/omni-audio/requirements.txt"
install -m 644 sh.homelab.omni-audio.plist "$HOME/Library/LaunchAgents/"
launchctl bootstrap "gui/$(id -u)" \
  "$HOME/Library/LaunchAgents/sh.homelab.omni-audio.plist"
launchctl kickstart -k "gui/$(id -u)/sh.homelab.omni-audio"
)
```

The LaunchAgent runs `run.sh`, which injects the lane key and starts uvicorn
with `--factory omni_audio:create_app`, binds port 8010, and restarts with a
ten-second throttle. Startup failure must be fixed in the service or its
environment; do not start a second copy on another port.

## Verification and cutover

1. Confirm the checkout is now `$HOME/Library/Application Support/omni-audio/model`
   and oMLX no longer discovers it. Keep the checkout outside `~/models`;
   copying it back would allow a second engine to load it.
2. Start the service and verify `/healthz` reports `"loaded": true` after model
   initialization.
3. Use authenticated requests on port 8010 to verify a known WAV through
   transcription, speech, and audio conversation. Check English and Chinese
   output and a named voice when one is configured. Omni speech is verified on
   this service; VoxCPM2 retains the existing gateway `/v1/audio/speech` lane.
4. Confirm the relocated model path, listener port 8010, logs, and memory
   pressure. The standalone process is outside oMLX's memory guard, so measure
   before cutover.
5. Only after real-model validation, open the separate gateway migration PR.
   Keep the current gateway backend unchanged until that PR is deployed.

Rollback: stop only `sh.homelab.omni-audio`, move the checkout back to
`~/models/minicpm-o-4.5`, and restore the previous oMLX model settings. Preserve
voice/reference files. No gateway rollback is needed before the migration PR.

## Tests

The repository tests exercise audio normalization, authentication, valid WAV
conversation responses, unknown-voice rejection, realtime PCM events, and
invalid PCM input with a deterministic fake engine. They do not claim to verify
MiniCPM-O quality. Run the real-model verification above on the Mac Studio.
