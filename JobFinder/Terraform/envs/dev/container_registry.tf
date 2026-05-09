# ==============================================================================
# Container Registry
# ==============================================================================
# Stores Docker images for the 4 agents:
#   - agent-offer-fetching
#   - agent-embedding
#   - agent-matching
#   - agent-cleanup
# Images are pulled by Container Apps via AcrPull Managed Identity (M2).

module "container_registry" {
  source = "../../modules/container_registry"

  name                = "cr${var.project}${var.env}${var.location_short}"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.rg_app.name
  sku                 = "Basic"
  environment         = var.env
  project             = var.project
  owner               = var.owner
}

module "secret_acr_login_server" {
  source       = "../../modules/keyvault_secret"
  name         = "acr-login-server"
  value        = module.container_registry.login_server
  key_vault_id = module.keyvault.id
  content_type = "text/plain"
  environment  = var.env
  project      = var.project
  owner        = var.owner
}
