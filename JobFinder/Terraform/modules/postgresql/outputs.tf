output "server_id" {
  description = "Resource ID of the PostgreSQL Flexible Server"
  value       = azurerm_postgresql_flexible_server.this.id
}

output "server_fqdn" {
  description = "FQDN of the PostgreSQL Flexible Server"
  value       = azurerm_postgresql_flexible_server.this.fqdn
}

output "database_name" {
  description = "Name of the jobfinder database"
  value       = azurerm_postgresql_flexible_server_database.jobfinder.name
}

output "connection_string_secret_id" {
  description = "Resource ID of the Key Vault secret storing the connection string"
  value       = azurerm_key_vault_secret.connection_string.id
}
