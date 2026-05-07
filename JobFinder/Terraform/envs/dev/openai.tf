# ==============================================================================
# Azure OpenAI
# ==============================================================================
# Models:
#   gpt-4o-mini            → Agent 3 (matching analysis, strengths/weaknesses)
#   text-embedding-3-small → Agent 2 (CV and offer embeddings)
# Region: francecentral — GDPR compliance, CV/user data stays in EU (ADR-006)

module "openai" {
  source = "../../modules/openai"

  name                = "oai-${var.project}-${var.env}-${var.location_short}"
  location            = var.location
  resource_group_name = module.rg_app.name
  environment         = var.env
  project             = var.project
  owner               = var.owner

  deployments = {
    "gpt-4o-mini" = {
      model_name    = "gpt-4o-mini"
      model_version = "2024-07-18"
      capacity_tpm  = 10 # 10K tokens per minute — sufficient for dev
    }
    "text-embedding-3-small" = {
      model_name    = "text-embedding-3-small"
      model_version = "1"
      capacity_tpm  = 10
    }
  }
}

module "secret_openai_key" {
  source       = "../../modules/keyvault_secret"
  name         = "openai-api-key"
  value        = module.openai.primary_key
  key_vault_id = module.keyvault.id
  content_type = "text/plain"
  environment  = var.env
  project      = var.project
  owner        = var.owner
}

module "secret_openai_endpoint" {
  source       = "../../modules/keyvault_secret"
  name         = "openai-endpoint"
  value        = module.openai.endpoint
  key_vault_id = module.keyvault.id
  content_type = "text/plain"
  environment  = var.env
  project      = var.project
  owner        = var.owner
}
