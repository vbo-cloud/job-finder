# ==============================================================================
# Service Bus Namespace
# ==============================================================================
resource "azurerm_servicebus_namespace" "this" {
  name                = var.name
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = var.sku

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
# Queues
# ==============================================================================
resource "azurerm_servicebus_queue" "this" {
  for_each     = toset(var.queues)
  name         = each.value
  namespace_id = azurerm_servicebus_namespace.this.id

  # Messages kept 7 days if not consumed
  default_message_ttl = "P7D"

  # Dead-letter after 10 failed delivery attempts
  max_delivery_count = 10

  enable_dead_lettering_on_message_expiration = true
}
