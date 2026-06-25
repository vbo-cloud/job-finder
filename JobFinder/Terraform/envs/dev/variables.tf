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

variable "jumpbox_ssh_public_key" {
  description = "SSH public key (authorized_keys format) for the jumpbox VM admin user."
  type        = string
  sensitive   = true
}

