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

output "frontend_url" {
  description = "Public URL of the Next.js frontend Container App (default *.azurecontainerapps.io FQDN, before custom domain binding)."
  value       = module.frontend.fqdn
}

output "container_app_environment_custom_domain_verification_id" {
  description = "Verification ID to publish as the asuid.<subdomain> TXT record at the DNS registrar before binding a custom domain to the frontend Container App."
  value       = module.container_app_environment.custom_domain_verification_id
}

output "frontend_custom_domain" {
  description = "Target custom domain for the frontend Container App (not yet bound -- see BACKLOG.md). Read alongside frontend_url and container_app_environment_custom_domain_verification_id to build the TXT/CNAME records at the DNS registrar."
  value       = var.frontend_custom_domain
}

output "jumpbox_private_ip" {
  description = "Private IP of the jumpbox VM (connect via Azure Bastion)."
  value       = module.jumpbox.private_ip
}

output "action_group_id" {
  description = "Resource ID of the owner alert action group."
  value       = azurerm_monitor_action_group.owner.id
}
