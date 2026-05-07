output "policy_definition_id" {
  description = "Resource ID of the auto-lock policy definition"
  value       = azurerm_policy_definition.this.id
}

output "policy_assignment_id" {
  description = "Resource ID of the subscription-level auto-lock policy assignment"
  value       = azurerm_subscription_policy_assignment.this.id
}
