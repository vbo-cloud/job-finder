resource "azurerm_subnet" "this" {
  name                              = var.name
  resource_group_name               = var.resource_group_name
  virtual_network_name              = var.virtual_network_name
  address_prefixes                  = var.address_prefixes
  private_endpoint_network_policies = "Enabled"

  dynamic "delegation" {
    for_each = var.delegation_name != null ? [1] : []
    content {
      name = var.delegation_name
      service_delegation {
        name    = var.delegation_service
        actions = var.delegation_actions
      }
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}
