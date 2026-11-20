# Blob storage for CV and job offer files.
# Reached over its public endpoint, protected by RBAC (managed identity) and private containers.
# The blob private endpoint (+ privatelink.blob DNS zone) was removed to save ~6.7 EUR/month: the
# account stays publicly reachable (public_network_access_enabled = true, see modules/storage and
# BACKLOG "Self-hosted runner dans le VNet"), so the endpoint enforced no isolation. Re-add it
# together with public_network_access_enabled = false once a self-hosted runner in the VNet exists.

# ==============================================================================
# Storage Account
# ==============================================================================

module "storage" {
  source = "../../modules/storage"
  # Storage accounts omit hyphens, max 24 chars: st{project}{env}{region}
  name                = "st${var.project}dev${var.location_short}"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.rg_data.name
  environment         = var.env
  project             = var.project
  owner               = var.owner
}

# ==============================================================================
# Containers
# ==============================================================================

resource "azurerm_storage_container" "cvs" {
  name                  = "cvs"
  storage_account_id    = module.storage.id
  container_access_type = "private"
}

resource "azurerm_storage_container" "offers" {
  name                  = "offers"
  storage_account_id    = module.storage.id
  container_access_type = "private"
}
