variable "name" {
  type        = string
  description = "Name of the Azure Container Registry. Must be globally unique and alphanumeric only (ACR constraint — hyphens not allowed). Convention: cr{project}{env}{region} e.g. crjfdevfrc"
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

  validation {
    condition     = contains(["Basic", "Standard", "Premium"], var.sku)
    error_message = "sku must be 'Basic', 'Standard', or 'Premium'."
  }
}

variable "public_network_access_enabled" {
  type        = bool
  default     = true
  description = "Whether public network access is enabled. Set to false for prod (requires Premium SKU + Private Endpoint)."
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
