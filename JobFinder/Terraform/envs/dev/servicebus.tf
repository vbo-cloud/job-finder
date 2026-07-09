# ==============================================================================
# Service Bus
# ==============================================================================
# Queues:
#   distillate-offer-fetched — agent offer-fetching (une fois par offre à distiller) → agent
#                              offer-distillation (distillation LLM puis embedding, un message par offer_id)
#   start-matching           — profile.py (changement d'intention) + agent cv-analysis (nouveau CV) +
#                              agent matching-heartbeat (timer de rattrapage) → job-matching
#                              (renommage de offer-ready : granularité par événement déclencheur,
#                              jamais par offre — voir docs/prompts/prompt-offer-distillation-pipeline.md)
#   match-ready               — job-matching → notification utilisateur
#   cv-analysis               — POST /cv/upload → agent cv-analysis (codes ROME + qualité du CV)
#   match-analysis            — job-matching (top N auto) + POST /matches/.../analyze → agent match-analysis

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
    "distillate-offer-fetched",
    "start-matching",
    "match-ready",
    "cv-analysis",
    "match-analysis",
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
