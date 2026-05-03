variable "name" {
  type        = string
  description = "Key Vault name (globally unique, 3-24 chars)"
}

variable "location" {
  type        = string
  description = "Azure region"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group to deploy into"
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

variable "sku_name" {
  type        = string
  description = "Key Vault SKU: standard or premium"
  default     = "standard"
}

variable "soft_delete_retention_days" {
  type        = number
  description = "Soft delete retention in days (7-90)"
  default     = 7
}
