# ==============================================================================
# Public IP
# ==============================================================================

resource "azurerm_public_ip" "this" {
  name                = "pip-${var.name}"
  location            = var.location
  resource_group_name = var.resource_group_name
  allocation_method   = "Static"
  sku                 = "Standard"

  tags = {
    environment = var.environment
    project     = var.project
    owner       = var.owner
  }
}

# ==============================================================================
# Network Security Group
# ==============================================================================

resource "azurerm_network_security_group" "this" {
  name                = "nsg-${var.name}"
  location            = var.location
  resource_group_name = var.resource_group_name

  security_rule {
    name                       = "AllowSSH"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefixes    = var.allowed_ssh_cidr_blocks
    destination_address_prefix = "*"
  }

  tags = {
    environment = var.environment
    project     = var.project
    owner       = var.owner
  }
}

# ==============================================================================
# Network Interface
# ==============================================================================

resource "azurerm_network_interface" "this" {
  name                = "nic-${var.name}"
  location            = var.location
  resource_group_name = var.resource_group_name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = var.subnet_id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.this.id
  }

  tags = {
    environment = var.environment
    project     = var.project
    owner       = var.owner
  }
}

resource "azurerm_network_interface_security_group_association" "this" {
  network_interface_id      = azurerm_network_interface.this.id
  network_security_group_id = azurerm_network_security_group.this.id
}

# ==============================================================================
# Virtual Machine
# ==============================================================================

# cloud-init script: installs postgresql-client and sets up an auto-deallocate
# systemd timer that fires every 30 minutes. If no active SSH session is found,
# the VM calls the Azure IMDS + REST API to deallocate itself using its
# system-assigned managed identity.
locals {
  cloud_init = <<-EOT
    #cloud-config
    packages:
      - postgresql-client
      - curl
      - python3
    write_files:
      - path: /usr/local/bin/auto-deallocate.sh
        permissions: '0755'
        content: |
          #!/bin/bash
          set -euo pipefail
          # Do not deallocate if an SSH session is active.
          SESSION_COUNT=$(who | grep -c pts || true)
          if [ "$SESSION_COUNT" -gt 0 ]; then
            exit 0
          fi
          IMDS="http://169.254.169.254/metadata"
          TOKEN=$(curl -sf -H "Metadata: true" \
            "$IMDS/identity/oauth2/token?api-version=2018-02-01&resource=https://management.azure.com/" \
            | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
          INFO=$(curl -sf -H "Metadata: true" \
            "$IMDS/instance?api-version=2021-02-01")
          SUB=$(echo "$INFO" | python3 -c "import sys,json; print(json.load(sys.stdin)['compute']['subscriptionId'])")
          RG=$(echo "$INFO"  | python3 -c "import sys,json; print(json.load(sys.stdin)['compute']['resourceGroupName'])")
          VM=$(echo "$INFO"  | python3 -c "import sys,json; print(json.load(sys.stdin)['compute']['name'])")
          curl -sf -X POST \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Length: 0" \
            "https://management.azure.com/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.Compute/virtualMachines/$VM/deallocate?api-version=2023-03-01"
      - path: /etc/systemd/system/auto-deallocate.service
        content: |
          [Unit]
          Description=Deallocate VM when idle (no active SSH sessions)
          [Service]
          Type=oneshot
          ExecStart=/usr/local/bin/auto-deallocate.sh
      - path: /etc/systemd/system/auto-deallocate.timer
        content: |
          [Unit]
          Description=Check VM idleness every 30 minutes
          [Timer]
          OnBootSec=30min
          OnUnitActiveSec=30min
          [Install]
          WantedBy=timers.target
    runcmd:
      - systemctl daemon-reload
      - systemctl enable --now auto-deallocate.timer
  EOT
}

resource "azurerm_linux_virtual_machine" "this" {
  name                = var.name
  location            = var.location
  resource_group_name = var.resource_group_name
  size                = var.vm_size
  admin_username      = var.admin_username
  custom_data         = base64encode(local.cloud_init)

  # System-assigned identity required by the auto-deallocate script
  # to call the Azure REST API without stored credentials.
  identity {
    type = "SystemAssigned"
  }

  network_interface_ids = [azurerm_network_interface.this.id]

  admin_ssh_key {
    username   = var.admin_username
    public_key = var.admin_ssh_public_key
  }

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
# RBAC — allow VM to deallocate itself via managed identity
# ==============================================================================

# The system-assigned identity needs Virtual Machine Contributor on its own
# resource group to call the deallocate REST API from the cloud-init script.
resource "azurerm_role_assignment" "self_deallocate" {
  scope                = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/resourceGroups/${var.resource_group_name}"
  role_definition_name = "Virtual Machine Contributor"
  principal_id         = azurerm_linux_virtual_machine.this.identity[0].principal_id
}

data "azurerm_client_config" "current" {}

# ==============================================================================
# Auto-shutdown schedule — daily safety net
# ==============================================================================

# Daily shutdown at auto_shutdown_time UTC. Acts as a safety net if the
# auto-deallocate timer fails (e.g. VM frozen, script error).
resource "azurerm_dev_test_global_vm_shutdown_schedule" "this" {
  virtual_machine_id = azurerm_linux_virtual_machine.this.id
  location           = var.location
  enabled            = true

  daily_recurrence_time = var.auto_shutdown_time
  timezone              = "UTC"

  notification_settings {
    enabled = false
  }
}
