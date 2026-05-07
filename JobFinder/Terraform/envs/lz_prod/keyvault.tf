# Upgrade to Premium SKU when prod requires HSM-backed secrets or private endpoints.
module "keyvault" {
  source                     = "../../modules/keyvault"
  name                       = "kv-${var.project}-lz-prod-${var.location_short}"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  soft_delete_retention_days = 90
  environment                = var.env
  project                    = var.project
  owner                      = var.owner
}
