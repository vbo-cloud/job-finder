variable "name" {
  type        = string
  description = "Name of the Container App."
}

variable "resource_group_name" {
  type        = string
  description = "Name of the resource group that contains the Container App."
}

variable "environment_id" {
  type        = string
  description = "Container Apps Environment resource ID."
}

variable "image" {
  type        = string
  description = "Docker image to run (e.g. acrjfdevfrc.azurecr.io/agents/webapp:latest)."
}

variable "cpu" {
  type        = number
  default     = 0.5
  description = "CPU allocation for the container in vCPU cores."

  validation {
    condition     = var.cpu > 0 && var.cpu <= 4
    error_message = "cpu must be greater than 0 and at most 4 (Container Apps limit)."
  }
}

variable "memory" {
  type        = string
  default     = "1Gi"
  description = "Memory allocation for the container (e.g. 1Gi, 2Gi)."

  validation {
    condition     = can(regex("^[0-9]+(\\.[0-9]+)?Gi$", var.memory)) && tonumber(replace(var.memory, "Gi", "")) > 0
    error_message = "memory must be in the format '<number>Gi' (e.g. 0.5Gi, 1Gi) and must be greater than 0."
  }
}

variable "min_replicas" {
  type        = number
  default     = 0
  description = "Minimum number of replicas. 0 enables scale-to-zero."

  validation {
    condition     = var.min_replicas >= 0
    error_message = "min_replicas must be 0 or greater."
  }
}

variable "max_replicas" {
  type        = number
  default     = 1
  description = "Maximum number of replicas. Must be greater than or equal to min_replicas (Terraform cannot cross-validate variables, so this is a caller responsibility)."

  validation {
    condition     = var.max_replicas >= 1
    error_message = "max_replicas must be at least 1."
  }
}

variable "env_vars" {
  type = list(object({
    name        = string
    value       = optional(string)
    secret_name = optional(string)
  }))
  default     = []
  description = "Environment variables for the container. Set 'value' for plain text, 'secret_name' for secret-backed variables."
}

variable "secrets" {
  type = list(object({
    name  = string
    value = string
  }))
  default     = []
  sensitive   = true
  description = "Secrets available to the container, referenced by 'secret_name' in env_vars."
}

variable "identity_ids" {
  type        = list(string)
  default     = []
  description = "List of User Assigned Managed Identity resource IDs to attach to the Container App."
}

variable "registry_server" {
  type        = string
  default     = null
  description = "Container registry login server hostname (e.g. acrjfdevfrc.azurecr.io). Required when pulling from a private registry."
}

variable "registry_identity" {
  type        = string
  default     = null
  description = "Resource ID of the User Assigned Managed Identity used to authenticate to the registry. Required when registry_server is set."

  validation {
    condition     = var.registry_server == null || var.registry_identity != null
    error_message = "registry_identity must be set when registry_server is provided."
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
