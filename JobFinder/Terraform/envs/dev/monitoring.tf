# ==============================================================================
# Application Insights + Log Analytics
# ==============================================================================
# Single Application Insights instance for all agents.
# Each agent sets cloud_role_name in its code to differentiate its telemetry:
#   - agent-offer-fetching
#   - agent-embedding
#   - agent-matching
#   - agent-cleanup

module "application_insights" {
  source = "../../modules/application_insights"

  name                = "appi-${var.project}-${var.env}-${var.location_short}"
  workspace_name      = "log-${var.project}-${var.env}-${var.location_short}"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.rg_core.name
  retention_in_days   = 30
  environment         = var.env
  project             = var.project
  owner               = var.owner
}

module "secret_appinsights_connection_string" {
  source       = "../../modules/keyvault_secret"
  name         = "appinsights-connection-string"
  value        = module.application_insights.connection_string
  key_vault_id = module.keyvault.id
  content_type = "text/plain"
  environment  = var.env
  project      = var.project
  owner        = var.owner
}

# ==============================================================================
# Locals
# ==============================================================================
# Single maintenance point for job IDs — add new jobs here so metric alerts
# automatically pick them up without a separate scopes update.

locals {
  # Map of logical name → job ID. Add new jobs here so metric alerts
  # automatically get their own alert without a separate resource block.
  all_job_ids = {
    matching       = module.job_matching.id
    cleanup        = module.job_cleanup.id
    offer-fetching = module.job_offer_fetching.id
    cv-analysis    = module.job_cv_analysis.id
    match-analysis = module.job_match_analysis.id
  }
}

# ==============================================================================
# Alerting
# ==============================================================================

resource "azurerm_monitor_action_group" "owner" {
  name                = "ag-${var.project}-${var.env}-${var.location_short}-owner"
  resource_group_name = data.azurerm_resource_group.rg_core.name
  short_name          = "jf-owner"

  email_receiver {
    name          = "owner"
    email_address = var.alert_email
  }

  tags = {
    environment = var.env
    project     = var.project
    owner       = var.owner
  }
}

resource "azurerm_monitor_metric_alert" "job_execution_failed" {
  for_each = local.all_job_ids

  name                = "alert-${var.project}-${var.env}-${each.key}-failed"
  resource_group_name = data.azurerm_resource_group.rg_app.name
  # Microsoft.App/jobs does not support multi-resource scopes — one alert per job.
  scopes      = [each.value]
  description = "Container App Job '${each.key}' had a failed execution."
  severity    = 1
  frequency   = "PT5M"
  window_size = "PT15M"

  criteria {
    metric_namespace = "Microsoft.App/jobs"
    metric_name      = "Executions"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 0

    dimension {
      name     = "state"
      operator = "Include"
      values   = ["failed"]
    }
  }

  action {
    action_group_id = azurerm_monitor_action_group.owner.id
  }

  tags = {
    environment = var.env
    project     = var.project
    owner       = var.owner
  }
}

resource "azurerm_monitor_metric_alert" "servicebus_deadletter" {
  name                = "alert-${var.project}-${var.env}-sb-deadletter"
  resource_group_name = data.azurerm_resource_group.rg_app.name
  scopes              = [module.servicebus.id]
  description         = "Messages are accumulating in the dead-letter queue."
  severity            = 1
  frequency           = "PT5M"
  window_size         = "PT5M"

  criteria {
    metric_namespace = "Microsoft.ServiceBus/namespaces"
    metric_name      = "DeadletteredMessages"
    aggregation      = "Maximum"
    operator         = "GreaterThan"
    threshold        = 0
  }

  action {
    action_group_id = azurerm_monitor_action_group.owner.id
  }

  tags = {
    environment = var.env
    project     = var.project
    owner       = var.owner
  }
}

# ==============================================================================
# Diagnostic Settings — Container App Environment
# ==============================================================================
# Enables ContainerAppConsoleLogs (agent stdout/stderr) and
# ContainerAppSystemLogs (KEDA controller events, provisioning) on the CAE.
# Without these, Log Analytics tables are empty and KEDA failures are invisible.

resource "azurerm_monitor_diagnostic_setting" "cae" {
  name                       = "diag-${var.project}-${var.env}-${var.location_short}-cae"
  target_resource_id         = module.container_app_environment.id
  log_analytics_workspace_id = module.application_insights.workspace_id

  enabled_log {
    category = "ContainerAppConsoleLogs"
  }

  enabled_log {
    category = "ContainerAppSystemLogs"
  }
}

resource "azurerm_monitor_metric_alert" "servicebus_active_messages_stale" {
  name                = "alert-${var.project}-${var.env}-sb-stale-messages"
  resource_group_name = data.azurerm_resource_group.rg_app.name
  scopes              = [module.servicebus.id]
  description         = "Active messages not consumed for over 30 minutes — KEDA may be down."
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT30M"

  criteria {
    metric_namespace = "Microsoft.ServiceBus/namespaces"
    metric_name      = "ActiveMessages"
    aggregation      = "Minimum"
    operator         = "GreaterThan"
    threshold        = 0
  }

  action {
    action_group_id = azurerm_monitor_action_group.owner.id
  }

  tags = {
    environment = var.env
    project     = var.project
    owner       = var.owner
  }
}
