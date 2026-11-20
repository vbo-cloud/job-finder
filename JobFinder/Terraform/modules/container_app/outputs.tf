output "id" {
  description = "Resource ID of the Container App."
  value       = azurerm_container_app.this.id
}

output "fqdn" {
  # ingress[0].fqdn is the app-level hostname, distinct from latest_revision_fqdn
  # (revision-specific, e.g. app--0000003.<env>...). A prior version of this output
  # used latest_revision_fqdn with a comment claiming it was "stable in Single
  # revision mode" -- disproved by an observed terraform plan where an unrelated
  # attribute change alone bumped the revision suffix. Anything depending on this
  # output staying constant (e.g. an externally-configured DNS CNAME) must use
  # ingress[0].fqdn, not the revision-specific value.
  description = "Public HTTPS URL of the Container App (stable across revisions)."
  value       = "https://${azurerm_container_app.this.ingress[0].fqdn}"
}
