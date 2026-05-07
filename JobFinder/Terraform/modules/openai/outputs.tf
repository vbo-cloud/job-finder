output "id" { value = azurerm_cognitive_account.this.id }
output "endpoint" { value = azurerm_cognitive_account.this.endpoint }
output "primary_key" {
  value     = azurerm_cognitive_account.this.primary_access_key
  sensitive = true
}
