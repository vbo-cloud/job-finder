variable "name" {
  type        = string
  description = "Private endpoint resource name"
}

variable "location" {
  type        = string
  description = "Azure region"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group for the private endpoint"
}

variable "subnet_id" {
  type        = string
  description = "Subnet ID where the private endpoint NIC is placed"
}

variable "private_connection_resource_id" {
  type        = string
  description = "Resource ID of the service to connect to (e.g. storage account, key vault)"
}

variable "subresource_name" {
  type        = string
  description = "Subresource to target (e.g. \"blob\", \"vault\", \"postgresqlServer\")"
}

variable "private_dns_zone_ids" {
  type        = list(string)
  description = "List of private DNS zone IDs to associate via the dns_zone_group"
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
