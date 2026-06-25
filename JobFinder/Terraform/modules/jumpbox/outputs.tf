output "public_ip" {
  description = "Public IP address of the jumpbox VM."
  value       = azurerm_public_ip.this.ip_address
}

output "vm_id" {
  description = "Resource ID of the jumpbox virtual machine."
  value       = azurerm_linux_virtual_machine.this.id
}

output "private_ip" {
  description = "Private IP address of the jumpbox VM (for reference)."
  value       = azurerm_network_interface.this.private_ip_address
}

output "ssh_command" {
  description = "Ready-to-use SSH command to connect to the jumpbox."
  value       = "ssh ${azurerm_linux_virtual_machine.this.admin_username}@${azurerm_public_ip.this.ip_address}"
}
