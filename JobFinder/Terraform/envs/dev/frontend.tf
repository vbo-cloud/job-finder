# ==============================================================================
# Frontend — Next.js
# ==============================================================================
# NEXT_PUBLIC_* variables are inlined into the JS bundle at `npm run build` time
# (see frontend/Dockerfile), not read at runtime — so this Container App carries
# no env_vars/secrets of its own, unlike the webapp module below.

module "frontend" {
  source = "../../modules/container_app"

  name                = "app-${var.project}-${var.env}-${var.location_short}-frontend"
  resource_group_name = data.azurerm_resource_group.rg_app.name
  environment_id      = module.container_app_environment.id
  image               = "${module.container_registry.login_server}/frontend:latest"
  target_port         = 3000
  cpu                 = 0.5
  memory              = "1Gi"
  min_replicas        = 0
  max_replicas        = 1
  # Reuses the Container App Jobs' shared identity purely for ACR pull (its only
  # permission that's relevant here) rather than provisioning a dedicated identity.
  # The frontend never calls Azure services directly, so it implicitly inherits
  # whatever permissions id-jf-dev-frc-caj gains in the future even though it only
  # needs this one. See BACKLOG.md ("dédier une identité au frontend").
  identity_ids      = [data.azurerm_user_assigned_identity.caj.id]
  registry_server   = module.container_registry.login_server
  registry_identity = data.azurerm_user_assigned_identity.caj.id
  environment       = var.env
  project           = var.project
  owner             = var.owner
}
