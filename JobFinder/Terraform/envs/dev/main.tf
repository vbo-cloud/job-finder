# Application layer for dev — DECOMMISSIONED (PR #270): all application resources were
# removed from this directory. Only the providers, backend and variables remain, because
# Terraform needs the providers to destroy what is still recorded in the state.
# To redeploy, restore the removed files from the git tag `archive/pre-decommission`.

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
    # Kept only so the state can be destroyed: it was used for the frontend custom domain
    # certificate binding (frontend.tf, now removed -- see tag `archive/pre-decommission`).
    # azurerm_container_app_custom_domain cannot attach an Azure-managed certificate.
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
