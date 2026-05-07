# State address migrations — tells Terraform to rename existing state entries
# instead of destroying and recreating resources.
# Safe to delete after the first successful apply that picks up these moves.

moved {
  from = azurerm_subnet.postgresql
  to   = module.subnet_postgresql.azurerm_subnet.this
}

moved {
  from = azurerm_resource_group.rg_core
  to   = module.rg_core.azurerm_resource_group.rg
}

moved {
  from = azurerm_resource_group.rg_app
  to   = module.rg_app.azurerm_resource_group.rg
}

moved {
  from = azurerm_resource_group.rg_data
  to   = module.rg_data.azurerm_resource_group.rg
}
