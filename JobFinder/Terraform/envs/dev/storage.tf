# Blob storage for CV and job offer files, isolated behind a private endpoint.
# subnet_id comes from data.azurerm_subnet.lz_vnet_app defined in network.tf.

# ==============================================================================
# Private DNS — Blob Storage
# ==============================================================================

resource "azurerm_private_dns_zone" "blob" {
  name                = "privatelink.blob.core.windows.net"
  resource_group_name = azurerm_resource_group.rg_core.name

  tags = {
    environment = "dev"
    project     = var.project
    owner       = var.owner
  }
}

resource "azurerm_private_dns_zone_virtual_network_link" "blob" {
  name                  = "pdns-link-${var.project}-lz-dev-${var.location_short}-blob"
  resource_group_name   = azurerm_resource_group.rg_core.name
  private_dns_zone_name = azurerm_private_dns_zone.blob.name
  virtual_network_id    = data.azurerm_virtual_network.lz_vnet.id

  tags = {
    environment = "dev"
    project     = var.project
    owner       = var.owner
  }
}

# ==============================================================================
# Storage Account
# ==============================================================================

module "storage" {
  source = "../../modules/storage"
  # Storage accounts omit hyphens, max 24 chars: st{project}{env}{region}
  name                = "st${var.project}dev${var.location_short}"
  location            = var.location
  resource_group_name = azurerm_resource_group.rg_data.name
  environment         = "dev"
  project             = var.project
  owner               = var.owner
}

# ==============================================================================
# Management Lock
# ==============================================================================

resource "azurerm_management_lock" "storage" {
  name       = "lock-st${var.project}dev${var.location_short}"
  scope      = module.storage.id
  lock_level = "CanNotDelete"
  notes      = "Protects blob storage from accidental deletion. Remove manually before destroying."
}

# ==============================================================================
# Containers
# ==============================================================================

resource "azurerm_storage_container" "cvs" {
  name                  = "cvs"
  storage_account_name  = module.storage.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "offers" {
  name                  = "offers"
  storage_account_name  = module.storage.name
  container_access_type = "private"
}

# ==============================================================================
# Private Endpoint
# ==============================================================================

module "private_endpoint_blob" {
  source                         = "../../modules/private_endpoint"
  name                           = "pe-${module.storage.name}-blob"
  location                       = var.location
  resource_group_name            = azurerm_resource_group.rg_data.name
  subnet_id                      = data.azurerm_subnet.lz_vnet_app.id
  private_connection_resource_id = module.storage.id
  subresource_name               = "blob"
  private_dns_zone_ids           = [azurerm_private_dns_zone.blob.id]
  environment                    = "dev"
  project                        = var.project
  owner                          = var.owner
}
