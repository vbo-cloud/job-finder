# ==============================================================================
# Azure Container Registry
# ==============================================================================
resource "azurerm_container_registry" "this" {
  name                = var.name
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = var.sku

  # Admin account disabled — agents authenticate via Managed Identity (AcrPull role)
  admin_enabled = false

  tags = {
    environment = var.environment
    project     = var.project
    owner       = var.owner
    protect     = "true"
  }

  lifecycle {
    prevent_destroy = true
  }
}
