#!/bin/sh
# Creates the authentik OIDC auth source in Forgejo. IDEMPOTENT.
#
# Forgejo/Gitea has no REST API for auth sources — this CLI is the only
# supported path. Run ONCE on the NAS after BOTH are live:
#   1. https://git.noirprime.com answers (kubernetes forgejo-proxy route)
#   2. ROOT_URL=https://git.noirprime.com/ applied (docker-compose.yml, this repo)
# The client_id/secret are operator-generated, stored in 1Password
# (`authentik` item, forgejo_oidc_client_id/secret fields) — the authentik
# blueprint reads the same pair. Export them before running:
#   FORGEJO_OIDC_CLIENT_ID=... FORGEJO_OIDC_CLIENT_SECRET=... sh oidc-auth-source.sh
set -eu

: "${FORGEJO_OIDC_CLIENT_ID:?set from 1Password authentik item}"
: "${FORGEJO_OIDC_CLIENT_SECRET:?set from 1Password authentik item}"

# auth list hits the DB through the app config; run as the container's git user
if docker exec -u git forgejo forgejo admin auth list | grep -q 'authentik'; then
  echo "auth source 'authentik' already exists — nothing to do"
  exit 0
fi

docker exec -u git forgejo forgejo admin auth add-oauth \
  --name authentik \
  --provider openidConnect \
  --key "${FORGEJO_OIDC_CLIENT_ID}" \
  --secret "${FORGEJO_OIDC_CLIENT_SECRET}" \
  --auto-discover-url "https://auth.noirprime.com/application/o/forgejo/.well-known/openid-configuration" \
  --group-claim-name groups \
  --admin-group homelab-admin

echo "created. Verify: https://git.noirprime.com/user/login should offer 'authentik'."
echo "Local accounts (admin) stay as break-glass on the direct URL."
