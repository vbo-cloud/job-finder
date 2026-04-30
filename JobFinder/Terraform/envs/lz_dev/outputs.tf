# Expose lz_dev identifiers so app environments can reference shared resources
# without hardcoding names — avoids drift if naming conventions change.
# keyvault_uri is consumed by the app layer to retrieve secrets at deploy time.

output "rg_name" {
  value = azurerm_resource_group.rg.name
}

output "vnet_id" {
  value = azurerm_virtual_network.vnet.id
}

output "subnet_app_id" {
  value = azurerm_subnet.app.id
}

output "keyvault_uri" {
  value = azurerm_key_vault.kv.vault_uri
}