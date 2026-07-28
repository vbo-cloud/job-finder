# ==============================================================================
# Azure OpenAI
# ==============================================================================
# Models:
#   gpt-4o-mini            → Agent 3 (matching analysis, strengths/weaknesses)
#   gpt-5-mini             → Agent 2 (CV analysis: ROME extraction, quality) — see the
#                            prompt-cv-analysis-referentiel-model-upgrade-column-parsing doc.
#                            Deployment was created manually in the Azure portal ahead of this
#                            Terraform entry for testing; imported into state (PR #217) rather
#                            than left for `apply` to create it fresh. That import is history:
#                            the SKU switch below replaces all three deployments regardless
#                            (changing a deployment's sku.name forces destroy+create, same name
#                            — see JOURNAL #263).
#   text-embedding-3-small → Agent 2 (CV and offer embeddings)
# Region: francecentral (data at rest in France). Deployments use the
# DataZoneStandard SKU (below) so inference is processed within the EU data zone
# — CV/user data never leaves the EU (GDPR, ADR-006). GlobalStandard was used
# previously only because regional Standard isn't offered for these models in
# francecentral; DataZoneStandard gives the EU guarantee without routing requests
# worldwide the way GlobalStandard did.

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
      sku_name      = "DataZoneStandard"      # EU data residency: inference stays in the EU data zone (vs GlobalStandard = worldwide routing)
    }
    "gpt-5-mini" = {
      model_name    = "gpt-5-mini"
      model_version = "2025-08-07"
      capacity_tpm  = var.openai_capacity_tpm_gpt5_mini # dedicated: DataZone gpt-5-mini quota is only 670 < the 1M shared default (see variables.tf)
      sku_name      = "DataZoneStandard"
    }
    "text-embedding-3-small" = {
      model_name    = "text-embedding-3-small"
      model_version = "1"
      capacity_tpm  = var.openai_capacity_tpm # 1M TPM by default — update variable to change
      sku_name      = "DataZoneStandard"      # EU data residency (see gpt-4o-mini above)
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
