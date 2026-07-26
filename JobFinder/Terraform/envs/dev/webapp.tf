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
  resource_group_name = data.azurerm_resource_group.rg_app.name
  environment_id      = module.container_app_environment.id
  image               = "${module.container_registry.login_server}/agents/webapp:latest"
  cpu                 = 0.5
  memory              = "1Gi"
  # min_replicas = 1 trades scale-to-zero for no cold start; accepted idle-rate
  # cost is ~$0.000008/vCPU-s + $0.000001/GiB-s (see docs/JOURNAL.md, PR #210).
  min_replicas      = 1
  max_replicas      = 1
  identity_ids      = [data.azurerm_user_assigned_identity.caj.id]
  registry_server   = module.container_registry.login_server
  registry_identity = data.azurerm_user_assigned_identity.caj.id
  environment       = var.env
  project           = var.project
  owner             = var.owner

  secrets = [
    {
      name  = "postgresql-connection-string"
      value = module.postgresql.connection_string
    },
    {
      name  = "entra-external-client-secret"
      value = data.azurerm_key_vault_secret.entra_client_secret.value
    },
    {
      name  = "notifications-unsubscribe-secret"
      value = local.notifications_unsubscribe_secret
    },
  ]

  env_vars = [
    {
      name        = "DATABASE_URL"
      secret_name = "postgresql-connection-string"
    },
    {
      name  = "AZURE_OPENAI_ENDPOINT"
      value = module.openai.endpoint
    },
    {
      name  = "AZURE_SERVICEBUS_FULLY_QUALIFIED_NAMESPACE"
      value = "${module.servicebus.name}.servicebus.windows.net"
    },
    {
      name  = "AZURE_CLIENT_ID"
      value = data.azurerm_user_assigned_identity.caj.client_id
    },
    {
      name  = "AZURE_STORAGE_ACCOUNT_URL"
      value = module.storage.primary_blob_endpoint
    },
    # Tenant ID and client ID are semi-public (visible in OAuth2 flows).
    # Promoting them to secrets adds complexity without meaningful security gain.
    # The client secret is already secret-backed; this split is intentional.
    {
      name  = "ENTRA_EXTERNAL_TENANT_ID"
      value = data.azurerm_key_vault_secret.entra_tenant_id.value
    },
    {
      name  = "ENTRA_EXTERNAL_CLIENT_ID"
      value = data.azurerm_key_vault_secret.entra_client_id.value
    },
    {
      name        = "ENTRA_EXTERNAL_CLIENT_SECRET"
      secret_name = "entra-external-client-secret"
    },
    {
      name        = "NOTIFICATIONS_UNSUBSCRIBE_SECRET"
      secret_name = "notifications-unsubscribe-secret"
    },
    # Frontend origins allowed to call the API cross-origin. var.frontend_custom_domain is
    # the single source of truth shared with the future custom domain binding (PR 2).
    {
      name  = "CORS_ALLOWED_ORIGINS"
      value = "http://localhost:3000,https://${var.frontend_custom_domain}"
    },
    # Entra user IDs (JWT sub) granted in-app admin features. Opaque GUIDs,
    # not credentials — authorization still requires a valid signed JWT for
    # that sub, so a plain env var (not a secret) is intentional.
    {
      name  = "ADMIN_USER_IDS"
      value = var.admin_user_ids
    },
    # Anonymous-auth Azure Function URL (portfolio repo) — semi-public by
    # design, not a secret. Left empty until Vincent provisions the value
    # (see docs/JOURNAL.md); POST /feedback degrades to a 502 until then.
    {
      name  = "PORTFOLIO_CONTACT_FUNCTION_URL"
      value = var.portfolio_contact_function_url
    },
  ]
}
