# Policy is assigned at subscription level from lz_dev — no need to repeat it in the app layer (dev/).
# northeurope is allowed as a secondary region for disaster recovery scenarios.
# global is required for Microsoft.Network/privateDnsZones, which Azure registers as location "global".
module "policy_allowed_locations" {
  source = "../../modules/policy"

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
