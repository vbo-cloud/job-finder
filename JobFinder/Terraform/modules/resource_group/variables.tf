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
