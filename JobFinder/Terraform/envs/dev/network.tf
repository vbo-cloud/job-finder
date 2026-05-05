# LZ data sources and shared subnet configuration for dev.
# Private DNS zones and VNet links live in their respective service files
# (postgresql.tf, storage.tf) — one file per service.
#
# Sections:
#   - LZ data sources (VNet, subnet app)
#   - PostgreSQL Flexible Server (delegated subnet)

data "azurerm_virtual_network" "lz_vnet" {
  name                = "vnet-${var.project}-lz-dev-${var.location_short}"
  resource_group_name = "rg-${var.project}-lz-dev-${var.location_short}"
}

data "azurerm_subnet" "lz_vnet_app" {
  name                 = "snet-${var.project}-lz-dev-${var.location_short}-app"
  virtual_network_name = data.azurerm_virtual_network.lz_vnet.name
  resource_group_name  = "rg-${var.project}-lz-dev-${var.location_short}"
}

# ==============================================================================
# PostgreSQL Flexible Server
# ==============================================================================

# Dedicated subnet with delegation — PostgreSQL Flexible Server in VNet injection mode
# requires an exclusive delegated subnet (no other resource types allowed in it).
module "subnet_postgresql" {
  source               = "../../modules/subnet"
  name                 = "snet-${var.project}-postgresql-dev-${var.location_short}"
  resource_group_name  = "rg-${var.project}-lz-dev-${var.location_short}"
  virtual_network_name = data.azurerm_virtual_network.lz_vnet.name
  address_prefixes     = ["10.0.3.0/24"]
  delegation_name      = "postgresql-delegation"
  delegation_service   = "Microsoft.DBforPostgreSQL/flexibleServers"
  delegation_actions   = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
}
