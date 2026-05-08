# Backend config cannot use Terraform variables — these must be literal strings.
# Replace CHANGE_ME with the actual storage account name before running terraform init.
terraform {
  backend "azurerm" {
    resource_group_name  = "rg-jf-tfstate-frc"
    storage_account_name = "stjftfstatefrc" # Template users: replace with your own Terraform state storage account name
    container_name       = "tfstate"
    key                  = "dev.tfstate"
  }
}