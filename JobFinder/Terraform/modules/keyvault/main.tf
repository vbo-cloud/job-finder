resource "azurerm_key_vault" "this" {
  name                       = var.name
  location                   = var.location
  resource_group_name        = var.resource_group_name
  tenant_id                  = var.tenant_id
  sku_name                   = var.sku_name
  enable_rbac_authorization  = true
  purge_protection_enabled   = true
  soft_delete_retention_days = var.soft_delete_retention_days
  # Public access is required for GitHub-hosted runners to reach the Key Vault data plane
  # and write secrets via Terraform. Access control is enforced by RBAC
  # (enable_rbac_authorization = true) — network restriction is a defence-in-depth layer,
  # not the primary control. A self-hosted runner inside the VNet would allow disabling
  # public access — see BACKLOG.md.
  public_network_access_enabled = true

  tags = {
    environment = var.environment
    project     = var.project
    owner       = var.owner
    protect     = "true"
  }

  lifecycle {
    prevent_destroy = true
  }
}
