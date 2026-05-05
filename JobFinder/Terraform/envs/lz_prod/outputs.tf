output "rg_name" {
  value = azurerm_resource_group.rg.name
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
