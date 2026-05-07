output "id" {
  value = azurerm_servicebus_namespace.this.id
}

output "name" {
  value = azurerm_servicebus_namespace.this.name
}

output "primary_connection_string" {
  value     = azurerm_servicebus_namespace.this.default_primary_connection_string
  sensitive = true
}
