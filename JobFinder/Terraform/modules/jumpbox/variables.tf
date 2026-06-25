variable "name" {
  description = "Name of the virtual machine."
  type        = string
}

variable "location" {
  description = "Azure region where the VM is deployed."
  type        = string
}

variable "resource_group_name" {
  description = "Name of the resource group that contains the VM."
  type        = string
}

variable "subnet_id" {
  description = "Resource ID of the subnet to attach the VM NIC to."
  type        = string
}

variable "vm_size" {
  description = "Azure VM SKU. Defaults to Standard_B2s (2 vCPU, 4 GB RAM) — Standard_B1ms is unavailable in France Central."
  type        = string
  default     = "Standard_B2s"
}

variable "admin_username" {
  description = "Linux admin username for SSH access via Bastion."
  type        = string
  default     = "azureuser"
}

variable "admin_password" {
  description = "Password for the admin user. Use a randomly generated value stored in Key Vault."
  type        = string
  sensitive   = true
}

variable "auto_shutdown_time" {
  description = "Daily auto-shutdown time in UTC (format: HHMM). The VM is deallocated at this time every day as a cost safety net."
  type        = string
  default     = "2000"

  validation {
    condition     = can(regex("^([01][0-9]|2[0-3])[0-5][0-9]$", var.auto_shutdown_time))
    error_message = "auto_shutdown_time must be in HHMM format (e.g. '2000' for 20:00 UTC)."
  }
}

variable "environment" {
  description = "Environment name used for tagging (e.g. dev, prod)."
  type        = string
}

variable "project" {
  description = "Project identifier used for tagging."
  type        = string
}

variable "owner" {
  description = "Owner identifier used for tagging."
  type        = string
}
