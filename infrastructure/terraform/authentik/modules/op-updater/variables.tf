variable "op_vault" {
  description = "1Password vault name"
  type        = string
}

variable "op_item_title" {
  description = "Title of the 1Password item to create or update (e.g. 'authentik')"
  type        = string
}

variable "credentials" {
  description = "Map of slug → {client_id, client_secret, issuer_url, well_known}"
  type = map(object({
    client_id     = string
    client_secret = string
    issuer_url    = string
    well_known    = string
  }))
  sensitive = true
}
