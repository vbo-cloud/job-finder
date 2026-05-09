# ==============================================================================
# Resource Groups — App layer (dev)
# ==============================================================================
# Provisioned here by sp-jf-platform so sp-jf-github never needs subscription-
# scoped write permissions — its Contributor role is restricted to these three
# resource groups instead of the full subscription.

module "rg_core" {
  source      = "../../modules/resource_group"
  name        = "rg-${var.project}-dev-${var.location_short}-core"
  location    = var.location
  environment = "dev"
  project     = var.project
  owner       = var.owner
}

module "rg_app" {
  source      = "../../modules/resource_group"
  name        = "rg-${var.project}-dev-${var.location_short}-app"
  location    = var.location
  environment = "dev"
  project     = var.project
  owner       = var.owner
}

module "rg_data" {
  source      = "../../modules/resource_group"
  name        = "rg-${var.project}-dev-${var.location_short}-data"
  location    = var.location
  environment = "dev"
  project     = var.project
  owner       = var.owner
}

# Import the existing resource groups from dev.tfstate into lz_dev.tfstate.
# These were originally provisioned by envs/dev/ — ownership transferred here.
# Import blocks are idempotent: no-op once the resource is already in state.
import {
  to = module.rg_core.azurerm_resource_group.rg
  id = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/resourceGroups/rg-${var.project}-dev-${var.location_short}-core"
}

import {
  to = module.rg_app.azurerm_resource_group.rg
  id = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/resourceGroups/rg-${var.project}-dev-${var.location_short}-app"
}

import {
  to = module.rg_data.azurerm_resource_group.rg
  id = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/resourceGroups/rg-${var.project}-dev-${var.location_short}-data"
}
