# Inputs for the resource_group module.
# Both are required (no defaults) so callers are always explicit about name and location.

variable "name" {
  type        = string
  description = "Resource group's name"
}

variable "location" {
  type        = string
  description = "Resource group's location"
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
