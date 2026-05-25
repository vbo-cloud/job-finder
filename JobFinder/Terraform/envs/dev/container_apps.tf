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
# M1: no secrets — placeholder image only.
# M2: add postgresql-connection-string secret to purge stale offers and matches from the DB.
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
}
