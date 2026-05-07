variable "name" {
  type        = string
  description = "Name of the Azure Container Registry."
}

variable "location" {
  type        = string
  description = "Azure region where the registry is deployed."
}

variable "resource_group_name" {
  type        = string
  description = "Name of the resource group that contains the registry."
}

variable "sku" {
  type        = string
  default     = "Basic"
  description = "ACR SKU. Basic for dev, Standard or Premium for prod."
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
