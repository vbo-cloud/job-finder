output "instrumentation_key" {
  description = "Instrumentation key of the Application Insights resource."
  value       = azurerm_application_insights.this.instrumentation_key
  sensitive   = true
}

output "connection_string" {
  description = "Connection string of the Application Insights resource."
  value       = azurerm_application_insights.this.connection_string
  sensitive   = true
}

output "app_id" {
  description = "App ID of the Application Insights resource."
  value       = azurerm_application_insights.this.app_id
}
