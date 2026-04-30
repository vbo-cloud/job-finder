# Expose name and ID so dependent modules can reference this resource group
# without duplicating the name string, which avoids drift if the name changes.

output "name" {
  value = azurerm_resource_group.rg.name
}

output "id" {
  value = azurerm_resource_group.rg.id
}
