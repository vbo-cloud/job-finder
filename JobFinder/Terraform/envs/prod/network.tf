# Application-layer network prerequisites for prod.
# The VNet is read from lz_prod via a data source; all app-specific subnets,
# DNS zones, and VNet links are managed here. Mirror of envs/dev/network.tf.
#
# Sections:
#   - PostgreSQL Flexible Server (delegated subnet, private DNS zone, VNet link)

data "azurerm_virtual_network" "lz_vnet" {
  name                = "vnet-${var.project}-lz-prod-${var.location_short}"
  resource_group_name = "rg-${var.project}-lz-prod-${var.location_short}"
}

# ==============================================================================
# PostgreSQL Flexible Server
# ==============================================================================

module "subnet_postgresql" {
  source               = "../../modules/subnet"
  name                 = "snet-${var.project}-postgresql-prod-${var.location_short}"
  resource_group_name  = "rg-${var.project}-lz-prod-${var.location_short}"
  virtual_network_name = data.azurerm_virtual_network.lz_vnet.name
  address_prefixes     = ["10.1.3.0/24"]
  delegation_name      = "postgresql-delegation"
  delegation_service   = "Microsoft.DBforPostgreSQL/flexibleServers"
  delegation_actions   = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
}

# The subnet above lives in the lz_prod RG because it is attached to the LZ VNet —
# Azure requires subnet and VNet to share the same resource group.
# The DNS zone and VNet link live in rg_core (app layer) because they are
# app-specific concerns. This split is intentional.
resource "azurerm_private_dns_zone" "postgresql" {
  name                = "privatelink.postgres.database.azure.com"
  resource_group_name = azurerm_resource_group.rg_core.name

  tags = {
    environment = var.env
    project     = var.project
    owner       = var.owner
  }
}

resource "azurerm_private_dns_zone_virtual_network_link" "postgresql" {
  name                  = "pdns-link-${var.project}-lz-prod-${var.location_short}-postgresql"
  resource_group_name   = azurerm_resource_group.rg_core.name
  private_dns_zone_name = azurerm_private_dns_zone.postgresql.name
  virtual_network_id    = data.azurerm_virtual_network.lz_vnet.id

  tags = {
    environment = var.env
    project     = var.project
    owner       = var.owner
  }
}
