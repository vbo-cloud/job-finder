# ==============================================================================
# Container App
# ==============================================================================
resource "azurerm_container_app" "this" {
  name                         = var.name
  resource_group_name          = var.resource_group_name
  container_app_environment_id = var.environment_id
  revision_mode                = "Single"

  template {
    container {
      name   = var.name
      image  = var.image
      cpu    = var.cpu
      memory = var.memory

      dynamic "env" {
        for_each = var.env_vars
        content {
          name        = env.value.name
          value       = lookup(env.value, "value", null)
          secret_name = lookup(env.value, "secret_name", null)
        }
      }
    }

    min_replicas = var.min_replicas
    max_replicas = var.max_replicas

    # Business-hours mode: min_replicas stays 0 and a KEDA cron rule holds the desired
    # replica count between start and end. The HTTP rule is required alongside it, otherwise
    # nothing wakes the app for a request received outside the window.
    dynamic "custom_scale_rule" {
      for_each = var.active_hours != null ? [var.active_hours] : []
      content {
        name             = "business-hours"
        custom_rule_type = "cron"
        metadata = {
          timezone        = custom_scale_rule.value.timezone
          start           = custom_scale_rule.value.start
          end             = custom_scale_rule.value.end
          desiredReplicas = tostring(custom_scale_rule.value.desired_replicas)
        }
      }
    }

    dynamic "http_scale_rule" {
      for_each = var.active_hours != null ? [1] : []
      content {
        name                = "http-wake-up"
        concurrent_requests = "10"
      }
    }
  }

  dynamic "secret" {
    for_each = var.secrets
    content {
      name  = secret.value.name
      value = secret.value.value
    }
  }

  ingress {
    external_enabled = true
    target_port      = var.target_port
    transport        = "http"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  dynamic "identity" {
    for_each = length(var.identity_ids) > 0 ? [1] : []
    content {
      type         = "UserAssigned"
      identity_ids = var.identity_ids
    }
  }

  dynamic "registry" {
    for_each = var.registry_server != null ? [1] : []
    content {
      server   = var.registry_server
      identity = var.registry_identity
    }
  }

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
