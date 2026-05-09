variable "name" {
  type        = string
  description = "Storage account name (globally unique, no hyphens, max 24 chars)"
}

variable "location" {
  type        = string
  description = "Azure region"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group for the storage account"
}

variable "environment" {
  type        = string
  description = "Environment tag value"
}

variable "project" {
  type        = string
  description = "Project tag value"
}

variable "owner" {
  type        = string
  description = "Owner tag value (email)"
}
