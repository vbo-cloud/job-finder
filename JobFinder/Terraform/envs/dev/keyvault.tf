module "keyvault" {
  source              = "../../modules/keyvault"
  name                = "kv-${var.project}-dev-${var.location_short}"
  location            = var.location
  resource_group_name = azurerm_resource_group.rg_core.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  environment         = "dev"
  project             = var.project
  owner               = var.owner
}
