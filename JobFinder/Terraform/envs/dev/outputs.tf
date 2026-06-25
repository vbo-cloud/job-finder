output "servicebus_namespace_name" {
  description = "Name of the Service Bus namespace, for use by agent infrastructure."
  value       = module.servicebus.name
}

output "servicebus_namespace_id" {
  description = "Resource ID of the Service Bus namespace."
  value       = module.servicebus.id
}

output "webapp_url" {
  description = "Public URL of the FastAPI webapp Container App."
  value       = module.webapp.fqdn
}

output "jumpbox_private_ip" {
  description = "Private IP of the jumpbox VM (connect via Azure Bastion)."
  value       = module.jumpbox.private_ip
}
