# Application layer for dev — depends on lz_dev being deployed first.
# Consumes the shared VNet, Key Vault, and policy baseline provisioned by the landing zone.

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
  use_oidc = true
  # Authentication is handled via ARM_* environment variables injected by CI/CD (OIDC).
  # No explicit tenant_id, subscription_id, or client_id needed here.
}