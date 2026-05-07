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
