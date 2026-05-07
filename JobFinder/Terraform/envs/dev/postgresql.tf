# The subnet lives in the lz_dev RG because it is attached to the LZ VNet —
# Azure requires subnet and VNet to share the same resource group.
# The DNS zone and VNet link live in rg_core (app layer) because they are
# app-specific concerns. This split is intentional.
resource "azurerm_private_dns_zone" "postgresql" {
  name                = "privatelink.postgres.database.azure.com"
  resource_group_name = module.rg_core.name

  tags = {
    environment = var.env
    project     = var.project
    owner       = var.owner
  }
}

resource "azurerm_private_dns_zone_virtual_network_link" "postgresql" {
  name                  = "pdns-link-${var.project}-lz-dev-${var.location_short}-postgresql"
  resource_group_name   = module.rg_core.name
  private_dns_zone_name = azurerm_private_dns_zone.postgresql.name
  virtual_network_id    = data.azurerm_virtual_network.lz_vnet.id

  tags = {
    environment = var.env
    project     = var.project
    owner       = var.owner
  }
}

module "postgresql" {
  source              = "../../modules/postgresql"
  name                = "psql-${var.project}-dev-${var.location_short}"
  location            = var.location
  resource_group_name = module.rg_data.name
  environment         = var.env
  project             = var.project
  owner               = var.owner
  key_vault_id        = module.keyvault.id
  delegated_subnet_id = module.subnet_postgresql.id
  private_dns_zone_id = azurerm_private_dns_zone.postgresql.id
}
