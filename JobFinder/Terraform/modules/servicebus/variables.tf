variable "name" {
  type        = string
  description = "Name of the Service Bus namespace."
}

variable "location" {
  type        = string
  description = "Azure region where the namespace is deployed."
}

variable "resource_group_name" {
  type        = string
  description = "Name of the resource group that contains the namespace."
}

variable "sku" {
  type        = string
  default     = "Standard"
  description = "SKU of the Service Bus namespace. Basic does not support topics; use Standard or Premium."

  validation {
    condition     = contains(["Basic", "Standard", "Premium"], var.sku)
    error_message = "sku must be 'Basic', 'Standard', or 'Premium'."
  }
}

variable "queues" {
  type        = list(string)
  description = "List of queue names to create inside the namespace."
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
