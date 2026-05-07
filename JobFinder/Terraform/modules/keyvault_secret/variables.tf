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
  type        = string
  description = "Environment identifier applied to resource tags (e.g. dev)."
}

variable "project" {
  type        = string
  description = "Short project identifier applied to resource tags (e.g. jf)."
}

variable "owner" {
  type        = string
  description = "Owner email address applied to resource tags."
}
