# State address migration — safe to delete after first successful apply.

moved {
  from = azurerm_subnet.postgresql
  to   = module.subnet_postgresql.azurerm_subnet.this
}
