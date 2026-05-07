# ==============================================================================
# Policy — Auto-lock resources tagged protect=true
# ==============================================================================

locals {
  auto_lock_policy_rule = {
    if = {
      field  = "tags['protect']"
      equals = "true"
    }
    then = {
      effect = "deployIfNotExists"
      details = {
        type = "Microsoft.Authorization/locks"
        existenceCondition = {
          field  = "Microsoft.Authorization/locks/level"
          equals = "CanNotDelete"
        }
        roleDefinitionIds = [
          "/providers/Microsoft.Authorization/roleDefinitions/8e3af657-a8ff-443c-a75c-2fe8c4bcb635"
        ]
        deployment = {
          properties = {
            mode = "incremental"
            parameters = {
              resourceName = { value = "[field('name')]" }
              resourceType = { value = "[field('type')]" }
            }
            template = {
              "$schema"      = "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#"
              contentVersion = "1.0.0.0"
              parameters = {
                resourceName = { type = "string" }
                resourceType = { type = "string" }
              }
              resources = [
                {
                  type       = "Microsoft.Authorization/locks"
                  apiVersion = "2016-09-01"
                  name       = "auto-lock-cannotdelete"
                  scope      = "[concat(parameters('resourceType'), '/', parameters('resourceName'))]"
                  properties = {
                    level = "CanNotDelete"
                    notes = "Auto-applied by policy on resources tagged protect=true. Remove tag or lock manually before destroying."
                  }
                }
              ]
            }
          }
        }
      }
    }
  }
}

resource "azurerm_policy_definition" "auto_lock" {
  name         = "jf-auto-lock-protect-tagged"
  policy_type  = "Custom"
  mode         = "All"
  display_name = "Auto-lock resources tagged protect=true"
  description  = "Deploys a CanNotDelete lock on any resource tagged protect=true if one does not already exist."

  metadata = jsonencode({
    environment = "lz-dev"
    project     = var.project
    owner       = var.owner
  })

  policy_rule = jsonencode(local.auto_lock_policy_rule)

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_subscription_policy_assignment" "auto_lock" {
  name                 = "jf-auto-lock-protect-tagged"
  display_name         = "Auto-lock protect=true resources"
  policy_definition_id = azurerm_policy_definition.auto_lock.id
  subscription_id      = "/subscriptions/${data.azurerm_client_config.current.subscription_id}"
  location             = var.location

  identity {
    type = "SystemAssigned"
  }

  metadata = jsonencode({
    environment = "lz-dev"
    project     = var.project
    owner       = var.owner
  })

  lifecycle {
    prevent_destroy = true
  }
}
