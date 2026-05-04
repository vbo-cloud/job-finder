terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

# ==============================================================================
# Admin Password
# ==============================================================================

resource "random_password" "admin" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
  min_lower        = 2
  min_upper        = 2
  min_numeric      = 2
  min_special      = 2
}

# ==============================================================================
# Flexible Server
# ==============================================================================

resource "azurerm_postgresql_flexible_server" "this" {
  name                = var.name
  location            = var.location
  resource_group_name = var.resource_group_name
  version             = "16"
  sku_name            = var.sku_name
  storage_mb          = 32768

  administrator_login    = var.administrator_login
  administrator_password = random_password.admin.result

  # VNet injection mode — no public endpoint, traffic stays on the private subnet.
  delegated_subnet_id = var.delegated_subnet_id
  private_dns_zone_id = var.private_dns_zone_id
  # Required when using delegated_subnet_id — Azure enforces private-only access with VNet integration.
  public_network_access_enabled = false

  backup_retention_days        = var.backup_retention_days
  geo_redundant_backup_enabled = var.geo_redundant_backup_enabled

  tags = {
    environment = var.environment
    project     = var.project
    owner       = var.owner
  }

  lifecycle {
    prevent_destroy = true
    ignore_changes = [zone] 
  }
}

resource "azurerm_postgresql_flexible_server_database" "jobfinder" {
  name      = "jobfinder"
  server_id = azurerm_postgresql_flexible_server.this.id
  charset   = "UTF8"
  collation = "en_US.utf8"

  lifecycle {
    prevent_destroy = true
  }
}

# Enable pgvector — required for the AI similarity-search features of job-finder.
resource "azurerm_postgresql_flexible_server_configuration" "vector" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.this.id
  value     = "VECTOR"
}

# ==============================================================================
# Key Vault Secret
# ==============================================================================

resource "azurerm_key_vault_secret" "connection_string" {
  name         = "postgresql-connection-string"
  key_vault_id = var.key_vault_id
  value        = "postgresql://${var.administrator_login}:${random_password.admin.result}@${azurerm_postgresql_flexible_server.this.fqdn}/jobfinder?sslmode=require"

  tags = {
    environment = var.environment
    project     = var.project
    owner       = var.owner
  }
}
