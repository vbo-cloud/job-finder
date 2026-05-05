# State address migrations — tells Terraform to rename existing state entries
# instead of destroying and recreating resources.
# Safe to delete after the first successful apply that picks up these moves.

moved {
  from = azurerm_subnet.postgresql
  to   = module.subnet_postgresql.azurerm_subnet.this
}
