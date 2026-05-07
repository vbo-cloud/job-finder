# ==============================================================================
# RBAC — Role assignments for sp-jf-github
# ==============================================================================
# Managed here (lz_dev) rather than in iam/ because sp-jf-github now has
# User Access Administrator, allowing the CI/CD pipeline to manage role
# assignments directly without manual intervention.

data "azurerm_key_vault" "app_dev" {
  name                = "kv-jf-dev-frc"
  resource_group_name = "rg-jf-dev-frc-core"
}

data "azurerm_key_vault" "lz_dev" {
  name                = "kv-jf-lz-dev-frc"
  resource_group_name = "rg-jf-lz-dev-frc"
}

data "azurerm_resource_group" "dev_data" {
  name = "rg-jf-dev-frc-data"
}

locals {
  sp_role_assignments = {
    kv_app_secrets_officer = {
      scope                = data.azurerm_key_vault.app_dev.id
      role_definition_name = "Key Vault Secrets Officer"
    }
    kv_lz_secrets_officer = {
      scope                = data.azurerm_key_vault.lz_dev.id
      role_definition_name = "Key Vault Secrets Officer"
    }
    storage_blob_contributor = {
      scope                = data.azurerm_resource_group.dev_data.id
      role_definition_name = "Storage Blob Data Contributor"
    }
  }
}

resource "azurerm_role_assignment" "sp_github" {
  for_each             = local.sp_role_assignments
  scope                = each.value.scope
  role_definition_name = each.value.role_definition_name
  principal_id         = var.sp_github_object_id
}
