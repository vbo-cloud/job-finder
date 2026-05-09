output "id" {
  description = "The resource ID of the subnet"
  value       = azurerm_subnet.this.id
}

output "name" {
  description = "The name of the subnet"
  value       = azurerm_subnet.this.name
}
