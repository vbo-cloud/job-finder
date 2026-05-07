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
  resource_group_name = module.rg_core.name
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
