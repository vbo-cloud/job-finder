# ==============================================================================
# Service Bus
# ==============================================================================
# Queues:
#   offer-ready  — Agent 1 (offer fetching) → Agent 2 (embedding)
#   cv-ready     — user CV upload           → Agent 2 (embedding)
#   match-ready  — Agent 2 (embedding)      → Agent 3 (matching + email)
# Agent 4 (daily cleanup) is timer-triggered and does not use queues.

module "servicebus" {
  source = "../../modules/servicebus"

  name                = "sb-${var.project}-${var.environment}-${var.location_short}"
  location            = var.location
  resource_group_name = azurerm_resource_group.rg_app.name
  sku                 = "Standard"
  environment         = var.environment
  project             = var.project
  owner               = var.owner

  queues = [
    "offer-ready",
    "cv-ready",
    "match-ready",
  ]
}

# Store connection string in Key Vault for agents to consume
resource "azurerm_key_vault_secret" "servicebus_connection_string" {
  name         = "servicebus-connection-string"
  value        = module.servicebus.primary_connection_string
  key_vault_id = module.keyvault.id
}
