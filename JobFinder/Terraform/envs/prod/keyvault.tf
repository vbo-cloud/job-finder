module "keyvault" {
  source              = "../../modules/keyvault"
  name                = "kv-${var.project}-prod-${var.location_short}"
  location            = var.location
  resource_group_name = azurerm_resource_group.rg_core.name
  environment         = "prod"
  project             = var.project
  owner               = var.owner
}
