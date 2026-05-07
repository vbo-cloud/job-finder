# ==============================================================================
# Key Vault Secret
# ==============================================================================
resource "azurerm_key_vault_secret" "this" {
  name         = var.name
  value        = var.value
  key_vault_id = var.key_vault_id
  content_type = var.content_type

  tags = {
    environment = var.environment
    project     = var.project
    owner       = var.owner
  }
}
