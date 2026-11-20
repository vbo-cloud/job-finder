output "communication_service_id" {
  description = "Resource ID of the Communication Service — the RBAC scope for PR 6/7 (role for caj)."
  value       = azurerm_communication_service.this.id
}

output "hostname" {
  description = "Data-plane hostname the EmailClient SDK connects to (endpoint = https://<hostname>) — needed by PR 7/7's agent."
  value       = azurerm_communication_service.this.hostname
}

output "sender_address" {
  description = "Full sender address for the notification agent's From header (e.g. jobfinder@vincentboutin.dev)."
  value       = "${var.sender_username}@${var.domain_name}"
}

output "verification_records" {
  description = "DNS records to add manually at the domain's DNS host to prove ownership and enable sending (Domain, DKIM, DKIM2, SPF, DMARC). DMARC has a known upstream provider issue (hashicorp/terraform-provider-azurerm#29731) where it can come back empty — check the Azure portal directly if so."
  value       = azurerm_email_communication_service_domain.this.verification_records
}
