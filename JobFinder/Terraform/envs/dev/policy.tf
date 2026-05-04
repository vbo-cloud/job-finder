# Policy is assigned at subscription level so it covers all resources in the dev environment,
# including those not managed by Terraform (e.g., manually created test resources).
module "policy_allowed_locations" {
  source = "../../modules/policy"

  environment       = "dev"
  project           = var.project
  location_short    = var.location_short
  # global is required for Microsoft.Network/privateDnsZones (Azure registers them as location "global").
  allowed_locations = [var.location, "northeurope", "global"]

  tags = {
    environment = "dev"
    project     = var.project
    owner       = var.owner
  }
}
