# Expose both resource IDs so callers can reference the policy in other modules
# (e.g. to build exemptions, audit queries, or compliance dashboards).

output "policy_definition_id" {
  description = "Resource ID of the policy definition"
  value       = azurerm_policy_definition.allowed_locations.id
}

output "policy_assignment_id" {
  description = "Resource ID of the subscription-level policy assignment"
  value       = azurerm_subscription_policy_assignment.allowed_locations.id
}
