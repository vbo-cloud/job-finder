# Module: resource_group
# Thin wrapper around azurerm_resource_group. Using a module instead of inline resources
# ensures consistent tagging and naming enforcement in one place as the project grows,
# and lets future changes (e.g. adding resource locks) propagate everywhere automatically.

resource "azurerm_resource_group" "rg" {
  name     = var.name
  location = var.location

  tags = {
    environment = var.environment
    project     = var.project
    owner       = var.owner
  }
}
