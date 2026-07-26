# ==============================================================================
# Notifications one-click unsubscribe — HMAC signing secret
# ==============================================================================
# Wired as NOTIFICATIONS_UNSUBSCRIBE_SECRET into both job_notifications (container_apps.tf)
# and webapp (webapp.tf), ahead of the app-logic PR that will make them sign/verify the
# unsubscribe token with it — see docs/prompts/prompt-email-one-click-unsubscribe.md. This
# PR only provisions and wires the secret; neither Container App consumes it yet. Generated
# by Terraform itself rather than seeded manually: unlike ft-client-id/entra-external-*
# (real third-party credentials provisioned out-of-band, see
# job-finder-private/docs/MANUAL_OPERATIONS.md), this value has no external counterpart to
# match, so Terraform can mint it directly — same pattern as jumpbox.tf's admin password.
resource "random_password" "notifications_unsubscribe_secret" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>?"
}

module "secret_notifications_unsubscribe" {
  source       = "../../modules/keyvault_secret"
  name         = "notifications-unsubscribe-secret"
  value        = random_password.notifications_unsubscribe_secret.result
  key_vault_id = module.keyvault.id
  environment  = var.env
  project      = var.project
  owner        = var.owner
}
