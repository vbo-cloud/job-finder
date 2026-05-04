variable "name" {
  type        = string
  description = "PostgreSQL Flexible Server name"
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

variable "key_vault_id" {
  type        = string
  description = "Resource ID of the Key Vault where the connection string secret will be stored"
}

variable "delegated_subnet_id" {
  type        = string
  description = "Resource ID of the subnet delegated to Microsoft.DBforPostgreSQL/flexibleServers"
}

variable "private_dns_zone_id" {
  type        = string
  description = "Resource ID of the private DNS zone (privatelink.postgres.database.azure.com)"
}

variable "administrator_login" {
  type        = string
  description = "Administrator login name for the PostgreSQL server"
  default     = "pgadmin"
}

variable "sku_name" {
  type        = string
  description = "SKU name for the PostgreSQL Flexible Server (e.g. B_Standard_B1ms)"
  default     = "B_Standard_B1ms"
}

variable "backup_retention_days" {
  type        = number
  description = "Backup retention in days (7-35)"
  default     = 7
}

variable "geo_redundant_backup_enabled" {
  type        = bool
  description = "Enable geo-redundant backup (not available on Burstable tier)"
  default     = false
}
