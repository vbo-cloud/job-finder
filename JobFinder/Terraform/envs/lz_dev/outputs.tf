# Expose lz_dev identifiers so app environments can reference shared resources
# without hardcoding names — avoids drift if naming conventions change.
# keyvault_uri is consumed by the app layer to retrieve secrets at deploy time.

output "rg_name" {
  value = module.rg.name
}

output "vnet_id" {
  value = module.vnet.id
}

output "vnet_name" {
  value = module.vnet.name
}

output "subnet_app_id" {
  value = module.subnet_app.id
}

output "keyvault_uri" {
  value = module.keyvault.uri
}

output "caj_identity_id" {
  description = "Resource ID of the Container App Jobs User Assigned Managed Identity."
  value       = azurerm_user_assigned_identity.caj.id
}

output "caj_identity_principal_id" {
  description = "Principal ID of the Container App Jobs User Assigned Managed Identity."
  value       = azurerm_user_assigned_identity.caj.principal_id
}
