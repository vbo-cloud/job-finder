# Module: policy/allowed-locations
# Enforces an Azure Policy that denies resource deployment outside of approved regions.
# Scoped at subscription level so all resource groups — current and future — are covered
# without needing per-RG assignments.

# Custom policy definition is used instead of the built-in "Allowed locations" because
# mode = "All" enforces on both resources AND resource groups. The built-in only covers
# resources (mode = "Indexed"), which allows resource groups to be created in any region.
resource "azurerm_policy_definition" "allowed_locations" {
  name         = "pd-${var.project}-${var.environment}-${var.location_short}-allowed-locations"
  policy_type  = "Custom"
  mode         = "All"
  display_name = "Allowed locations - ${var.environment}"
  description  = "Denies deployments outside of allowed Azure regions: ${join(", ", var.allowed_locations)}."

  metadata = jsonencode({
    category = "General"
  })

  policy_rule = jsonencode({
    if = {
      not = {
        field = "location"
        in    = var.allowed_locations
      }
    }
    then = {
      effect = "Deny"
    }
  })

  # Prevent accidental destruction — removing the definition would silently unblock
  # deployments to restricted regions across the entire subscription.
  lifecycle {
    prevent_destroy = true
  }
}

# Subscription ID is resolved from the active OIDC session — no need to pass it explicitly.
data "azurerm_client_config" "current" {}

# Subscription-level assignment: one assignment covers all resource groups, including
# ones created after this policy is applied. Per-RG assignments would require a new
# assignment for each resource group, which is error-prone at scale.
resource "azurerm_subscription_policy_assignment" "allowed_locations" {
  name                 = "pa-${var.project}-${var.environment}-${var.location_short}-allowed-locations"
  display_name         = "Allowed locations - ${var.environment}"
  policy_definition_id = azurerm_policy_definition.allowed_locations.id
  subscription_id      = "/subscriptions/${data.azurerm_client_config.current.subscription_id}"
  not_scopes           = var.not_scopes

  # Tags embedded in metadata — azurerm_subscription_policy_assignment has no tags block
  metadata = jsonencode(var.tags)

  # Same rationale as the definition: removing the assignment silently disables enforcement.
  lifecycle {
    prevent_destroy = true
  }
}
