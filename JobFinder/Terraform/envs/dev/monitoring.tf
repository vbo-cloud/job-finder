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
  all_job_ids = [
    module.job_matching.id,
    module.job_cleanup.id,
    module.job_offer_fetching.id,
    module.job_cv_analysis.id,
  ]
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
  name                = "alert-${var.project}-${var.env}-job-execution-failed"
  resource_group_name = data.azurerm_resource_group.rg_app.name
  # Metric alerts on Microsoft.App/jobs must target the job resources directly;
  # the CAE (managedEnvironments) does not expose job execution metrics.
  scopes = local.all_job_ids
  description = "A Container App Job execution failed."
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
