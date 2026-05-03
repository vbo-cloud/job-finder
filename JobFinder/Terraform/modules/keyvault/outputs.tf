output "id" {
  description = "The resource ID of the Key Vault"
  value       = azurerm_key_vault.this.id
}

output "uri" {
  description = "The URI of the Key Vault for secret access"
  value       = azurerm_key_vault.this.vault_uri
}
