output "item_uuid" {
  description = "UUID of the 1Password item"
  value       = onepassword_item.authentik_creds.uuid
}

# ---------------------------------------------------------------------------
# Emit the canonical op:// reference for every field so consumers can
# copy-paste paths directly into service configs or CI/CD secret stores.
# ---------------------------------------------------------------------------
output "secret_references" {
  description = "Map of field label → op:// reference path"
  value = {
    for f in local.fields :
    f.label => "op://${var.op_vault}/${var.op_item_title}/${f.label}"
  }
}
