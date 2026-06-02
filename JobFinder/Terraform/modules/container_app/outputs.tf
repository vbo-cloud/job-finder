output "id" {
  description = "Resource ID of the Container App."
  value       = azurerm_container_app.this.id
}

output "fqdn" {
  # latest_revision_fqdn is revision-specific but stable in Single revision mode:
  # each new deployment replaces the active revision in place, keeping the URL unchanged.
  description = "Public HTTPS URL of the Container App (stable in Single revision mode)."
  value       = "https://${azurerm_container_app.this.latest_revision_fqdn}"
}
