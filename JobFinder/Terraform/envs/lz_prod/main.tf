# Landing zone (hub) for prod — mirror of lz_dev but isolated in its own state and resource group.
# Must be deployed before the app layer (prod/).

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

data "azurerm_client_config" "current" {}

# ==============================================================================
# Resource Group
# ==============================================================================

resource "azurerm_resource_group" "rg" {
  name     = "rg-${var.project}-lz-prod-${var.location_short}"
  location = var.location

  tags = {
    environment = "lz-prod"
    project     = var.project
    owner       = var.owner
  }
}

