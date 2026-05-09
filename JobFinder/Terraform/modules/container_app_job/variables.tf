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

variable "image" {
  type        = string
  description = "Docker image to run. Use placeholder in M1."
}

variable "cpu" {
  type        = number
  default     = 0.25
  description = "CPU allocation for the container in cores."
}

variable "memory" {
  type        = string
  default     = "0.5Gi"
  description = "Memory allocation for the container (e.g. 0.5Gi)."
}

variable "replica_timeout_in_seconds" {
  type        = number
  default     = 300
  description = "Maximum duration in seconds before a replica is terminated."
}

variable "replica_retry_limit" {
  type        = number
  default     = 3
  description = "Number of times a failed replica is retried before the job fails."
}

variable "max_executions" {
  type        = number
  default     = 1
  description = "Maximum number of job replicas running in parallel for queue triggers. Increase for prod under load."
}

variable "polling_interval_in_seconds" {
  type        = number
  default     = 30
  description = "Interval in seconds at which KEDA polls the queue for new messages."
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
