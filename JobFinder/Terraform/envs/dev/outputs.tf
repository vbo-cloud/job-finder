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

output "jumpbox_ssh_command" {
  description = "SSH command to connect to the jumpbox VM."
  value       = module.jumpbox.ssh_command
}

output "jumpbox_public_ip" {
  description = "Public IP of the jumpbox VM."
  value       = module.jumpbox.public_ip
}
