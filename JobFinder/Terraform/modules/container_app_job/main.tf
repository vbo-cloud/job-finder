# ==============================================================================
# Container App Job
# ==============================================================================
resource "azurerm_container_app_job" "this" {
  name                         = var.name
  location                     = var.location
  resource_group_name          = var.resource_group_name
  container_app_environment_id = var.environment_id
  workload_profile_name        = "Consumption"

  replica_timeout_in_seconds = var.replica_timeout_in_seconds
  replica_retry_limit        = var.replica_retry_limit

  # ==============================================================================
  # Trigger
  # ==============================================================================
  dynamic "schedule_trigger_config" {
    for_each = var.trigger_type == "timer" ? [1] : []
    content {
      cron_expression          = var.cron_expression
      parallelism              = 1
      replica_completion_count = 1
    }
  }

  dynamic "event_trigger_config" {
    for_each = var.trigger_type == "queue" ? [1] : []
    content {
      parallelism              = 1
      replica_completion_count = 1

      scale {
        min_executions              = 0
        max_executions              = var.max_executions
        polling_interval_in_seconds = var.polling_interval_in_seconds

        rules {
          name             = "queue-trigger"
          custom_rule_type = "azure-servicebus"
          metadata = merge(
            {
              queueName    = var.queue_name
              namespace    = var.servicebus_namespace
              messageCount = "1"
            },
            var.uami_client_id != null ? { clientId = var.uami_client_id, tenantId = var.uami_tenant_id } : {}
          )

          dynamic "authentication" {
            for_each = var.uami_client_id == null ? [1] : []
            content {
              secret_name       = "servicebus-connection-string"
              trigger_parameter = "connection"
            }
          }
        }
      }
    }
  }

  # ==============================================================================
  # Container
  # ==============================================================================
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
          value       = env.value.value
          secret_name = env.value.secret_name
        }
      }
    }
  }

  # ==============================================================================
  # Secrets
  # ==============================================================================
  dynamic "secret" {
    for_each = var.secrets
    content {
      name  = secret.value.name
      value = secret.value.value
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
  }
}
