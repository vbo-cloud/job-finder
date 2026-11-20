variable "name" {
  type        = string
  description = "Name of the Container App Job."
}

variable "location" {
  type        = string
  description = "Azure region where the job is deployed."
}

variable "resource_group_name" {
  type        = string
  description = "Name of the resource group that contains the job."
}

variable "environment_id" {
  type        = string
  description = "Container Apps Environment resource ID."
}

variable "trigger_type" {
  type        = string
  description = "Trigger type for the job. Accepted values: timer, queue."

  validation {
    condition     = contains(["timer", "queue"], var.trigger_type)
    error_message = "trigger_type must be 'timer' or 'queue'."
  }
}

variable "cron_expression" {
  type        = string
  default     = null
  description = "Cron expression for timer trigger. Required if trigger_type = timer."
}

variable "queue_name" {
  type        = string
  default     = null
  description = "Service Bus queue name. Required if trigger_type = queue."
}

variable "servicebus_namespace" {
  type        = string
  default     = null
  description = "Service Bus namespace name. Required if trigger_type = queue."
}

variable "uami_client_id" {
  type        = string
  default     = null
  nullable    = true
  description = "Client ID of the User Assigned Managed Identity used for KEDA Service Bus workload identity authentication. When set, replaces the connection-string-based authentication block with workload identity. When null (default), the caller must provide a 'servicebus-connection-string' secret."

  validation {
    condition     = var.uami_client_id == null || can(regex("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", var.uami_client_id))
    error_message = "uami_client_id must be a valid UUID (e.g. '00000000-0000-0000-0000-000000000000')."
  }

  validation {
    condition     = (var.uami_client_id == null) == (var.uami_tenant_id == null)
    error_message = "uami_client_id and uami_tenant_id must both be set or both be null."
  }
}

variable "uami_tenant_id" {
  type        = string
  default     = null
  nullable    = true
  description = "Tenant ID of the Azure AD tenant where the UAMI is registered. Required alongside uami_client_id for KEDA 2.18+ workload identity auth on the azure-servicebus scaler."

  validation {
    condition     = var.uami_tenant_id == null || can(regex("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", var.uami_tenant_id))
    error_message = "uami_tenant_id must be a valid UUID (e.g. '00000000-0000-0000-0000-000000000000')."
  }
}

variable "image" {
  type        = string
  description = "Docker image to run. Use placeholder in M1."
}

variable "cpu" {
  type        = number
  default     = 0.25
  description = "CPU allocation for the container in cores."

  validation {
    condition     = var.cpu > 0 && var.cpu <= 4
    error_message = "cpu must be greater than 0 and at most 4 cores (Container Apps limit)."
  }
}

variable "memory" {
  type        = string
  default     = "0.5Gi"
  description = "Memory allocation for the container (e.g. 0.5Gi)."

  validation {
    condition     = can(regex("^[0-9]+(\\.[0-9]+)?Gi$", var.memory)) && tonumber(replace(var.memory, "Gi", "")) > 0
    error_message = "memory must be in the format '<number>Gi' (e.g. 0.5Gi, 1Gi, 2Gi) and must be greater than 0."
  }
}

variable "replica_timeout_in_seconds" {
  type        = number
  default     = 300
  description = "Maximum duration in seconds before a replica is terminated."

  validation {
    condition     = var.replica_timeout_in_seconds >= 1 && var.replica_timeout_in_seconds <= 86400
    error_message = "replica_timeout_in_seconds must be between 1 and 86400 (24 hours)."
  }
}

variable "replica_retry_limit" {
  type        = number
  default     = 3
  description = "Number of times a failed replica is retried before the job fails."

  validation {
    condition     = var.replica_retry_limit >= 0
    error_message = "replica_retry_limit must be 0 or greater."
  }
}

variable "max_executions" {
  type        = number
  default     = 1
  description = "Maximum number of job replicas running in parallel for queue triggers. Increase for prod under load."

  validation {
    condition     = var.max_executions >= 1
    error_message = "max_executions must be at least 1."
  }
}

variable "polling_interval_in_seconds" {
  type        = number
  default     = 30
  description = "Interval in seconds at which KEDA polls the queue for new messages."

  validation {
    condition     = var.polling_interval_in_seconds >= 1
    error_message = "polling_interval_in_seconds must be at least 1."
  }
}

variable "env_vars" {
  type = list(object({
    name        = string
    value       = optional(string)
    secret_name = optional(string)
  }))
  default     = []
  description = "Environment variables for the container. Set 'value' for plain text, 'secret_name' for secret-backed variables. Exactly one of the two must be set per entry."
}

variable "secrets" {
  type = list(object({
    name  = string
    value = string
  }))
  default     = []
  sensitive   = true
  description = "Secrets available to the container."
}

variable "identity_ids" {
  type        = list(string)
  default     = []
  description = "List of User Assigned Managed Identity resource IDs to attach to the job. Required when pulling images from a private registry."
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

variable "additional_tags" {
  type        = map(string)
  default     = {}
  description = "Additional tags merged into the resource tags. Useful for one-off operational markers (e.g. keda_reset)."
}
