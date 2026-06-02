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

# Connection string intentionally not stored in Key Vault —
# agents authenticate via Managed Identity (Azure Service Bus Data Owner on UAMI).
