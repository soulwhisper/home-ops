# ---------------------------------------------------------------------------
# Step 1 – Read OIDC credentials for each blueprint-managed app from authentik
# ---------------------------------------------------------------------------
module "oidc_reader" {
  source = "./modules/oidc-reader"

  app_slugs     = local.app_slugs
  authentik_url = var.authentik_url
}

# ---------------------------------------------------------------------------
# Step 2 – Sync all credentials into a single 1Password item
#           Creates the item on first apply; updates fields on subsequent runs.
# ---------------------------------------------------------------------------
module "op_updater" {
  source = "./modules/op-updater"

  op_vault      = var.op_vault
  op_item_title = var.op_item_title
  credentials   = module.oidc_reader.credentials
}
