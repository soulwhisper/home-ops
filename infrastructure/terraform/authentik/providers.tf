# authentik provider
provider "authentik" {
  url = var.authentik_url
}

# 1Password provider
provider "onepassword" {
  account = var.op_account
}
