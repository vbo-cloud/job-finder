# VNet lives in the landing zone (hub) so app environments peer to it rather than owning their own.
# 10.0.0.0/16 is reserved for lz_dev; lz_prod uses 10.1.0.0/16 to avoid overlap for future VNet peering.
module "vnet" {
  source              = "../../modules/vnet"
  name                = "vnet-${var.project}-lz-dev-${var.location_short}"
  location            = module.rg.location
  resource_group_name = module.rg.name
  address_space       = ["10.0.0.0/16"]
  environment         = var.env
  project             = var.project
  owner               = var.owner
}

# Single subnet for now; split into app/data/mgmt subnets when NSGs or route tables are required.
module "subnet_app" {
  source               = "../../modules/subnet"
  name                 = "snet-${var.project}-lz-dev-${var.location_short}-app"
  resource_group_name  = module.rg.name
  virtual_network_name = module.vnet.name
  address_prefixes     = ["10.0.1.0/24"]
}

# Dedicated subnet for the Container App Environment.
# /23 is the minimum size required by Azure for VNet-injected CAEs.
# Delegation to Microsoft.App/environments is mandatory.
module "subnet_cae" {
  source               = "../../modules/subnet"
  name                 = "snet-${var.project}-lz-dev-${var.location_short}-cae"
  resource_group_name  = module.rg.name
  virtual_network_name = module.vnet.name
  address_prefixes     = ["10.0.2.0/23"]
  delegation_name      = "cae-delegation"
  delegation_service   = "Microsoft.App/environments"
  delegation_actions   = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
}
