output "id" {
  description = "Resource ID of the Container App Environment."
  value       = azurerm_container_app_environment.this.id
}

output "name" {
  description = "Name of the Container App Environment."
  value       = azurerm_container_app_environment.this.name
}

output "custom_domain_verification_id" {
  description = "Verification ID used as the value of the asuid.<subdomain> TXT record to prove ownership before binding a custom domain to a Container App in this environment."
  value       = azurerm_container_app_environment.this.custom_domain_verification_id
}
