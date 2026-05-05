# VNet lives in the landing zone (hub) — prod uses 10.1.0.0/16, non-overlapping with lz_dev (10.0.0.0/16)
# so both can be peered without address conflicts in a future hub-and-spoke topology.
module "vnet" {
  source              = "../../modules/vnet"
  name                = "vnet-${var.project}-lz-prod-${var.location_short}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  address_space       = ["10.1.0.0/16"]
  environment         = "lz-prod"
  project             = var.project
  owner               = var.owner
}

module "subnet_app" {
  source               = "../../modules/subnet"
  name                 = "snet-${var.project}-lz-prod-${var.location_short}-app"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = module.vnet.name
  address_prefixes     = ["10.1.1.0/24"]
}
