terraform {
  backend "azurerm" {
    resource_group_name  = "rg-tfstate"
    storage_account_name = "stjftfstatefrc"
    container_name       = "tfstate"
    key                  = "iam-dev.tfstate"
  }
}
