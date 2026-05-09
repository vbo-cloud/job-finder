output "id" {
  description = "The resource ID of the private endpoint"
  value       = azurerm_private_endpoint.this.id
}

output "private_ip_address" {
  description = "The private IP address allocated to the endpoint NIC"
  value       = azurerm_private_endpoint.this.private_service_connection[0].private_ip_address
}
