# ==============================================================================
# Azure Policies — subscription-scoped, managed from lz_dev
# ==============================================================================

module "policy_allowed_locations" {
  source = "../../modules/policy/allowed_locations"

  environment       = "lz-dev"
  project           = var.project
  location_short    = var.location_short
  subscription_id   = data.azurerm_client_config.current.subscription_id
  allowed_locations = [var.location, "northeurope", "global"]

  tags = {
    environment = "lz-dev"
    project     = var.project
    owner       = var.owner
  }
}

module "policy_auto_lock" {
  source = "../../modules/policy/auto_lock"

  project         = var.project
  owner           = var.owner
  location        = var.location
  subscription_id = data.azurerm_client_config.current.subscription_id
}
