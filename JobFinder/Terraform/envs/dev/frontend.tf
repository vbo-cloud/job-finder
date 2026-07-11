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

# ==============================================================================
# Frontend — Custom domain binding
# ==============================================================================
# Requires the TXT (asuid.<subdomain>, value = the container_app_environment_
# custom_domain_verification_id output) and CNAME (<subdomain> -> frontend_url
# output) records to already be live at the DNS registrar (OVH, managed outside
# this repo) before this applies successfully -- domain_control_validation =
# "CNAME" means Azure issues the managed certificate by checking that the CNAME
# already resolves to this Container App, so DNS propagation must complete first.
# If this apply fails on a fresh domain, it's almost always DNS not propagated
# yet -- confirm with `nslookup`/`dig` and re-run rather than changing this code.
#
# Two-phase resource creation, distinct from the DNS propagation wait above:
# Azure rejects creating the managed certificate unless the hostname is
# *already* registered as a custom domain on the app (API error
# RequireCustomHostnameInEnvironment), but a custom domain that references a
# not-yet-existing certificate would make Terraform create the certificate
# first (dependency ordering) -- the two requirements contradict each other
# within a single apply. Phase 1 (this state): custom domain registered with
# no certificate (binding "Disabled"), which lets the certificate resource
# below succeed. Phase 2 (follow-up commit, after phase 1 has applied
# successfully): add certificate_binding_type = "SniEnabled" and
# container_app_environment_certificate_id back onto the custom domain -- an
# in-place update at that point, not a create, so the ordering conflict
# doesn't recur.

# No tags block: azurerm_container_app_custom_domain has no tags attribute in
# the provider schema (a binding/config resource, not independently taggable
# in ARM -- same category of exception as azurerm_subnet, see conventions-terraform).
resource "azurerm_container_app_custom_domain" "frontend" {
  name                     = var.frontend_custom_domain
  container_app_id         = module.frontend.id
  certificate_binding_type = "Disabled"
}

resource "azurerm_container_app_environment_managed_certificate" "frontend" {
  name                         = "cert-${var.project}-${var.env}-${var.location_short}-frontend"
  container_app_environment_id = module.container_app_environment.id
  subject_name                 = var.frontend_custom_domain
  domain_control_validation    = "CNAME"

  tags = {
    environment = var.env
    project     = var.project
    owner       = var.owner
  }

  depends_on = [azurerm_container_app_custom_domain.frontend]
}
