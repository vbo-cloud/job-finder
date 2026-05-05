# State address migrations — tells Terraform to rename existing state entries
# instead of destroying and recreating resources.
# Safe to delete after the first successful apply that picks up these moves.

moved {
  from = azurerm_virtual_network.vnet
  to   = module.vnet.azurerm_virtual_network.this
}

moved {
  from = azurerm_subnet.app
  to   = module.subnet_app.azurerm_subnet.this
}

moved {
  from = azurerm_key_vault.kv
  to   = module.keyvault.azurerm_key_vault.this
}
