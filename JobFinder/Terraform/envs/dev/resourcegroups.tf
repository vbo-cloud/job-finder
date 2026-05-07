# Three resource groups enforce separation of concerns and allow fine-grained RBAC:
# - core: infrastructure and shared services (AKS, networking attachments)
# - app:  application workloads and containers
# - data: databases, storage accounts, and other stateful resources

# ==============================================================================
# Core
# ==============================================================================

module "rg_core" {
  source      = "../../modules/resource_group"
  name        = "rg-${var.project}-dev-${var.location_short}-core"
  location    = var.location
  environment = var.env
  project     = var.project
  owner       = var.owner
}

# ==============================================================================
# Application
# ==============================================================================

module "rg_app" {
  source      = "../../modules/resource_group"
  name        = "rg-${var.project}-dev-${var.location_short}-app"
  location    = var.location
  environment = var.env
  project     = var.project
  owner       = var.owner
}

# ==============================================================================
# Data
# ==============================================================================

module "rg_data" {
  source      = "../../modules/resource_group"
  name        = "rg-${var.project}-dev-${var.location_short}-data"
  location    = var.location
  environment = var.env
  project     = var.project
  owner       = var.owner
}
