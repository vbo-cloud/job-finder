# Expose name and ID so dependent modules can reference this resource group
# without duplicating the name string, which avoids drift if the name changes.

output "name" {
  description = "The name of the resource group"
  value       = azurerm_resource_group.rg.name
}

output "id" {
  description = "The resource ID of the resource group"
  value       = azurerm_resource_group.rg.id
}

output "location" {
  description = "The Azure region of the resource group"
  value       = azurerm_resource_group.rg.location
}
