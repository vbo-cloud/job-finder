variable "communication_service_name" {
  type        = string
  description = "Name of the Azure Communication Service resource."
}

variable "email_service_name" {
  type        = string
  description = "Name of the Azure Email Communication Service resource."
}

variable "resource_group_name" {
  type        = string
  description = "Name of the resource group that contains the resources."
}

variable "data_location" {
  type        = string
  description = "Geography where the Communication/Email service stores data at rest (e.g. France)."
}

variable "domain_name" {
  type        = string
  description = "Customer-managed domain used as the email sender domain (e.g. vincentboutin.dev)."

  validation {
    condition     = can(regex("^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$", var.domain_name))
    error_message = "domain_name must be a valid DNS hostname (e.g. vincentboutin.dev)."
  }
}

variable "sender_username" {
  type        = string
  description = "Local part of the sender address (e.g. jobfinder for jobfinder@<domain_name>)."

  validation {
    condition     = can(regex("^[a-z0-9._-]+$", var.sender_username))
    error_message = "sender_username must contain only lowercase letters, digits, dots, underscores, or hyphens."
  }
}

variable "sender_display_name" {
  type        = string
  default     = null
  description = "Friendly display name shown next to the sender address in email clients."
}

variable "environment" {
  type        = string
  description = "Environment identifier applied to resource tags."
}

variable "project" {
  type        = string
  description = "Short project identifier applied to resource tags."
}

variable "owner" {
  type        = string
  description = "Owner email address applied to resource tags."
}
