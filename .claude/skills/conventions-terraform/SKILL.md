---
name: conventions-terraform
description: Conventions Terraform obligatoires du projet Job Finder — nommage Azure (rg-jf-dev-frc, vnet-jf-lz-dev-frc...), structure des modules, tags, règles de lifecycle et de protection (prevent_destroy, protect="true") sur les ressources critiques (Key Vault, AKS, VNet, PostgreSQL, Service Bus, Azure OpenAI, ACR...), checklist sécurité et coût. Utilise ce skill avant d'écrire ou modifier tout fichier .tf, de créer une resource group / VNet / subnet / module Terraform, de nommer une ressource Azure, ou de reviewer une PR touchant lz-dev/, dev/, lz-prod/, prod/, ou modules/ — même si l'utilisateur ne dit pas explicitement "convention" ou "Terraform".
---

# Terraform Conventions

## Naming

- Cloud provider: Azure only — no AWS, GCP, or other provider resources allowed
- Environment folder names use underscores (`lz_dev`, `dev`). Tag values and Azure resource names use hyphens (`lz-dev`, `rg-jf-dev-frc`)
- Naming pattern: `{type}-{project}-{environment}-{region}-{index}`
  - Project: `jf`
  - Environments: `dev`, `prod`, `lz-dev`, `lz-prod`
  - Region: `frc` (France Central)
  - Index: `001`, `002`… (optional)
  - Prefixes: `rg`, `vnet`, `snet`, `kv`, `st`, `aks`, `nsg`
  - Examples: `rg-jf-dev-frc`, `vnet-jf-lz-dev-frc`, `snet-jf-dev-frc-app`
  - Storage accounts omit hyphens and are capped at 24 chars: `stjfdevfrc`

## Section separators in `.tf` files

Use the following format to separate logical groups of resources within a file:

```hcl
# ==============================================================================
# Section Name
# ==============================================================================
```

## Rules

- Always write reusable modules. Raison : le mirror prod (v1.0.0) réutilisera ces modules tels quels — du code non modulaire signifie tout réécrire à ce moment-là.
- Comment non-obvious architecture decisions. Raison : projet solo — les commentaires remplacent les échanges d'équipe qui expliqueraient sinon ces choix à un futur lecteur (humain ou Claude Code).
- Every resource must have tags: environment, project, owner
- Every `variable` and `output` block in a module must have a `description`. No exceptions.
- Add `validation` blocks to module variables that have obvious constraints (accepted values, value ranges, expected formats). Do not validate unconstrained fields like `name` or `location` — those are validated by Azure at apply time.
- Always reference other resources through their module outputs, never directly.
  For example: `module.keyvault.id` not `azurerm_key_vault.this.id`,
  `module.rg_app.name` not `azurerm_resource_group.rg_app.name`.
  Before writing any reference to another resource, check whether a module
  already manages it and use its output.
- Every provider used in an environment — directly or via a module — must be declared explicitly in the `required_providers` block of the root environment (`envs/*/main.tf`). Modules must not be the sole place where a provider is declared. This ensures all provider dependencies are visible at the environment level and versions are controlled centrally.
- Never run `terraform apply` locally. All applies must go through the CI/CD pipeline via a PR merged to main. Raison : évite les state locaux divergents du state distant et garde un historique d'applies traçable et reproductible en CI.
- `terraform.tfvars` files are never committed (gitignored). Do not attempt to stage or commit them.
- Always update `docs/JOURNAL.md` when creating or updating a PR. `docs/JOURNAL.md` is a concise log of the project's progress. For each PR, add an entry with: PR number and title, date, summary of what was implemented and why, and any important technical decisions made.
- During Milestone 1, only implement changes in `envs/dev/`. Do not mirror to `envs/prod/` until dev is stable and testable (end of M1). A single prod mirror + apply will be done at v1.0.0, with prod-specific adjustments (SKUs, retention, geo-redundancy).

## Common Commands

All Terraform commands must be run from within the specific environment directory (e.g., `JobFinder/Terraform/envs/dev/`).

```bash
terraform init                      # Initialize backend and providers
terraform fmt                       # Format code
terraform fmt -check                # Check formatting (used in CI)
terraform validate                  # Validate syntax
terraform plan -input=false         # Preview changes
terraform apply -auto-approve -input=false  # Apply changes (CI only)
```

## Architecture

### Environment Structure

Two-layer pattern per environment:

- **Landing Zone** (`lz_dev`, `lz_prod`): Foundation infrastructure — resource groups, Key Vault, virtual networks/subnets. Must be deployed before the app layer.
- **Application** (`dev`, `prod`): App-level resource groups split into core, app, and data concerns.

### Modules

Reusable modules live in `JobFinder/Terraform/modules/`:
- `resource_group/` — Azure resource groups
- `vnet/` — Virtual networks
- `subnet/` — Subnets (with optional delegation)
- `keyvault/` — Key Vault (RBAC, purge protection)
- `keyvault_secret/` — Key Vault secrets
- `private_endpoint/` — Generic private endpoint + DNS zone group
- `storage/` — Storage accounts
- `postgresql/` — PostgreSQL Flexible Server (pgvector, VNet injection, KV secret)
- `servicebus/` — Service Bus namespace + queues
- `openai/` — Azure OpenAI account + model deployments
- `container_registry/` — Azure Container Registry
- `application_insights/` — Application Insights + Log Analytics Workspace
- `container_app_environment/` — Container Apps Environment (shared)
- `container_app_job/` — Container App Job (timer or queue trigger)
- `policy/allowed_locations/` — Azure Policy: restrict deployments to allowed regions
- `policy/auto_lock/` — Azure Policy: CanNotDelete lock on `protect=true` resources
- `compute/`, `network/`, `data/` — Placeholders (not yet implemented)

**Module design rule:** one primary resource per module, plus resources intrinsically linked that have no meaning without it. If a secondary resource cannot exist independently of the primary, it goes in the module. If it can exist alone or be shared between multiple resources, it stays outside the module.

### State Backend

Remote state in Azure Storage (`stjftfstatefrc` storage account, `tfstate` container). Each environment has its own state file: `dev.tfstate`, `lz-dev.tfstate`, `lz-prod.tfstate`, `prod.tfstate`.

## Lifecycle rules on critical resources

All of the following resource types must include `prevent_destroy = true` **and** the tag `protect = "true"`:
- `azurerm_key_vault`
- `azurerm_kubernetes_cluster`
- `azurerm_virtual_network`
- `azurerm_subnet`
- `azurerm_resource_group` — `prevent_destroy = true` only (no `protect` tag — see note below)
- `azurerm_postgresql_flexible_server`
- `azurerm_servicebus_namespace`
- `azurerm_cognitive_account` (Azure OpenAI)
- `azurerm_container_registry`
- `azurerm_container_app_environment`
- `azurerm_application_insights`
- `azurerm_log_analytics_workspace`
- `azurerm_policy_definition` / `azurerm_subscription_policy_assignment`

Note: `azurerm_subnet` does not support tags in the azurerm provider — protection is enforced via `prevent_destroy = true` only.

Note: `azurerm_resource_group` does not carry the `protect = "true"` tag — a CanNotDelete auto-lock applied to a Resource Group would block Terraform operations on its child resources. Protection is enforced by `prevent_destroy = true` alone.

The `protect = "true"` tag triggers the auto-lock policy (deployIfNotExists) defined in `lz_dev/policies.tf`, which automatically applies a `CanNotDelete` management lock on the resource.

## Security & cost review checklist

- No public IP unless explicitly justified in the PR description
- Storage accounts must not be publicly accessible
- Key Vault must have `purge_protection_enabled = true`
- NSG rules must not be open to `0.0.0.0/0`
- No passwords, secrets, or credentials hardcoded or in plain text
- Flag VM SKUs above `Standard_D4s_v3` in dev environments
- Flag any resource generating significant recurring cost; suggest cheaper alternatives when relevant
- Prod mirror is deferred to v1.0.0 — do not mirror dev changes to prod until then
