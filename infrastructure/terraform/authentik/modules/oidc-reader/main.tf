# ---------------------------------------------------------------------------
# Derive provider names from the configurable pattern
# replace() is used instead of templatefile() so slugs remain in one local.
# ---------------------------------------------------------------------------
locals {
  provider_names = {
    for slug in var.app_slugs :
    slug => replace(var.provider_name_pattern, "{{slug}}", slug)
  }
}

# ---------------------------------------------------------------------------
# Look up each application by slug.
# These are managed by blueprints; we only read them here.
# ---------------------------------------------------------------------------
data "authentik_application" "this" {
  for_each = var.app_slugs
  slug     = each.key
}

# ---------------------------------------------------------------------------
# Look up the OAuth2 provider associated with each application.
#
# The authentik TF provider resolves providers by name. The name must match
# whatever the blueprint used. Adjust var.provider_name_pattern accordingly.
#
# client_id  – returned by the API in plain text
# client_secret – returned by the API; sensitive, stored in TF state encrypted
# ---------------------------------------------------------------------------
data "authentik_provider_oauth2" "this" {
  for_each = var.app_slugs
  name     = local.provider_names[each.key]
}
