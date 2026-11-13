# Omni audio service

Standalone MiniCPM-O 4.5 audio service for the existing pinned
`~/models/minicpm-o-4.5` checkout. It uses `mlx-vlm` directly rather than
oMLX's VLM audio-message routing or its `STTEngine` gate.

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

Realtime clients send `start` with `api_key`, optional `voice`, and `language`,
then base64 PCM16 `input_audio_buffer.append` and `input_audio_buffer.commit`
events. Responses contain `response.text.delta`, base64 PCM16
`response.audio.delta`, and `response.done`. Audio output is chunked after the
current non-streaming `generate_audio()` call completes; this is not the
upstream TDM full-duplex implementation. Cancellation suppresses the response
but cannot preempt an already-running MLX generation.

All model inference is serialized, with at most four waiting requests. Audio
inputs are limited to 100 MiB and ten minutes.

## Authentication

The service reads `OMNI_API_KEY` first, then the existing `auth.api_key` from
`~/.omlx/settings.json`. No credential is copied into this repository. The
agentgateway backend injects the same upstream key through `studio-api-auth`.
All `/v1/*` endpoints require bearer authentication; the realtime WebSocket
authenticates its initial `start` message.

## Voices

Optional named voices are read from `~/.omlx/voices/<name>.wav`. Names use
lowercase letters, digits, `_`, and `-`. Unknown names are rejected. If no voice
is supplied, the model's normal speech default applies. Voice selection never
accepts a client-provided filesystem path.

## Install after merge

Use Python 3.12 or newer. Run these steps on the Mac Studio only after the PR
is merged:

```sh
install -d "$HOME/Library/Application Support/omni-audio"
install -m 644 omni_audio.py requirements.txt \
  "$HOME/Library/Application Support/omni-audio/"
uv venv --python 3.13 "$HOME/Library/Application Support/omni-audio/venv"
uv pip install \
  --python "$HOME/Library/Application Support/omni-audio/venv/bin/python" \
  -r "$HOME/Library/Application Support/omni-audio/requirements.txt"
install -m 644 sh.homelab.omni-audio.plist "$HOME/Library/LaunchAgents/"
launchctl bootstrap "gui/$(id -u)" \
  "$HOME/Library/LaunchAgents/sh.homelab.omni-audio.plist"
launchctl kickstart -k "gui/$(id -u)/sh.homelab.omni-audio"
```

The LaunchAgent runs uvicorn with `--factory omni_audio:create_app`, binds port
8010, and restarts with a ten-second throttle. Startup failure must be fixed in
the service or its environment; do not start a second copy on another port.

## Verification and cutover

1. Start the service and verify `/healthz` reports `"loaded": true` after model
   initialization.
2. Use authenticated requests to verify a known WAV through transcription,
   speech, and audio conversation. Check English and Chinese output and a named
   voice when one is configured.
3. Confirm the pinned model path, listener port 8010, logs, and memory pressure.
   The standalone process is outside oMLX's memory guard, so measure before
   cutover.
4. Unload Omni from oMLX and keep it absent from `model_settings.json`; do not
   leave both engines resident.
5. Point `llm-backend-omni` to port 8010 and verify authenticated chat, vision,
   transcription, and speech through agentgateway.

Rollback: point the gateway backend to port 8000, restore the previous oMLX
model settings, and stop only `sh.homelab.omni-audio` after the gateway has
moved back. Preserve the model checkout and all voice/reference files.

## Tests

The repository tests exercise audio normalization, authentication, valid WAV
conversation responses, unknown-voice rejection, realtime PCM events, and
invalid PCM input with a deterministic fake engine. They do not claim to verify
MiniCPM-O quality. Run the real-model verification above on the Mac Studio.
