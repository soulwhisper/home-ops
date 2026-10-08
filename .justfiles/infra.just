set lazy
set positional-arguments
set quiet
set script-interpreter := ['bash', '-euo', 'pipefail']
set shell := ['bash', '-euo', 'pipefail', '-c']

BUCKETS := 'postgres kopiur zot'
AWS_ENDPOINT_URL := env_var_or_default('AWS_ENDPOINT_URL', 'http://localhost:9000')

[private]
default:
  @just --list

[doc('Get 1password secrets')]
[script]
_op_get_secret item field:
  retries=5
  for (( count=1; count<=retries; count++ )); do
    if result=$(op item get "{{item}}" --fields "{{field}}" --reveal 2>/dev/null) && [[ -n "$result" ]]; then
      echo "$result"
      exit 0
    fi
    if [[ $count -lt $retries ]]; then
      echo "⚠️  [attempt ${count}/${retries}] failed to fetch {{field}} from {{item}}, retrying in 2s..." >&2
      sleep 2
    fi
  done
  echo "❌ failed to retrieve {{field}} from {{item}} after ${retries} attempts" >&2
  exit 1

[doc('Init/Reset Garage'), no-exit-message]
[script]
garage mode:
  for BUCKET in {{BUCKETS}}; do
    if [ "{{mode}}" = "init" ]; then
      echo "🔐 Fetching credentials for ${BUCKET}..."
      access_key=$(just _op_get_secret "garage" "${BUCKET}_access_key")
      secret_key=$(just _op_get_secret "garage" "${BUCKET}_secret_key")
      : "${access_key:?Access key is empty}"
      : "${secret_key:?Secret key is empty}"
      echo "🚀 Initializing bucket: ${BUCKET}"
      garage bucket create "${BUCKET}" || true
      garage key import "$access_key" "$secret_key" -n "${BUCKET}" --yes
      garage bucket allow --read --write "${BUCKET}" --key "${BUCKET}"
      echo "✅ Created bucket: ${BUCKET}"
    elif [ "{{mode}}" = "reset" ]; then
      garage bucket delete "${BUCKET}" || echo "⚠️ Bucket ${BUCKET} not found or already deleted"
      echo "🗑️ Deleted bucket: ${BUCKET}"
    else
      echo "❌ Unknown mode: {{mode}}"
      exit 1
    fi
  done

[doc('Init/Reset Versity S3 Gateway'), no-exit-message]
[script]
versity mode:
  echo "🔐 Fetching Admin Credentials..."
  AWS_ACCESS_KEY_ID=$(just _op_get_secret "app-user" "admin_user")
  AWS_SECRET_ACCESS_KEY=$(just _op_get_secret "app-user" "admin_pass")
  : "${AWS_ACCESS_KEY_ID:?AWS Access Key ID is missing}"
  : "${AWS_SECRET_ACCESS_KEY:?AWS Secret Key is missing}"
  export AWS_ACCESS_KEY_ID
  export AWS_SECRET_ACCESS_KEY
  for BUCKET in {{BUCKETS}}; do
    if [ "{{mode}}" = "init" ]; then
      if aws --endpoint-url "{{AWS_ENDPOINT_URL}}" s3api head-bucket --bucket "${BUCKET}" 2>/dev/null; then
        echo "ℹ️ Bucket ${BUCKET} already exists. Skipping."
      else
        echo "🚀 Creating bucket: ${BUCKET}"
        aws --endpoint-url "{{AWS_ENDPOINT_URL}}" s3api create-bucket --bucket "${BUCKET}"
        echo "✅ Created bucket: ${BUCKET}"
      fi
    elif [ "{{mode}}" = "reset" ]; then
      echo "🗑️ Deleting bucket: ${BUCKET}"
      aws --endpoint-url "{{AWS_ENDPOINT_URL}}" s3api delete-bucket --bucket "${BUCKET}" || echo "⚠️ Failed to delete or not found"
    else
      echo "❌ Unknown mode: {{mode}}"
      exit 1
    fi
  done

[doc('Sync forgejo skills + workflows into the homelab-tickets repo')]
[script]
forgejo-sync:
    set -euo pipefail
    PAT="$(op item get forgejo --fields pat_tickets --reveal)"
    tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' EXIT
    git clone "http://oauth2:${PAT}@nas.homelab.internal:9003/soulwhisper/homelab-tickets.git" "$tmp/repo"
    rsync -a --delete infrastructure/forgejo/skills/ "$tmp/repo/skills/"
    mkdir -p "$tmp/repo/.forgejo"
    rsync -a --delete infrastructure/forgejo/workflows/ "$tmp/repo/.forgejo/workflows/"
    git -C "$tmp/repo" add -A
    git -C "$tmp/repo" diff --cached --quiet \
      || git -C "$tmp/repo" commit -m "chore: sync skills + workflows from home-ops"
    git -C "$tmp/repo" push
