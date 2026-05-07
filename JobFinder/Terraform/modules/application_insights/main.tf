# ==============================================================================
# Log Analytics Workspace
# ==============================================================================
# Backend storage for Application Insights data.
resource "azurerm_log_analytics_workspace" "this" {
  name                = var.workspace_name
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = var.retention_in_days
  daily_quota_gb      = var.daily_quota_gb

  tags = {
    environment = var.environment
    project     = var.project
    owner       = var.owner
  }

  lifecycle {
    prevent_destroy = true
  }
}

# ==============================================================================
# Application Insights
# ==============================================================================
# Agents identify themselves via cloud_role_name in their code —
# all agents share one resource, differentiated by that field.
resource "azurerm_application_insights" "this" {
  name                = var.name
  location            = var.location
  resource_group_name = var.resource_group_name
  workspace_id        = azurerm_log_analytics_workspace.this.id
  application_type    = "other"
  retention_in_days   = var.retention_in_days

  tags = {
    environment = var.environment
    project     = var.project
    owner       = var.owner
  }

  lifecycle {
    prevent_destroy = true
  }
}
