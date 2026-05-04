output "rg_name" {
  value = azurerm_resource_group.rg.name
}

output "vnet_id" {
  value = azurerm_virtual_network.vnet.id
}

output "vnet_name" {
  value = azurerm_virtual_network.vnet.name
}

output "subnet_app_id" {
  value = azurerm_subnet.app.id
}

output "keyvault_uri" {
  value = azurerm_key_vault.kv.vault_uri
}
