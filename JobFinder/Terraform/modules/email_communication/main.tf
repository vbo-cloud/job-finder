# ==============================================================================
# Communication Service — parent resource. Its hostname is the endpoint the
# EmailClient SDK connects to, and its resource ID is the RBAC scope for the
# future caj role assignment (PR 6/7 of the notifications plan — cannot be
# granted here, the role assignment's scope must already exist at apply time).
# ==============================================================================
resource "azurerm_communication_service" "this" {
  name                = var.communication_service_name
  resource_group_name = var.resource_group_name
  data_location       = var.data_location

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
# Email Communication Service
# ==============================================================================
resource "azurerm_email_communication_service" "this" {
  name                = var.email_service_name
  resource_group_name = var.resource_group_name
  data_location       = var.data_location

  tags = {
    environment = var.environment
    project     = var.project
    owner       = var.owner
  }
}

# ==============================================================================
# Custom domain — CustomerManaged: Azure does not configure DNS. Ownership is
# proven by adding the DNS records exposed by this resource's
# verification_records attribute (see this module's outputs.tf) manually at
# the domain's DNS host. Protected: re-verifying a domain after an accidental
# destroy means redoing that manual DNS step, not just a terraform apply.
# ==============================================================================
resource "azurerm_email_communication_service_domain" "this" {
  name              = var.domain_name
  email_service_id  = azurerm_email_communication_service.this.id
  domain_management = "CustomerManaged"

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
# Sender username — the local part of the "From" address.
# ==============================================================================
resource "azurerm_email_communication_service_domain_sender_username" "this" {
  name                    = var.sender_username
  email_service_domain_id = azurerm_email_communication_service_domain.this.id
  display_name            = var.sender_display_name
}

# ==============================================================================
# Link the domain to the Communication Service — without this, the parent
# resource cannot send through this domain even once it shows Verified.
# ==============================================================================
resource "azurerm_communication_service_email_domain_association" "this" {
  communication_service_id = azurerm_communication_service.this.id
  email_service_domain_id  = azurerm_email_communication_service_domain.this.id
}
