# ==============================================================================
# Resource Groups — data sources only
# ==============================================================================
# Resource groups are provisioned by lz_dev (sp-jf-platform).
# envs/dev reads them as data sources so all resources can reference the same
# name and location outputs without hardcoding strings.

data "azurerm_resource_group" "rg_core" {
  name = "rg-${var.project}-dev-${var.location_short}-core"
}

data "azurerm_resource_group" "rg_app" {
  name = "rg-${var.project}-dev-${var.location_short}-app"
}

data "azurerm_resource_group" "rg_data" {
  name = "rg-${var.project}-dev-${var.location_short}-data"
}

# Remove the module-managed resource groups from dev.tfstate without destroying
# them — ownership transferred to lz_dev. Requires Terraform >= 1.7.
removed {
  from = module.rg_core.azurerm_resource_group.rg
  lifecycle {
    destroy = false
  }
}

removed {
  from = module.rg_app.azurerm_resource_group.rg
  lifecycle {
    destroy = false
  }
}

removed {
  from = module.rg_data.azurerm_resource_group.rg
  lifecycle {
    destroy = false
  }
}
