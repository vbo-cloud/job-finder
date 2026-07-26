# Variables default to CHANGE_ME so terraform validate passes on a fresh clone;
# fill in terraform.tfvars with real values before running plan or apply.
# tenant_id and subscription_id are not declared here — they are injected via
# ARM_TENANT_ID and ARM_SUBSCRIPTION_ID environment variables by the CI/CD OIDC workflow.

variable "location" {
  type        = string
  description = "Azure primary region for resource deployment"
  default     = "CHANGE_ME"

  validation {
    condition     = var.location != "CHANGE_ME"
    error_message = "location must be set — replace CHANGE_ME with a real Azure region (e.g. francecentral)."
  }
}

variable "location_short" {
  type        = string
  description = "Short identifier for the Azure region, used in resource names (e.g. frc for francecentral)"
  default     = "CHANGE_ME"

  validation {
    condition     = can(regex("^[a-z]{2,4}$", var.location_short))
    error_message = "location_short must be 2-4 lowercase letters (e.g. frc)."
  }
}

variable "project" {
  type        = string
  description = "Short project identifier used in resource names (e.g. jf)"
  default     = "CHANGE_ME"

  validation {
    condition     = can(regex("^[a-z]{2,4}$", var.project))
    error_message = "project must be 2-4 lowercase letters (e.g. jf)."
  }
}

variable "owner" {
  type        = string
  description = "Owner email address applied to all resource tags"
  default     = "CHANGE_ME"

  validation {
    condition     = can(regex("^[^@]+@[^@]+\\.[^@]+$", var.owner))
    error_message = "owner must be a valid email address (e.g. user@example.com)."
  }
}

variable "env" {
  type        = string
  description = "Environment identifier applied to all resource tags (e.g. dev)"
  default     = "dev"
}

variable "alert_email" {
  description = "Email address to notify on monitoring alerts."
  type        = string
  validation {
    condition     = can(regex("^[^@]+@[^@]+\\.[^@]+$", var.alert_email))
    error_message = "alert_email must be a valid email address."
  }
}

variable "admin_user_ids" {
  type        = string
  default     = ""
  description = "Comma-separated Entra External ID user IDs (JWT sub claims) granted in-app admin features in the webapp (e.g. the credits refill button). Empty string means no admins — the feature is simply disabled."
}

variable "portfolio_contact_function_url" {
  type        = string
  default     = ""
  sensitive   = true
  description = "URL of the portfolio repo's sendContactEmail Azure Function, called server-to-server by the webapp's POST /feedback endpoint. Not a secret in the confidentiality sense — an anonymous-auth HTTP Function URL — but left empty by default since it's only known after that Function is deployed; empty string means the feedback endpoint returns 502 until this is set (see docs/JOURNAL.md). Marked sensitive = true purely as log hygiene: this repo is public, so it keeps the value out of terraform plan's formatted diff in CI logs, on top of the GitHub Actions secret already masking it at the raw-text level."
}

variable "frontend_custom_domain" {
  type        = string
  default     = "jobfinder.vincentboutin.dev"
  description = "Custom domain for the frontend Container App. Not yet bound to an azurerm_container_app_custom_domain resource -- that binding lands in a follow-up PR once DNS propagation is confirmed (see docs/JOURNAL.md, PR #191). Referenced now so CORS_ALLOWED_ORIGINS and that future binding share a single source of truth instead of duplicating the literal."

  validation {
    condition     = can(regex("^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$", var.frontend_custom_domain))
    error_message = "frontend_custom_domain must be a valid DNS hostname (e.g. jobfinder.vincentboutin.dev)."
  }
}

variable "notification_sender_domain" {
  type        = string
  default     = "vincentboutin.dev"
  description = "Custom domain used as the sender for the notification agent's digest emails (Azure Communication Services Email, CustomerManaged domain). DNS records proving ownership (see the email_verification_records output) must be added manually at the domain's DNS host before Azure marks it Verified — same pattern as frontend_custom_domain (PR #191)."

  validation {
    condition     = can(regex("^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$", var.notification_sender_domain))
    error_message = "notification_sender_domain must be a valid DNS hostname (e.g. vincentboutin.dev)."
  }
}

variable "notification_sender_username" {
  type        = string
  default     = "jobfinder_donotreply"
  description = "Local part of the notification digest sender address (e.g. jobfinder_donotreply for jobfinder_donotreply@vincentboutin.dev)."

  validation {
    condition     = can(regex("^[a-z0-9._-]+$", var.notification_sender_username))
    error_message = "notification_sender_username must contain only lowercase letters, digits, dots, underscores, or hyphens."
  }
}

variable "budget_amount" {
  type = number
  # Azure bills in the subscription's billing currency (check the portal —
  # commonly EUR, not USD, for a France-based subscription). This value is a
  # bare number in whatever that currency is; it is not converted.
  default     = 40
  description = "Monthly budget amount for the rg_app resource group, in the subscription's billing currency, that triggers a cost-drift alert at 100% (see monitoring.tf's azurerm_consumption_budget_resource_group)."

  validation {
    condition     = var.budget_amount > 0
    error_message = "budget_amount must be greater than 0."
  }
}

variable "openai_capacity_tpm" {
  type    = number
  default = 1000
  # Single variable shared by gpt-4o-mini and text-embedding-3-small.
  # If the two models ever need independent quotas, split into two variables.
  description = "Token per minute quota (in thousands) for all Azure OpenAI model deployments. 1000 = 1M TPM. Each apply resets any manual portal change — update here to change the quota."

  validation {
    condition     = var.openai_capacity_tpm > 0
    error_message = "openai_capacity_tpm must be greater than 0."
  }
}

