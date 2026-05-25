# ==============================================================================
# Service Bus
# ==============================================================================
# Queues:
#   offer-ready  — GitHub Actions cron (fetch+embed) → job-matching
#   match-ready  — job-matching → notification utilisateur + futur agent cv-review

module "servicebus" {
  source = "../../modules/servicebus"

  name                = "sb-${var.project}-${var.env}-${var.location_short}"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.rg_app.name
  sku                 = "Standard"
  environment         = var.env
  project             = var.project
  owner               = var.owner

  queues = [
    "offer-ready",
    "match-ready",
  ]
}

# Store connection string in Key Vault for agents to consume
module "secret_servicebus" {
  source       = "../../modules/keyvault_secret"
  name         = "servicebus-connection-string"
  value        = module.servicebus.primary_connection_string
  key_vault_id = module.keyvault.id
  environment  = var.env
  project      = var.project
  owner        = var.owner
}
