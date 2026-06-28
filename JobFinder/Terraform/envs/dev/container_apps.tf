# ==============================================================================
# Container Apps Environment
# ==============================================================================
# Shared environment for all agent jobs.
# Each agent is a separate Container App Job — same environment, independent
# scaling, trigger, and lifecycle.
# Naming: job names use {type}-{project}-{env}-{region}-{suffix} pattern.
# Container App Job names are capped at 32 characters — the suffix is kept short accordingly.
# Force-recreated 2026-06-28: CAE, webapp, and all jobs deleted manually to reset
# the stuck KEDA azure-servicebus controller. Terraform recreates from this config.

module "container_app_environment" {
  source = "../../modules/container_app_environment"

  name                       = "cae-${var.project}-${var.env}-${var.location_short}"
  location                   = var.location
  resource_group_name        = data.azurerm_resource_group.rg_app.name
  log_analytics_workspace_id = module.application_insights.workspace_id
  infrastructure_subnet_id   = data.azurerm_subnet.lz_vnet_cae.id
  environment                = var.env
  project                    = var.project
  owner                      = var.owner
  additional_tags            = { keda_controller_reset = "2026-06-28" }
}

# ==============================================================================
# Agent Jobs
# ==============================================================================
# Agent 1 — Matching (queue: offer-ready)
# Agent 2 — Cleanup (timer: 02:00 UTC)
# Agent 3 — Offer Fetching (timer: 12:00 and 20:00 UTC)
# Agent 4 — CV Analysis (queue: cv-analysis)

data "azurerm_key_vault_secret" "ft_client_id" {
  name         = "ft-client-id"
  key_vault_id = module.keyvault.id
}

data "azurerm_key_vault_secret" "ft_client_secret" {
  name         = "ft-client-secret"
  key_vault_id = module.keyvault.id
}

locals {
  postgresql_connection_string = module.postgresql.connection_string
  openai_api_key               = module.openai.primary_key
  openai_endpoint              = module.openai.endpoint
  ft_client_id                 = data.azurerm_key_vault_secret.ft_client_id.value
  ft_client_secret             = data.azurerm_key_vault_secret.ft_client_secret.value
}

# ==============================================================================
# Managed Identity — Container App Jobs
# ==============================================================================
# UAMI and AcrPull role assignment are managed by lz_dev (sp-jf-platform).
# sp-jf-github (Contributor only) cannot create role assignments.

data "azurerm_user_assigned_identity" "caj" {
  name                = "id-${var.project}-${var.env}-${var.location_short}-caj"
  resource_group_name = data.azurerm_resource_group.rg_core.name
}

# Agent 1 — Matching (queue: offer-ready)
module "job_matching" {
  source = "../../modules/container_app_job"

  name                 = "job-jf-dev-frc-matching"
  location             = var.location
  resource_group_name  = data.azurerm_resource_group.rg_app.name
  environment_id       = module.container_app_environment.id
  trigger_type         = "queue"
  queue_name           = "offer-ready"
  servicebus_namespace = module.servicebus.name
  image                = "${module.container_registry.login_server}/agents/matching:latest"
  environment          = var.env
  project              = var.project
  owner                = var.owner
  identity_ids         = [data.azurerm_user_assigned_identity.caj.id]
  registry_server      = module.container_registry.login_server
  registry_identity    = data.azurerm_user_assigned_identity.caj.id
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
      name  = "openai-endpoint"
      value = module.openai.endpoint
    },
    {
      name  = "appinsights-connection-string"
      value = module.application_insights.connection_string
    },
    {
      name  = "servicebus-connection-string"
      value = module.servicebus.primary_connection_string
    },
  ]
  env_vars = [
    {
      name        = "DATABASE_URL"
      secret_name = "postgresql-connection-string"
    },
    {
      name        = "AZURE_OPENAI_API_KEY"
      secret_name = "openai-api-key"
    },
    {
      name        = "AZURE_OPENAI_ENDPOINT"
      secret_name = "openai-endpoint"
    },
    {
      name  = "MATCHING_SCORE_THRESHOLD"
      value = "0.8"
    },
    {
      name  = "AZURE_SERVICEBUS_FULLY_QUALIFIED_NAMESPACE"
      value = "${module.servicebus.name}.servicebus.windows.net"
    },
    # Used by DefaultAzureCredential (bus.py) to select the right UAMI,
    # and by KEDA (uami_client_id) to authenticate the Service Bus scaler.
    {
      name  = "AZURE_CLIENT_ID"
      value = data.azurerm_user_assigned_identity.caj.client_id
    },
    {
      name        = "APPLICATIONINSIGHTS_CONNECTION_STRING"
      secret_name = "appinsights-connection-string"
    },
  ]
}

# Agent 4 — Cleanup (timer: once daily at 02:00 UTC)
module "job_cleanup" {
  source = "../../modules/container_app_job"

  name                = "job-jf-dev-frc-cleanup"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.rg_app.name
  environment_id      = module.container_app_environment.id
  trigger_type        = "timer"
  cron_expression     = "0 2 * * *"
  image               = "${module.container_registry.login_server}/agents/cleanup:latest"
  environment         = var.env
  project             = var.project
  owner               = var.owner
  identity_ids        = [data.azurerm_user_assigned_identity.caj.id]
  registry_server     = module.container_registry.login_server
  registry_identity   = data.azurerm_user_assigned_identity.caj.id
  secrets = [
    {
      name  = "postgresql-connection-string"
      value = module.postgresql.connection_string
    },
    {
      name  = "appinsights-connection-string"
      value = module.application_insights.connection_string
    },
  ]
  env_vars = [
    {
      name        = "DATABASE_URL"
      secret_name = "postgresql-connection-string"
    },
    {
      name  = "CLEANUP_OFFER_MAX_AGE_DAYS"
      value = "60"
    },
    {
      name        = "APPLICATIONINSIGHTS_CONNECTION_STRING"
      secret_name = "appinsights-connection-string"
    },
  ]
}

# Agent 3 — Offer Fetching (timer: 12:00 and 20:00 UTC)
# Replaces offerFetch.yml GitHub Actions workflow.
module "job_offer_fetching" {
  source = "../../modules/container_app_job"

  name                       = "job-jf-dev-frc-fetch"
  location                   = var.location
  resource_group_name        = data.azurerm_resource_group.rg_app.name
  environment_id             = module.container_app_environment.id
  trigger_type               = "timer"
  cron_expression            = "0 12,20 * * *"
  replica_timeout_in_seconds = 3600
  image                      = "${module.container_registry.login_server}/agents/offer-fetching:latest"
  identity_ids               = [data.azurerm_user_assigned_identity.caj.id]
  registry_server            = module.container_registry.login_server
  registry_identity          = data.azurerm_user_assigned_identity.caj.id
  environment                = var.env
  project                    = var.project
  owner                      = var.owner
  secrets = [
    {
      name  = "postgresql-connection-string"
      value = local.postgresql_connection_string
    },
    {
      name  = "openai-api-key"
      value = local.openai_api_key
    },
    {
      name  = "ft-client-id"
      value = local.ft_client_id
    },
    {
      name  = "ft-client-secret"
      value = local.ft_client_secret
    },
    {
      name  = "appinsights-connection-string"
      value = module.application_insights.connection_string
    },
  ]
  env_vars = [
    {
      name        = "DATABASE_URL"
      secret_name = "postgresql-connection-string"
    },
    {
      name        = "AZURE_OPENAI_API_KEY"
      secret_name = "openai-api-key"
    },
    {
      name  = "AZURE_OPENAI_ENDPOINT"
      value = local.openai_endpoint
    },
    {
      name        = "FT_CLIENT_ID"
      secret_name = "ft-client-id"
    },
    {
      name        = "FT_CLIENT_SECRET"
      secret_name = "ft-client-secret"
    },
    {
      name  = "AZURE_SERVICEBUS_FULLY_QUALIFIED_NAMESPACE"
      value = "${module.servicebus.name}.servicebus.windows.net"
    },
    # Used by DefaultAzureCredential (bus.py) to select the right UAMI.
    # No KEDA auth here — this job is timer-triggered, not queue-triggered.
    {
      name  = "AZURE_CLIENT_ID"
      value = data.azurerm_user_assigned_identity.caj.client_id
    },
    {
      name        = "APPLICATIONINSIGHTS_CONNECTION_STRING"
      secret_name = "appinsights-connection-string"
    },
  ]
}

# ==============================================================================
# Agent cv-analysis (queue: cv-analysis)
# ==============================================================================
module "job_cv_analysis" {
  source = "../../modules/container_app_job"

  name                 = "job-jf-dev-frc-cv-analysis"
  location             = var.location
  resource_group_name  = data.azurerm_resource_group.rg_app.name
  environment_id       = module.container_app_environment.id
  trigger_type         = "queue"
  queue_name           = "cv-analysis"
  servicebus_namespace = module.servicebus.name
  image                = "${module.container_registry.login_server}/agents/cv-analysis:latest"
  environment          = var.env
  project              = var.project
  owner                = var.owner
  identity_ids         = [data.azurerm_user_assigned_identity.caj.id]
  registry_server      = module.container_registry.login_server
  registry_identity    = data.azurerm_user_assigned_identity.caj.id
  additional_tags      = { keda_reset = "2026-06-28" }
  secrets = [
    {
      name  = "postgresql-connection-string"
      value = local.postgresql_connection_string
    },
    {
      name  = "openai-api-key"
      value = local.openai_api_key
    },
    {
      name  = "appinsights-connection-string"
      value = module.application_insights.connection_string
    },
    {
      name  = "servicebus-connection-string"
      value = module.servicebus.primary_connection_string
    },
  ]
  env_vars = [
    {
      name        = "DATABASE_URL"
      secret_name = "postgresql-connection-string"
    },
    {
      name        = "AZURE_OPENAI_API_KEY"
      secret_name = "openai-api-key"
    },
    {
      name  = "AZURE_OPENAI_ENDPOINT"
      value = local.openai_endpoint
    },
    {
      name  = "AZURE_SERVICEBUS_FULLY_QUALIFIED_NAMESPACE"
      value = "${module.servicebus.name}.servicebus.windows.net"
    },
    {
      name  = "AZURE_OPENAI_ROME_DEPLOYMENT"
      value = "gpt-4o-mini"
    },
    {
      name  = "AZURE_CLIENT_ID"
      value = data.azurerm_user_assigned_identity.caj.client_id
    },
    {
      name        = "APPLICATIONINSIGHTS_CONNECTION_STRING"
      secret_name = "appinsights-connection-string"
    },
  ]
}
