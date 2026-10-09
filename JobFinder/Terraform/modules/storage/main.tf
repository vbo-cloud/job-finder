resource "azurerm_storage_account" "this" {
  name                             = var.name
  resource_group_name              = var.resource_group_name
  location                         = var.location
  account_tier                     = "Standard"
  account_replication_type         = "LRS"
  min_tls_version                  = "TLS1_2"
  allow_nested_items_to_be_public  = false
  cross_tenant_replication_enabled = false
  # Public access kept on for the GitHub-hosted runners. Not for azurerm_storage_container:
  # with storage_account_id it goes through the ARM API, not the blob data plane. What remains to
  # be settled is blob_properties below (see BACKLOG.md). No private endpoint is attached (removed
  # in PR #269: it isolated nothing while this stays true); re-add it when closing public access
  # once a self-hosted runner in the VNet exists.
  public_network_access_enabled = true

  blob_properties {
    delete_retention_policy {
      days = 7
    }
    container_delete_retention_policy {
      days = 7
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
