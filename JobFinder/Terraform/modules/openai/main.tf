# ==============================================================================
# Azure OpenAI Account
# ==============================================================================
resource "azurerm_cognitive_account" "this" {
  name                = var.name
  location            = var.location
  resource_group_name = var.resource_group_name
  kind                = "OpenAI"
  sku_name            = var.sku_name

  # Public access required for agents running outside the VNet (M1).
  # Restrict via private endpoint when self-hosted runners are available.
  public_network_access_enabled = true
  local_auth_enabled            = var.local_auth_enabled

  tags = {
    environment = var.environment
    project     = var.project
    owner       = var.owner
    protect     = "true"
  }

  lifecycle {
    prevent_destroy = true
  }
}

# ==============================================================================
# Model Deployments
# ==============================================================================
resource "azurerm_cognitive_deployment" "this" {
  for_each             = var.deployments
  name                 = each.key
  cognitive_account_id = azurerm_cognitive_account.this.id

  model {
    format  = "OpenAI"
    name    = each.value.model_name
    version = each.value.model_version
  }

  sku {
    name     = each.value.sku_name
    capacity = each.value.capacity_tpm
  }

  rai_policy_name = "Microsoft.DefaultV2"
}
