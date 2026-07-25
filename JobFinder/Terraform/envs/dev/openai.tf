# ==============================================================================
# Azure OpenAI
# ==============================================================================
# Models:
#   gpt-4o-mini            → Agent 3 (matching analysis, strengths/weaknesses)
#   gpt-5-mini             → Agent 2 (CV analysis: ROME extraction, quality) — see the
#                            prompt-cv-analysis-referentiel-model-upgrade-column-parsing doc.
#                            Deployment was created manually in the Azure portal ahead of this
#                            Terraform entry for testing; imported into state rather than left
#                            for `apply` to (re)create.
#   text-embedding-3-small → Agent 2 (CV and offer embeddings)
# Region: francecentral — GDPR compliance, CV/user data stays in EU (ADR-006)

module "openai" {
  source = "../../modules/openai"

  name                = "oai-${var.project}-${var.env}-${var.location_short}"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.rg_app.name
  environment         = var.env
  project             = var.project
  owner               = var.owner
  local_auth_enabled  = false

  deployments = {
    "gpt-4o-mini" = {
      model_name    = "gpt-4o-mini"
      model_version = "2024-07-18"
      capacity_tpm  = var.openai_capacity_tpm # 1M TPM by default — update variable to change
      sku_name      = "GlobalStandard"        # Standard not yet available in francecentral for this model
    }
    "gpt-5-mini" = {
      model_name    = "gpt-5-mini"
      model_version = "2025-08-07"
      capacity_tpm  = var.openai_capacity_tpm # shared variable — no dedicated quota for this model
      sku_name      = "GlobalStandard"
    }
    "text-embedding-3-small" = {
      model_name    = "text-embedding-3-small"
      model_version = "1"
      capacity_tpm  = var.openai_capacity_tpm # 1M TPM by default — update variable to change
      sku_name      = "GlobalStandard"        # Standard not yet available in francecentral for this model
    }
  }
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
