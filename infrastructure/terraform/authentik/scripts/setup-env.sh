#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# scripts/setup-env.sh
#
# SOURCE this file (do NOT execute it directly) to populate the environment
# variables required by both Terraform providers before running plan/apply.
#
#   source scripts/setup-env.sh
#   terraform plan
#
# Optional overrides (set before sourcing):
#   OP_VAULT  – 1Password vault name   (default: DevOps)
#   OP_ITEM   – 1Password item title   (default: authentik)
#
# Reads from 1Password:
#   op://${OP_VAULT}/${OP_ITEM}/authentik_secret_key  →  AUTHENTIK_TOKEN
# ---------------------------------------------------------------------------

# Require bash ≥ 4 (macOS ships bash 3; install via `brew install bash`)
if [[ "${BASH_VERSINFO[0]}" -lt 4 ]]; then
  echo "[setup-env] ERROR: bash ≥ 4 required (current: ${BASH_VERSION})" >&2
  return 1 2>/dev/null || exit 1
fi

set -euo pipefail

OP_VAULT="${OP_VAULT:-DevOps}"
OP_ITEM="${OP_ITEM:-authentik}"

# Abort cleanly whether the script is sourced or executed directly
_fail() {
  echo "[setup-env] ERROR: $*" >&2
  return 1 2>/dev/null || exit 1
}

# ── 1. op CLI present? ────────────────────────────────────────────────────
command -v op &>/dev/null \
  || _fail "'op' CLI not found. Install: https://1password.com/downloads/command-line/"

# ── 2. 1Password session ──────────────────────────────────────────────────
if [[ -z "${OP_SERVICE_ACCOUNT_TOKEN:-}" ]]; then
  if ! op account list --format=json &>/dev/null; then
    echo "[setup-env] No active session – starting interactive sign-in..." >&2
    eval "$(op signin)" || _fail "op signin failed"
  fi
fi

# ── 3. authentik admin token → AUTHENTIK_TOKEN ────────────────────────────
_ref="op://${OP_VAULT}/${OP_ITEM}/authentik_secret_key"
echo "[setup-env] Reading AUTHENTIK_TOKEN from ${_ref} ..." >&2

AUTHENTIK_TOKEN="$(op read "${_ref}")" \
  || _fail "Could not read ${_ref} – verify vault/item/field names"

[[ -n "${AUTHENTIK_TOKEN}" ]] \
  || _fail "Token field is empty at ${_ref}"

export AUTHENTIK_TOKEN
echo "[setup-env] AUTHENTIK_TOKEN exported ✓" >&2

# ── 4. Pass through service account token for the TF provider (CI) ────────
if [[ -n "${OP_SERVICE_ACCOUNT_TOKEN:-}" ]]; then
  export OP_SERVICE_ACCOUNT_TOKEN
  echo "[setup-env] OP_SERVICE_ACCOUNT_TOKEN already set ✓" >&2
fi

unset _ref
echo "[setup-env] Environment ready — run: terraform plan / apply" >&2
