variable "name" {
  type        = string
  description = "Subnet name"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group containing the VNet"
}

variable "virtual_network_name" {
  type        = string
  description = "Name of the parent virtual network"
}

variable "address_prefixes" {
  type        = list(string)
  description = "CIDR address prefixes for the subnet"
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

variable "delegation_name" {
  type        = string
  description = "Name of the delegation block (null = no delegation)"
  default     = null
}

variable "delegation_service" {
  type        = string
  description = "Service to delegate to (e.g. Microsoft.DBforPostgreSQL/flexibleServers)"
  default     = null

  validation {
    condition     = var.delegation_name == null || var.delegation_service != null
    error_message = "delegation_service must be set when delegation_name is provided."
  }
}

variable "delegation_actions" {
  type        = list(string)
  description = "List of actions granted to the delegated service"
  default     = []
}
