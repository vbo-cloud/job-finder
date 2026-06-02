# ==============================================================================
# Web App — FastAPI
# ==============================================================================

data "azurerm_key_vault_secret" "entra_tenant_id" {
  name         = "entra-external-tenant-id"
  key_vault_id = module.keyvault.id
}

data "azurerm_key_vault_secret" "entra_client_id" {
  name         = "entra-external-client-id"
  key_vault_id = module.keyvault.id
}

data "azurerm_key_vault_secret" "entra_client_secret" {
  name         = "entra-external-client-secret"
  key_vault_id = module.keyvault.id
}

module "webapp" {
  source = "../../modules/container_app"

  name                = "app-${var.project}-${var.env}-${var.location_short}"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.rg_app.name
  environment_id      = module.container_app_environment.id
  image               = "${module.container_registry.login_server}/agents/webapp:latest"
  cpu                 = 0.5
  memory              = "1Gi"
  min_replicas        = 0
  max_replicas        = 1
  identity_ids        = [data.azurerm_user_assigned_identity.caj.id]
  registry_server     = module.container_registry.login_server
  registry_identity   = data.azurerm_user_assigned_identity.caj.id
  environment         = var.env
  project             = var.project
  owner               = var.owner

  secrets = [
    {
      name  = "postgresql-connection-string"
      value = module.postgresql.connection_string
    },
    {
      name  = "openai-api-key"
      value = module.openai.primary_key
    },
    {
      name  = "entra-external-client-secret"
      value = data.azurerm_key_vault_secret.entra_client_secret.value
    },
  ]

  env_vars = [
    { name = "DATABASE_URL",
    secret_name = "postgresql-connection-string" },
    { name = "AZURE_OPENAI_API_KEY",
    secret_name = "openai-api-key" },
    { name = "AZURE_OPENAI_ENDPOINT",
    value = module.openai.endpoint },
    { name = "AZURE_SERVICEBUS_FULLY_QUALIFIED_NAMESPACE",
    value = "${module.servicebus.name}.servicebus.windows.net" },
    { name = "AZURE_CLIENT_ID",
    value = data.azurerm_user_assigned_identity.caj.client_id },
    { name = "AZURE_STORAGE_ACCOUNT_URL",
    value = module.storage.primary_blob_endpoint },
    { name = "ENTRA_EXTERNAL_TENANT_ID",
    value = data.azurerm_key_vault_secret.entra_tenant_id.value },
    { name = "ENTRA_EXTERNAL_CLIENT_ID",
    value = data.azurerm_key_vault_secret.entra_client_id.value },
    { name = "ENTRA_EXTERNAL_CLIENT_SECRET",
    secret_name = "entra-external-client-secret" },
  ]
}
