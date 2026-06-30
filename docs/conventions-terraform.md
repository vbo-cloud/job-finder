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

- Always write reusable modules
- Comment non-obvious architecture decisions
- Every resource must have tags: environment, project, owner
- Every `variable` and `output` block in a module must have a `description`. No exceptions.
- Add `validation` blocks to module variables that have obvious constraints (accepted values, value ranges, expected formats). Do not validate unconstrained fields like `name` or `location` — those are validated by Azure at apply time.
- Always reference other resources through their module outputs, never directly.
  For example: `module.keyvault.id` not `azurerm_key_vault.this.id`,
  `module.rg_app.name` not `azurerm_resource_group.rg_app.name`.
  Before writing any reference to another resource, check whether a module
  already manages it and use its output.
- Every provider used in an environment — directly or via a module — must be declared explicitly in the `required_providers` block of the root environment (`envs/*/main.tf`). Modules must not be the sole place where a provider is declared. This ensures all provider dependencies are visible at the environment level and versions are controlled centrally.
- Never run `terraform apply` locally. All applies must go through the CI/CD pipeline via a PR merged to main.
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
