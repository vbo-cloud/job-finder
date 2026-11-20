output "id" {
  description = "Resource ID of the Azure OpenAI cognitive account."
  value       = azurerm_cognitive_account.this.id
}

output "endpoint" {
  description = "Custom-subdomain endpoint of the Azure OpenAI account, required for AD token auth. Built from custom_subdomain_name rather than read from azurerm_cognitive_account.this.endpoint: both resolve to the same value (confirmed live via `az cognitiveservices account show`), but the PR #244 apply cached the pre-propagation value in Terraform state, and nothing pushed to dev since has re-triggered a plan/apply to pick up the drift. Building it from an input we already control makes the value known at plan time instead of depending on a possibly-stale computed read."
  value       = "https://${var.name}.openai.azure.com/"
}

output "primary_key" {
  description = "Primary access key of the Azure OpenAI cognitive account."
  value       = azurerm_cognitive_account.this.primary_access_key
  sensitive   = true
}
