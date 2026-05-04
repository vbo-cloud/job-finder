module "postgresql" {
  source                       = "../../modules/postgresql"
  name                         = "psql-${var.project}-prod-${var.location_short}"
  location                     = var.location
  resource_group_name          = azurerm_resource_group.rg_data.name
  environment                  = "prod"
  project                      = var.project
  owner                        = var.owner
  key_vault_id                 = module.keyvault.id
  delegated_subnet_id          = azurerm_subnet.postgresql.id
  private_dns_zone_id          = azurerm_private_dns_zone.postgresql.id
  backup_retention_days        = 35
  geo_redundant_backup_enabled = true
}
