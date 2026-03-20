variable "app_slugs" {
  description = "Set of authentik application slugs to read OIDC data for"
  type        = set(string)
}

variable "authentik_url" {
  description = "Base URL of the authentik instance"
  type        = string
}

variable "provider_name_pattern" {
  description = "Template for the OIDC provider name; {{slug}} is replaced with the app slug"
  type        = string
  default     = "{{slug}}"
}
