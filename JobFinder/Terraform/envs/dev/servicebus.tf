# ==============================================================================
# Service Bus
# ==============================================================================
# Queues:
#   start-matching            — agent offer-fetching (offres neuves embedées) + profile.py (changement
#                              d'intention) + agent cv-analysis (nouveau CV) → job-matching
#                              (renommage de offer-ready : granularité par événement déclencheur,
#                              jamais par offre — voir docs/prompts/prompt-remove-offer-distillation.md)
#   match-ready               — job-matching → notification utilisateur
#   cv-analysis               — POST /cv/upload → agent cv-analysis (codes ROME + qualité du CV)
#   match-analysis            — job-matching (top N auto) + POST /matches/.../analyze → agent match-analysis
#   offer-fetch-request       — offer_fetch_scheduler (relais planifié 12h/20h) + agent cv-analysis
#                              (nouveau code ROME mergé sur un profil) → job-offer-fetching
#                              (event-driven, voir docs/prompts/prompt-offer-fetching-event-driven-
#                              and-new-code-fetch.md)

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
    "start-matching",
    "match-ready",
    "cv-analysis",
    "match-analysis",
    "offer-fetch-request",
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
