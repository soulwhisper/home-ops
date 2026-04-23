terraform {
  required_version = ">= 1.5.0"

  required_providers {
    # authentik provider – used to resolve the admin token from 1Password
    # before any authentik resources/data-sources are accessed.
    authentik = {
      source  = "goauthentik/authentik"
      version = "~> 2026.2.0"
    }

    onepassword = {
      source  = "1Password/onepassword"
      version = "~> 3.0"
    }

    # null provider for local-exec upsert provisioners
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }

    # external provider for bash-based authentik API reads
    external = {
      source  = "hashicorp/external"
      version = "~> 2.3"
    }
  }
}
