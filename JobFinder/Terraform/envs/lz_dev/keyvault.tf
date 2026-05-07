# Standard SKU is sufficient for dev; Premium (HSM-backed) is reserved for prod secrets.
module "keyvault" {
  source                     = "../../modules/keyvault"
  name                       = "kv-${var.project}-lz-dev-${var.location_short}"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  soft_delete_retention_days = 90
  environment                = var.env
  project                    = var.project
  owner                      = var.owner
}
