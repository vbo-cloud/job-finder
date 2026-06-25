# ==============================================================================
# Jumpbox VM
# ==============================================================================

module "jumpbox" {
  source = "../../modules/jumpbox"

  name                = "vm-${var.project}-dev-${var.location_short}-mgmt-001"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.rg_app.name

  subnet_id            = data.azurerm_subnet.lz_vnet_mgmt.id
  admin_ssh_public_key = var.jumpbox_ssh_public_key

  environment = var.env
  project     = var.project
  owner       = var.owner
}
