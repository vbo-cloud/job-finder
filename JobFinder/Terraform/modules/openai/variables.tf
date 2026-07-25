variable "name" {
  type        = string
  description = "Name of the Azure OpenAI cognitive account."
}

variable "location" {
  type        = string
  description = "Azure region where the account is deployed."
}

variable "resource_group_name" {
  type        = string
  description = "Name of the resource group that contains the account."
}

variable "sku_name" {
  type        = string
  default     = "S0"
  description = "SKU of the cognitive account. S0 is the only option for Azure OpenAI."

  validation {
    condition     = var.sku_name == "S0"
    error_message = "sku_name must be 'S0' — the only supported SKU for Azure OpenAI."
  }
}

variable "environment" {
  type        = string
  description = "Environment identifier applied to resource tags (e.g. dev)."
}

variable "project" {
  type        = string
  description = "Short project identifier applied to resource tags (e.g. jf)."
}

variable "owner" {
  type        = string
  description = "Owner email address applied to resource tags."
}

variable "local_auth_enabled" {
  type        = bool
  default     = true
  description = "Whether API-key (local) authentication remains allowed on the account, in addition to Entra ID. Set to false once every consumer has migrated to Managed Identity — see docs/BACKLOG.md hardening item."
}

variable "deployments" {
  description = "Map of model deployments. Key = deployment name."
  type = map(object({
    model_name    = string
    model_version = string
    capacity_tpm  = number # Tokens per minute in thousands (e.g. 10 = 10K TPM)
    sku_name      = string # Deployment SKU: "Standard" or "GlobalStandard"
  }))

  validation {
    condition     = alltrue([for d in var.deployments : d.capacity_tpm > 0])
    error_message = "All deployment capacity_tpm values must be greater than 0."
  }

  validation {
    condition     = alltrue([for d in var.deployments : contains(["Standard", "GlobalStandard"], d.sku_name)])
    error_message = "All deployment sku_name values must be 'Standard' or 'GlobalStandard'."
  }
}
