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

  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
    maximum_count         = 0
    minimum_count         = 0
  }

  tags = merge(
    {
      environment = var.environment
      project     = var.project
      owner       = var.owner
      protect     = "true"
    },
    var.additional_tags
  )

  lifecycle {
    prevent_destroy       = true
  }
}
