# Backend config cannot use Terraform variables — these must be literal strings.
# Replace CHANGE_ME with the actual storage account name before running terraform init.
# Each environment has its own state key to prevent cross-environment state interference.
terraform {
  backend "azurerm" {
    resource_group_name  = "rg-tfstate"
    storage_account_name = "stjftfstatefrc" # Template users: replace with your own Terraform state storage account name
    container_name       = "tfstate"
    key                  = "lz-dev.tfstate"
  }
}