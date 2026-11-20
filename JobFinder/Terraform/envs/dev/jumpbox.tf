# ==============================================================================
# Jumpbox VM
# ==============================================================================

resource "random_password" "jumpbox_admin" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>?"
}

module "jumpbox_admin_password" {
  source       = "../../modules/keyvault_secret"
  name         = "jumpbox-admin-password"
  value        = random_password.jumpbox_admin.result
  key_vault_id = module.keyvault.id
  environment  = var.env
  project      = var.project
  owner        = var.owner
}

# Disabled by default (var.enable_jumpbox = false): the deallocated VM still billed its OS disk
# (~1.5 EUR/month). Set to true to recreate it; the admin password above is kept in Key Vault.
module "jumpbox" {
  count  = var.enable_jumpbox ? 1 : 0
  source = "../../modules/jumpbox"

  name                = "vm-${var.project}-dev-${var.location_short}-mgmt-001"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.rg_app.name

  subnet_id      = data.azurerm_subnet.lz_vnet_mgmt.id
  admin_password = module.jumpbox_admin_password.value

  environment = var.env
  project     = var.project
  owner       = var.owner
}
