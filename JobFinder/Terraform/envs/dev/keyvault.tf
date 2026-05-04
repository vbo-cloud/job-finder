module "keyvault" {
  source              = "../../modules/keyvault"
  name                = "kv-${var.project}-dev-${var.location_short}"
  location            = var.location
  resource_group_name = azurerm_resource_group.rg_core.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  environment         = "dev"
  project             = var.project
  owner               = var.owner
}

# Grant the Terraform service principal write access to secrets so it can store
# connection strings and other secrets without requiring a separate manual RBAC step.
resource "azurerm_role_assignment" "terraform_secrets_officer" {
  scope                = module.keyvault.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}
