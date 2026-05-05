terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

# Resource names are hardcoded intentionally — iam/ is a narrow-scope manual-apply
# project. If resources are renamed, update these data sources accordingly.
data "azurerm_key_vault" "dev" {
  name                = "kv-jf-dev-frc"
  resource_group_name = "rg-jf-dev-frc-core"
}

data "azurerm_key_vault" "lz_dev" {
  name                = "kv-jf-lz-dev-frc"
  resource_group_name = "rg-jf-lz-dev-frc"
}

locals {
  role_assignments = {
    kv_secrets_officer = {
      scope                = data.azurerm_key_vault.dev.id
      role_definition_name = "Key Vault Secrets Officer"
    }
    kv_lz_secrets_officer = {
      scope                = data.azurerm_key_vault.lz_dev.id
      role_definition_name = "Key Vault Secrets Officer"
    }
  }
}

resource "azurerm_role_assignment" "this" {
  for_each             = local.role_assignments
  scope                = each.value.scope
  role_definition_name = each.value.role_definition_name
  principal_id         = var.sp_object_id
}
