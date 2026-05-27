variable "name" {
  type        = string
  description = "Name of the Container App Environment."
}

variable "location" {
  type        = string
  description = "Azure region where the environment is deployed."
}

variable "resource_group_name" {
  type        = string
  description = "Name of the resource group that contains the environment."
}

variable "log_analytics_workspace_id" {
  type        = string
  description = "Resource ID of the Log Analytics Workspace used for agent telemetry."
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

variable "infrastructure_subnet_id" {
  type        = string
  default     = null
  description = "Resource ID of the subnet to inject the Container App Environment into. Must be a /23 or larger, delegated to Microsoft.App/environments. Null = no VNet injection (Consumption-only mode)."
}
