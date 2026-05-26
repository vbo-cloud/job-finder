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

data "azurerm_key_vault" "lz_dev" {
  name                = "kv-${var.project}-lz-dev-${var.location_short}"
  resource_group_name = module.rg.name
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
    kv_lz_secrets_officer = {
      scope                = data.azurerm_key_vault.lz_dev.id
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

# RBAC Administrator (conditioned) scoped to each dev resource group.
# Allows sp-jf-github to create role assignments within dev/ (e.g. AcrPull
# for Container App Jobs) without requiring sp-jf-platform for app-level RBAC.
# Same condition as sp-jf-platform: cannot assign Owner, User Access Administrator,
# or Role Based Access Control Administrator.
locals {
  sp_github_rbac_admin_scopes = {
    rg_core = module.rg_core.id
    rg_app  = module.rg_app.id
    rg_data = module.rg_data.id
  }

  rbac_admin_condition = "((!(ActionMatches{'Microsoft.Authorization/roleAssignments/write'})) OR (@Request[Microsoft.Authorization/roleAssignments:RoleDefinitionId] ForAnyOfAllValues:GuidNotEquals {8e3af657-a8ff-443c-a75c-2fe8c4bcb635, 18d7d88d-d35e-4fb5-a5c3-7773c20a72d9, f58310d9-a9f6-439a-9e8d-f62e7b41a168})) AND ((!(ActionMatches{'Microsoft.Authorization/roleAssignments/delete'})) OR (@Resource[Microsoft.Authorization/roleAssignments:RoleDefinitionId] ForAnyOfAllValues:GuidNotEquals {8e3af657-a8ff-443c-a75c-2fe8c4bcb635, 18d7d88d-d35e-4fb5-a5c3-7773c20a72d9, f58310d9-a9f6-439a-9e8d-f62e7b41a168}))"
}

resource "azurerm_role_assignment" "sp_github_rbac_admin" {
  for_each             = local.sp_github_rbac_admin_scopes
  scope                = each.value
  role_definition_name = "Role Based Access Control Administrator"
  principal_id         = var.sp_github_object_id
  condition_version    = "2.0"
  condition            = local.rbac_admin_condition
}
