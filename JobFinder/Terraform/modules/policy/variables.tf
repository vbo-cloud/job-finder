# Variables for the allowed-locations policy module.
# CHANGE_ME defaults are intentional: terraform validate succeeds without a tfvars file,
# but the placeholder makes it obvious which values must be substituted before deploying.

variable "environment" {
  type        = string
  description = "Environment name used in resource naming (e.g. lz-dev, dev, lz-prod, prod)"
}

variable "project" {
  type        = string
  description = "Short project identifier used in resource names (e.g. jf)"
  default     = "CHANGE_ME"
}

variable "location_short" {
  type        = string
  description = "Short identifier for the Azure region, used in resource names (e.g. frc for francecentral)"
  default     = "CHANGE_ME"
}

# Add or remove regions here to control where resources can be deployed.
# Changing this list triggers a policy update in-place, not a destroy/recreate.
variable "allowed_locations" {
  type        = list(string)
  description = "List of allowed Azure regions"
  default     = ["francecentral", "northeurope"]
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to policy resources (required keys: environment, project, owner)"
}

# Use this to exempt specific resource groups from the policy — e.g. a sandbox RG
# used for third-party integrations that deploy outside the allowed regions:
# not_scopes = ["/subscriptions/{id}/resourceGroups/rg-{project}-dev-{short}-sandbox"]
variable "not_scopes" {
  type        = list(string)
  description = "List of scope paths excluded from the policy assignment (e.g. resource group IDs for test exemptions)"
  default     = []
}
