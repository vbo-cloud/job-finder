output "id" {
  description = "Resource ID of the Service Bus namespace"
  value       = azurerm_servicebus_namespace.this.id
}

output "name" {
  description = "Name of the Service Bus namespace"
  value       = azurerm_servicebus_namespace.this.name
}

output "primary_connection_string" {
  description = "Primary connection string of the Service Bus namespace (sensitive)"
  value       = azurerm_servicebus_namespace.this.default_primary_connection_string
  sensitive   = true
}
