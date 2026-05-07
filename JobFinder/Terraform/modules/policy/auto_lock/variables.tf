variable "project" {
  type        = string
  description = "Short project identifier used in resource names (e.g. jf)"
}

variable "owner" {
  type        = string
  description = "Owner email applied to policy metadata"
}

variable "location" {
  type        = string
  description = "Azure region for the policy assignment (required for SystemAssigned identity)"
}

variable "subscription_id" {
  type        = string
  description = "Azure subscription ID for the policy assignment scope"
}
