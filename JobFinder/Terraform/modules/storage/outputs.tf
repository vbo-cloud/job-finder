output "id" {
  description = "The resource ID of the storage account"
  value       = azurerm_storage_account.this.id
}

output "name" {
  description = "The name of the storage account"
  value       = azurerm_storage_account.this.name
}

output "primary_blob_endpoint" {
  description = "The primary blob service endpoint URL"
  value       = azurerm_storage_account.this.primary_blob_endpoint
}
