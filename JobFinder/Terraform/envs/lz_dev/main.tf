# Landing zone (hub) for dev — must be deployed before the app layer (dev/).
# Provides the shared foundation: resource group, Key Vault, and VNet.

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
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

# Needed to retrieve the current client's tenant_id for the Key Vault access policy.
data "azurerm_client_config" "current" {}

# ==============================================================================
# Resource Group
# ==============================================================================

resource "azurerm_resource_group" "rg" {
  name     = "rg-${var.project}-lz-dev-${var.location_short}"
  location = var.location

  tags = {
    environment = "lz-dev"
    project     = var.project
    owner       = var.owner
  }
}

