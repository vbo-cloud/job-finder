output "id" {
  description = "Resource ID of the Container App."
  value       = azurerm_container_app.this.id
}

output "fqdn" {
  description = "Fully qualified domain name of the Container App."
  value       = azurerm_container_app.this.latest_revision_fqdn
}
