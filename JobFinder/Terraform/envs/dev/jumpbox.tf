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

module "jumpbox" {
  source = "../../modules/jumpbox"

  name                = "vm-${var.project}-dev-${var.location_short}-mgmt-001"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.rg_app.name

  subnet_id      = data.azurerm_subnet.lz_vnet_mgmt.id
  admin_password = random_password.jumpbox_admin.result

  environment = var.env
  project     = var.project
  owner       = var.owner
}
