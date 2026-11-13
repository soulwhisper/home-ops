#!/bin/zsh
set -euo pipefail

APP_HOME="$HOME/Library/Application Support/omni-audio"
OP="${OP:-/opt/homebrew/bin/op}"

# Inject the consumer-facing lane key without storing it in the plist or logs.
export OMNI_LANE_API_KEY="$("$OP" item get agentgateway --fields llm_omni)"

exec "$APP_HOME/venv/bin/uvicorn" \
  --factory omni_audio:create_app \
  --host 0.0.0.0 \
  --port 8010
