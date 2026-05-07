output "id" {
  description = "Resource ID of the Azure OpenAI cognitive account."
  value       = azurerm_cognitive_account.this.id
}

output "endpoint" {
  description = "Endpoint URL of the Azure OpenAI cognitive account."
  value       = azurerm_cognitive_account.this.endpoint
}

output "primary_key" {
  description = "Primary access key of the Azure OpenAI cognitive account."
  value       = azurerm_cognitive_account.this.primary_access_key
  sensitive   = true
}
