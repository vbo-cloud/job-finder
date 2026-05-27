# ==============================================================================
# Container App Environment
# ==============================================================================
# Shared execution environment for all Container App Jobs.
# Embeds KEDA for event-driven and cron triggers.

resource "azurerm_container_app_environment" "this" {
  name                       = var.name
  location                   = var.location
  resource_group_name        = var.resource_group_name
  log_analytics_workspace_id = var.log_analytics_workspace_id
  infrastructure_subnet_id   = var.infrastructure_subnet_id

  tags = {
    environment = var.environment
    project     = var.project
    owner       = var.owner
    protect     = "true"
  }

  # prevent_destroy temporarily removed to allow subnet injection (immutable property — forces replace).
  # Re-add after successful apply.
  lifecycle {}
}
