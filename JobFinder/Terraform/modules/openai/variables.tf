variable "name" {
  type        = string
  description = "Name of the Azure OpenAI cognitive account."
}

variable "location" {
  type        = string
  description = "Azure region where the account is deployed."
}

variable "resource_group_name" {
  type        = string
  description = "Name of the resource group that contains the account."
}

variable "sku_name" {
  type        = string
  default     = "S0"
  description = "SKU of the cognitive account. S0 is the only option for Azure OpenAI."
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

variable "deployments" {
  description = "Map of model deployments. Key = deployment name."
  type = map(object({
    model_name    = string
    model_version = string
    capacity_tpm  = number # Tokens per minute in thousands (e.g. 10 = 10K TPM)
    scale_type    = string # "Standard" or "GlobalStandard"
  }))
}
