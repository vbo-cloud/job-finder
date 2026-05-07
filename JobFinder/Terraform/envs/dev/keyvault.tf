module "keyvault" {
  source              = "../../modules/keyvault"
  name                = "kv-${var.project}-dev-${var.location_short}"
  location            = var.location
  resource_group_name = module.rg_core.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  environment         = var.env
  project             = var.project
  owner               = var.owner
}
