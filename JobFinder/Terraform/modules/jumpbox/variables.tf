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
  description = "Azure VM SKU. Defaults to Standard_B1ms (1 vCPU, 2 GB RAM)."
  type        = string
  default     = "Standard_B1ms"
}

variable "admin_username" {
  description = "Linux admin username for SSH access."
  type        = string
  default     = "azureuser"
}

variable "admin_ssh_public_key" {
  description = "SSH public key content (authorized_keys format) for the admin user."
  type        = string
  sensitive   = true
}

variable "allowed_ssh_cidr_blocks" {
  description = "List of CIDR blocks allowed to connect via SSH (port 22). Restrict to known IPs."
  type        = list(string)

  validation {
    condition     = length(var.allowed_ssh_cidr_blocks) > 0
    error_message = "At least one CIDR block must be provided for SSH access."
  }
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
