output "vm_id" {
  description = "Resource ID of the jumpbox virtual machine."
  value       = azurerm_linux_virtual_machine.this.id
}

output "private_ip" {
  description = "Private IP address of the jumpbox VM."
  value       = azurerm_network_interface.this.private_ip_address
}
