# ==============================================================================
# Network Interface
# ==============================================================================

# Private IP only — access via Azure Bastion Developer (no public endpoint needed).
resource "azurerm_network_interface" "this" {
  name                = "nic-${var.name}"
  location            = var.location
  resource_group_name = var.resource_group_name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = var.subnet_id
    private_ip_address_allocation = "Dynamic"
  }

  tags = {
    environment = var.environment
    project     = var.project
    owner       = var.owner
  }
}

# ==============================================================================
# Virtual Machine
# ==============================================================================

locals {
  cloud_init = <<-EOT
    #cloud-config
    packages:
      - postgresql-client
  EOT
}

resource "azurerm_linux_virtual_machine" "this" {
  name                = var.name
  location            = var.location
  resource_group_name = var.resource_group_name
  size                = var.vm_size
  admin_username      = var.admin_username
  custom_data         = base64encode(local.cloud_init)

  zone                            = "2"
  network_interface_ids           = [azurerm_network_interface.this.id]
  disable_password_authentication = false
  admin_password                  = var.admin_password

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
    disk_size_gb         = 30
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }

  tags = {
    environment = var.environment
    project     = var.project
    owner       = var.owner
  }
}

# ==============================================================================
# Auto-shutdown schedule — daily cost safety net
# ==============================================================================

resource "azurerm_dev_test_global_vm_shutdown_schedule" "this" {
  virtual_machine_id    = azurerm_linux_virtual_machine.this.id
  location              = var.location
  enabled               = true
  daily_recurrence_time = var.auto_shutdown_time
  timezone              = "UTC"

  notification_settings {
    enabled = false
  }
}
