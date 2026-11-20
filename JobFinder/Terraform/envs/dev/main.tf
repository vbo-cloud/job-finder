# Application layer for dev — depends on lz_dev being deployed first.
# Consumes the shared VNet, Key Vault, and policy baseline provisioned by the landing zone.

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.8"
    }
    # Used only for the frontend custom domain certificate binding (frontend.tf):
    # azurerm_container_app_custom_domain cannot attach an Azure-managed certificate
    # (only a bring-your-own one) -- see the comment above azapi_update_resource
    # "frontend_custom_domain_binding" in frontend.tf for the full explanation.
    azapi = {
      source  = "azure/azapi"
      version = "~> 2.0"
    }
  }
}

provider "azurerm" {
  features {}
  use_oidc = true
  # Authentication is handled via ARM_* environment variables injected by CI/CD (OIDC).
  # No explicit tenant_id, subscription_id, or client_id needed here.
}

provider "azapi" {
  # Same ARM_* OIDC environment variables as the azurerm provider above -- no
  # separate configuration needed.
}

data "azurerm_client_config" "current" {}
