# ---------------------------------------------------------------------------
# Flatten credentials into a list-of-objects that the dynamic field block
# can iterate without ambiguity.
# ---------------------------------------------------------------------------
locals {
  fields = concat(
    [for slug, c in var.credentials : {
      label     = "${slug}_oidc_client_id"
      value     = c.client_id
      concealed = false
    }],
    [for slug, c in var.credentials : {
      label     = "${slug}_oidc_client_secret"
      value     = c.client_secret
      concealed = true
    }],
  )
}

# ---------------------------------------------------------------------------
# 1Password item
#
# Lifecycle:
#   First apply   → item does not exist in state → created in 1Password
#   Later applies → in state → fields are diffed and updated in-place
#   Add slug      → new *_oidc_* fields appended to existing item
#   Remove slug   → corresponding fields removed from item
#
# Pre-existing item (not in state):
#   Import before the first apply to avoid a duplicate item:
#
#     OP_VAULT_UUID=$(op vault get myvault --format json | jq -r .id)
#     OP_ITEM_UUID=$(op item get authentik --vault myvault --format json | jq -r .id)
#     terraform import module.op_updater.onepassword_item.authentik_creds \
#       ${OP_VAULT_UUID}/${OP_ITEM_UUID}
# ---------------------------------------------------------------------------
resource "onepassword_item" "authentik_creds" {
  vault    = var.op_vault
  title    = var.op_item_title
  category = "login"

  # All credential fields live inside a single "oidc" section for a tidy
  # 1Password UI. The short op:// path works without a section qualifier
  # because field labels are unique within the item.
  section {
    label = "oidc"

    dynamic "field" {
      for_each = local.fields
      content {
        label = field.value.label
        type  = field.value.concealed ? "CONCEALED" : "STRING"
        value = field.value.value
      }
    }
  }
}
