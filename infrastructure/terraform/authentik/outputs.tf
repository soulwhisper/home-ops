# client_id values are not secret (they appear in browser redirect URIs, logs, etc.)
# nonsensitive() unwraps them from the sensitive credentials bundle so they
# can be inspected with `terraform output app_client_ids` without -json.
output "app_client_ids" {
  description = "Map of app slug → OIDC client_id (non-sensitive)"
  value = nonsensitive({
    for slug, cred in module.oidc_reader.credentials : slug => cred.client_id
  })
}

output "op_item_uuid" {
  description = "UUID of the 1Password 'authentik' item that stores all OIDC credentials"
  value       = module.op_updater.item_uuid
}

# op:// paths are safe to emit as non-sensitive: they are path references,
# not the secrets themselves. The actual values require 1Password auth to read.
output "op_secret_references" {
  description = "op:// reference paths for every credential field – paste into service configs or CI/CD"
  value       = module.op_updater.secret_references
}
