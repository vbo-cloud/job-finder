# ==============================================================================
# RBAC — Role assignments for sp-jf-github
# ==============================================================================
# Managed here (lz_dev) rather than in iam/ because sp-jf-platform has
# RBAC Administrator, allowing the CI/CD pipeline to manage role assignments
# without manual intervention.

data "azurerm_key_vault" "app_dev" {
  name                = "kv-${var.project}-dev-${var.location_short}"
  resource_group_name = module.rg_core.name
}

data "azurerm_storage_account" "tfstate" {
  name                = "stjftfstatefrc"
  resource_group_name = "rg-jf-tfstate-frc"
}

locals {
  # azurerm_storage_container data source uses the Blob data-plane API and
  # requires listKeys, which sp-jf-platform does not have. Build the ARM
  # resource ID directly from the storage account ID instead.
  app_tfstates_container_id = "${data.azurerm_storage_account.tfstate.id}/blobServices/default/containers/app-tfstates"

  sp_role_assignments = {
    kv_app_secrets_officer = {
      scope                = data.azurerm_key_vault.app_dev.id
      role_definition_name = "Key Vault Secrets Officer"
    }
    # Storage Blob Data Contributor on rg_data: data-plane access to blobs
    # (Contributor below covers control plane but not blob read/write).
    storage_blob_contributor = {
      scope                = module.rg_data.id
      role_definition_name = "Storage Blob Data Contributor"
    }
    tfstate_blob_contributor = {
      scope                = local.app_tfstates_container_id
      role_definition_name = "Storage Blob Data Contributor"
    }
    tfstate_reader = {
      scope                = data.azurerm_storage_account.tfstate.id
      role_definition_name = "Reader"
    }
    lz_rg_reader = {
      scope                = module.rg.id
      role_definition_name = "Reader"
    }
    # Contributor scoped to each app resource group — replaces the former
    # subscription-level Contributor now that lz_dev pre-provisions these RGs.
    rg_core_contributor = {
      scope                = module.rg_core.id
      role_definition_name = "Contributor"
    }
    rg_app_contributor = {
      scope                = module.rg_app.id
      role_definition_name = "Contributor"
    }
    rg_data_contributor = {
      scope                = module.rg_data.id
      role_definition_name = "Contributor"
    }
  }
}

resource "azurerm_role_assignment" "sp_github" {
  for_each             = local.sp_role_assignments
  scope                = each.value.scope
  role_definition_name = each.value.role_definition_name
  principal_id         = var.sp_github_object_id
}

# ==============================================================================
# Managed Identity — Container App Jobs
# ==============================================================================
# Created here (lz_dev) so sp-jf-platform can assign AcrPull directly.
# sp-jf-github (Contributor only) cannot create role assignments.
# Referenced from dev/ via data source on azurerm_user_assigned_identity.

resource "azurerm_user_assigned_identity" "caj" {
  name                = "id-${var.project}-dev-${var.location_short}-caj"
  location            = var.location
  resource_group_name = module.rg_core.name

  tags = {
    environment = var.env
    project     = var.project
    owner       = var.owner
  }
}

data "azurerm_container_registry" "acr" {
  name                = "cr${var.project}dev${var.location_short}"
  resource_group_name = module.rg_app.name
}

resource "azurerm_role_assignment" "caj_acr_pull" {
  scope                = data.azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.caj.principal_id
}
