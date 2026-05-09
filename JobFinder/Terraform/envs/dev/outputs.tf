output "servicebus_namespace_name" {
  description = "Name of the Service Bus namespace, for use by agent infrastructure."
  value       = module.servicebus.name
}

output "servicebus_namespace_id" {
  description = "Resource ID of the Service Bus namespace."
  value       = module.servicebus.id
}
