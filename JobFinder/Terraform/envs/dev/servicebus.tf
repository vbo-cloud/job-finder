# ==============================================================================
# Service Bus
# ==============================================================================
# Queues:
#   offer-ready  — agent cv-analysis → job-matching
#   match-ready  — job-matching → notification utilisateur + futur agent cv-review
#   cv-analysis  — POST /cv/upload → agent cv-analysis (extrait les codes ROME)

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
    "cv-analysis",
  ]
}

module "secret_servicebus_connection_string" {
  source       = "../../modules/keyvault_secret"
  name         = "servicebus-connection-string"
  value        = module.servicebus.primary_connection_string
  key_vault_id = module.keyvault.id
  content_type = "text/plain"
  environment  = var.env
  project      = var.project
  owner        = var.owner
}
