# Policy assigned at subscription level from lz_prod — enforces location restrictions for the prod environment.
# northeurope is allowed as a secondary region for disaster recovery scenarios.
# global is required for Microsoft.Network/privateDnsZones, which Azure registers as location "global".
module "policy_allowed_locations" {
  source = "../../modules/policy"

  environment       = "lz-prod"
  project           = var.project
  location_short    = var.location_short
  allowed_locations = [var.location, "northeurope", "global"]

  tags = {
    environment = "lz-prod"
    project     = var.project
    owner       = var.owner
  }
}
