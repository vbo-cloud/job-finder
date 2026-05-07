variable "name" {
  type        = string
  description = "Secret name in Key Vault."
}

variable "value" {
  type        = string
  sensitive   = true
  description = "Secret value."
}

variable "key_vault_id" {
  type        = string
  description = "Resource ID of the Key Vault."
}

variable "content_type" {
  type        = string
  default     = "text/plain"
  description = "Content type hint for consumers."
}

variable "environment" {
  type = string
}

variable "project" {
  type = string
}

variable "owner" {
  type = string
}
