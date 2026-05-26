# ==============================================================================
# Container Apps Environment
# ==============================================================================
# Shared environment for all agent jobs.
# Each agent is a separate Container App Job — same environment, independent
# scaling, trigger, and lifecycle.
# Naming: job names use {type}-{project}-{env}-{region}-{suffix} pattern.
# Container App Job names are capped at 32 characters — the suffix is kept short accordingly.

module "container_app_environment" {
  source = "../../modules/container_app_environment"

  name                       = "cae-${var.project}-${var.env}-${var.location_short}"
  location                   = var.location
  resource_group_name        = data.azurerm_resource_group.rg_app.name
  log_analytics_workspace_id = module.application_insights.workspace_id
  environment                = var.env
  project                    = var.project
  owner                      = var.owner
}

# ==============================================================================
# Agent Jobs
# ==============================================================================
# Offer fetch and embedding are handled by GitHub Actions (offerFetch.yml) — not a CAJ.
# Agent 1 — Matching (queue: offer-ready)
# Agent 2 — Cleanup (timer: 02:00 UTC)

locals {
  # M2: basculer sur key_vault_secret_id avec Managed Identity.
  servicebus_connection_string = module.servicebus.primary_connection_string
}

# ==============================================================================
# Managed Identity — Container App Jobs
# ==============================================================================
# UAMI and AcrPull role assignment are managed by lz_dev (sp-jf-platform).
# sp-jf-github (Contributor only) cannot create role assignments.

# Bootstrap: UAMI is created by lz_dev on first apply. Uncomment once lz_dev
# has been applied and id-jf-dev-frc-caj exists in rg-jf-dev-frc-core.
# data "azurerm_user_assigned_identity" "caj" {
#   name                = "id-${var.project}-${var.env}-${var.location_short}-caj"
#   resource_group_name = data.azurerm_resource_group.rg_core.name
# }

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
  image                = "mcr.microsoft.com/azuredocs/containerapps-helloworld"
  environment          = var.env
  project              = var.project
  owner                = var.owner
  # Uncomment after lz_dev apply creates the UAMI (id-jf-dev-frc-caj).
  # identity_ids      = [data.azurerm_user_assigned_identity.caj.id]
  # registry_server   = module.container_registry.login_server
  # registry_identity = data.azurerm_user_assigned_identity.caj.id
  secrets = [
    {
      name  = "servicebus-connection-string"
      value = local.servicebus_connection_string
    },
  ]
  env_vars = [
    {
      name        = "AZURE_SERVICEBUS_CONNECTION_STRING"
      secret_name = "servicebus-connection-string"
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
  image               = "mcr.microsoft.com/azuredocs/containerapps-helloworld"
  environment         = var.env
  project             = var.project
  owner               = var.owner
  # Uncomment after lz_dev apply creates the UAMI (id-jf-dev-frc-caj).
  # identity_ids      = [data.azurerm_user_assigned_identity.caj.id]
  # registry_server   = module.container_registry.login_server
  # registry_identity = data.azurerm_user_assigned_identity.caj.id
}
