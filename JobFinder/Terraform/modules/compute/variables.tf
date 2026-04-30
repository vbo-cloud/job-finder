# Variables for the compute module.
# vm_size follows Azure SKU naming: Standard_{tier}{vCPUs}s_v{version}.
# Use Standard_B2s for dev/test; move to Standard_D or E series for production workloads.
# Sizes above Standard_D4s_v3 in dev environments are flagged by the reviewer agent as costly.

variable "vm_size" {
  type        = string
  default     = "Standard_B2s"
  description = "The size of the Azure Virtual Machine"
}
