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
  # min_replicas = 1 trades scale-to-zero for no cold start; accepted idle-rate
  # cost is ~$0.000008/vCPU-s + $0.000001/GiB-s (see docs/JOURNAL.md, PR #210).
  min_replicas = 1
  max_replicas = 1
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
# to be created after; that applied successfully.
#
# PR #196 then attempted a phase 2 that flipped this resource's
# certificate_binding_type to "SniEnabled" directly, on the (wrong) assumption
# that Azure auto-resolves a managed certificate by matching subject_name once
# SniEnabled is requested. It doesn't: `terraform apply` reported success, but
# `az containerapp hostname list` showed the live binding stuck at "Disabled"
# -- the custom domain was live but served no certificate. Root cause,
# confirmed against the azurerm provider source and two open upstream issues
# (github.com/hashicorp/terraform-provider-azurerm issues #25788 and #27362):
# azurerm_container_app_custom_domain's container_app_environment_certificate_id
# argument only validates bring-your-own certificate IDs (ARM path
# .../certificates/...) and hard-rejects managed certificate IDs
# (.../managedCertificates/...). There is no argument on this resource that
# can reference a managed certificate -- the upstream-documented workaround is
# `lifecycle { ignore_changes = [certificate_binding_type,
# container_app_environment_certificate_id] }` plus binding the certificate
# out-of-band (portal or `az containerapp hostname bind`), which is exactly
# the kind of manual step this project's Terraform-only workflow avoids.
#
# The ignore_changes below keeps this resource pinned at the Disabled/no-cert
# shape it can actually manage (so Terraform stops trying, and failing, to
# reconcile a state it can't reach) while azapi_update_resource below does the
# one thing azurerm can't: PATCH the container app's ingress.customDomains
# directly via the ARM API, which -- unlike the azurerm provider's client-side
# validator -- accepts a managed certificate ID natively (it's what
# `az containerapp hostname bind` itself calls under the hood).
#
# No tags block: azurerm_container_app_custom_domain has no tags attribute in
# the provider schema (a binding/config resource, not independently taggable
# in ARM -- same category of exception as azurerm_subnet, see conventions-terraform).
resource "azurerm_container_app_custom_domain" "frontend" {
  name                     = var.frontend_custom_domain
  container_app_id         = module.frontend.id
  certificate_binding_type = "Disabled"

  lifecycle {
    ignore_changes = [certificate_binding_type, container_app_environment_certificate_id]
  }
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

# Binds the managed certificate above to the custom domain via a direct ARM
# PATCH, bypassing azurerm_container_app_custom_domain's inability to accept a
# managed certificate ID (see the comment block above). This is a merge-patch
# (azapi_update_resource only touches the paths listed in `body`) *at the
# Terraform level* -- the ARM resource provider's own merge behavior for the
# `ingress` object is not something the Terraform provider controls or
# guarantees, so after the first real apply, confirm via
# `az containerapp ingress show -n app-jf-dev-frc-frontend -g rg-jf-dev-frc-app`
# that target_port/external/transport/traffic weren't reset -- this project
# has already been burned once (PR #196) by an unverified assumption about
# this same API's behavior.
#
# depends_on is required on both: neither the custom domain hostname
# registration nor the certificate is referenced by attribute inside `body`
# (customDomains.name is a plain string, not
# `azurerm_container_app_custom_domain.frontend.name`), so without it
# Terraform has no graph edge forcing this to run after them.
#
# Removing this resource from config only stops Terraform from managing the
# binding -- azapi_update_resource has no revert/destroy body, so `terraform
# destroy` (or dropping this block) leaves the SNI binding live on the
# container app. To actually unbind, patch bindingType back to "Disabled"
# explicitly first.
resource "azapi_update_resource" "frontend_custom_domain_binding" {
  type        = "Microsoft.App/containerApps@2024-03-01"
  resource_id = module.frontend.id

  body = {
    properties = {
      configuration = {
        ingress = {
          customDomains = [
            {
              name          = var.frontend_custom_domain
              bindingType   = "SniEnabled"
              certificateId = azurerm_container_app_environment_managed_certificate.frontend.id
            }
          ]
        }
      }
    }
  }

  depends_on = [
    azurerm_container_app_custom_domain.frontend,
    azurerm_container_app_environment_managed_certificate.frontend,
  ]
}
