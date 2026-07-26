# ==============================================================================
# Notifications one-click unsubscribe — HMAC signing secret
# ==============================================================================
# Shared between job_notifications (signs the unsubscribe token when sending the digest,
# container_apps.tf) and webapp (verifies it in the future POST /notifications/unsubscribe
# endpoint, webapp.tf) — see docs/prompts/prompt-email-one-click-unsubscribe.md. Generated
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
