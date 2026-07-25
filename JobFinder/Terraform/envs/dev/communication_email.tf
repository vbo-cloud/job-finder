# ==============================================================================
# Azure Communication Services — Email
# ==============================================================================
# Sender for the notification agent's digest emails (PR 7/7 of the notifications
# plan — see docs/prompts/prompt-*.md). No RBAC granted here: an
# azurerm_role_assignment's scope must already exist at apply time, so the role
# for caj is PR 6/7, applied after this resource exists (see docs/prompts/
# prompt-acs-email-resource.md for the full ordering rationale).

module "email_communication" {
  source = "../../modules/email_communication"

  communication_service_name = "acs-${var.project}-${var.env}-${var.location_short}"
  email_service_name         = "ecs-${var.project}-${var.env}-${var.location_short}"
  resource_group_name        = data.azurerm_resource_group.rg_app.name
  data_location              = "France"
  domain_name                = var.notification_sender_domain
  sender_username            = var.notification_sender_username
  sender_display_name        = "JobFinder"
  environment                = var.env
  project                    = var.project
  owner                      = var.owner
}
