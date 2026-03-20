# ---------------------------------------------------------------------------
# credentials – consumed by module op-updater
# ---------------------------------------------------------------------------
output "credentials" {
  description = "Map of slug → OIDC credential attributes"
  sensitive   = true
  value = {
    for slug in var.app_slugs : slug => {
      client_id     = data.authentik_provider_oauth2.this[slug].client_id
      client_secret = data.authentik_provider_oauth2.this[slug].client_secret
      issuer_url    = "${var.authentik_url}/application/o/${slug}/"
      well_known    = "${var.authentik_url}/application/o/${slug}/.well-known/openid-configuration"
    }
  }
}
