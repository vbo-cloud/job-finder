variable "name" {
  type        = string
  description = "Name of the Application Insights resource."
}

variable "workspace_name" {
  type        = string
  description = "Name of the Log Analytics Workspace backing Application Insights."
}

variable "location" {
  type        = string
  description = "Azure region where the resources are deployed."
}

variable "resource_group_name" {
  type        = string
  description = "Name of the resource group that contains the resources."
}

variable "retention_in_days" {
  type        = number
  default     = 30
  description = "Log retention in days. 30 for dev, 90+ for prod."

  validation {
    condition     = var.retention_in_days >= 30 && var.retention_in_days <= 730
    error_message = "retention_in_days must be between 30 and 730."
  }
}

variable "daily_quota_gb" {
  type        = number
  default     = 1
  description = "Daily ingestion cap in GB for the Log Analytics Workspace. -1 = unlimited. Keep low in dev to avoid runaway agent costs."

  validation {
    condition     = var.daily_quota_gb == -1 || var.daily_quota_gb > 0
    error_message = "daily_quota_gb must be -1 (unlimited) or a positive number."
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
