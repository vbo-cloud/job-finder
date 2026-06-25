output "id" {
  description = "Resource ID of the Key Vault secret"
  value       = azurerm_key_vault_secret.this.id
}

output "secret_name" {
  description = "Name of the Key Vault secret"
  value       = azurerm_key_vault_secret.this.name
}

output "version" {
  description = "Current version of the Key Vault secret"
  value       = azurerm_key_vault_secret.this.version
}

output "value" {
  description = "Plaintext value of the Key Vault secret"
  value       = azurerm_key_vault_secret.this.value
  sensitive   = true
}
