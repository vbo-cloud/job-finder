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
# This binding was created in two phases because Azure rejects creating the
# managed certificate unless the hostname is *already* registered as a custom
# domain on the app (API error RequireCustomHostnameInEnvironment), while a
# custom domain that references a not-yet-existing certificate makes Terraform
# create the certificate first (dependency ordering) -- the two requirements
# contradicted each other within a single apply. Phase 1 (PR #195) registered
# the custom domain with certificate_binding_type = "Disabled" and no
# certificate reference, plus an explicit depends_on forcing the certificate
# to be created after; that applied successfully. This final state below
# (phase 2) flips the binding to "SniEnabled" on the already-existing custom
# domain. `terraform plan` shows this change as `-/+ destroy and then create
# replacement`, not an in-place update, on this specific value transition --
# expect the custom domain resource to be recreated, and a brief window where
# jobfinder.vincentboutin.dev is unbound from the app during the apply.
# Acceptable for dev (no SLA, prod mirror deferred to v1.0.0 per CLAUDE.md).

# No tags block: azurerm_container_app_custom_domain has no tags attribute in
# the provider schema (a binding/config resource, not independently taggable
# in ARM -- same category of exception as azurerm_subnet, see conventions-terraform).
#
# No container_app_environment_certificate_id here: that argument expects a
# bring-your-own azurerm_container_app_environment_certificate (uploaded cert,
# ARM path .../certificates/...), not a managed certificate (.../managedCertificates/...
# -- confirmed via the provider schema, using the wrong one fails terraform plan
# with a hard ARM ID parsing error). The field that *would* reference a managed
# certificate, container_app_environment_managed_certificate_id, is Computed-only
# -- Azure resolves it itself by matching subject_name to this hostname once
# certificate_binding_type = "SniEnabled" and a matching managed certificate
# already exists (it does, see the resource below, already Succeeded).
resource "azurerm_container_app_custom_domain" "frontend" {
  name                     = var.frontend_custom_domain
  container_app_id         = module.frontend.id
  certificate_binding_type = "SniEnabled"
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
}
