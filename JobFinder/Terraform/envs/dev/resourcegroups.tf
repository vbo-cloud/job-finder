# Three resource groups enforce separation of concerns and allow fine-grained RBAC:
# - core: infrastructure and shared services (AKS, networking attachments)
# - app:  application workloads and containers
# - data: databases, storage accounts, and other stateful resources

# ==============================================================================
# Core
# ==============================================================================

resource "azurerm_resource_group" "rg_core" {
  name     = "rg-${var.project}-dev-${var.location_short}-core"
  location = var.location

  tags = {
    environment = "dev"
    project     = var.project
    owner       = var.owner
  }
}

# ==============================================================================
# Application
# ==============================================================================

resource "azurerm_resource_group" "rg_app" {
  name     = "rg-${var.project}-dev-${var.location_short}-app"
  location = var.location

  tags = {
    environment = "dev"
    project     = var.project
    owner       = var.owner
  }
}

# ==============================================================================
# Data
# ==============================================================================

resource "azurerm_resource_group" "rg_data" {
  name     = "rg-${var.project}-dev-${var.location_short}-data"
  location = var.location

  tags = {
    environment = "dev"
    project     = var.project
    owner       = var.owner
  }
}
