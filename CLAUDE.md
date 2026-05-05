# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Job-Finder Infrastructure Project

## Context
Portfolio project for a Cloud/AI career transition.
Unity developer transitioning to Azure + AI.
Az-104 certification obtained.

## Tech Stack
- Cloud: Azure
- IaC: Terraform
- CI/CD: GitHub Actions with OIDC
- Target: AKS (Kubernetes)
- AI: Claude API agents (coming soon)

## Repo Structure
- lz-dev/   → Landing Zone dev (network core, RBAC, policies)
- dev/      → Application infrastructure dev
- lz-prod/  → (coming soon)
- prod/     → (coming soon)
- iam/dev/, iam/prod/ → RBAC management, applied manually by the user (not via CI/CD, not via sp-jf-github). The identity running `terraform apply` is the current session user (`data.azurerm_client_config.current`). Never add iam/ to the Plan/Apply workflows.

## Terraform Conventions
- Modules: compute / network / data / resource-group
- Remote state: Azure Storage Backend
- Naming pattern: `{type}-{project}-{environment}-{region}-{index}`
- Section separators in `.tf` files: use the following format to separate logical groups of resources within a file:
  ```hcl
  # ==============================================================================
  # Section Name
  # ==============================================================================
  ```
  - Project: `jf`
  - Environments: `dev`, `prod`, `lz-dev`, `lz-prod`
  - Region: `frc` (France Central)
  - Index: `001`, `002`… (optional)
  - Prefixes: `rg`, `vnet`, `snet`, `kv`, `st`, `aks`, `nsg`
  - Examples: `rg-jf-dev-frc`, `vnet-jf-lz-dev-frc`, `snet-jf-dev-frc-app`
  - Storage accounts omit hyphens and are capped at 24 chars: `stjfdevfrc`

## Rules
- Always write reusable modules
- Comment non-obvious architecture decisions
- Every resource must have tags: environment, project, owner
- Never run `terraform apply` locally. All applies must go through the CI/CD pipeline via a PR merged to main.
- `terraform.tfvars` files are never committed (gitignored). Do not attempt to stage or commit them.
- Always update `docs/JOURNAL.md` when creating or updating a PR. `docs/JOURNAL.md` is a concise log of the project's progress. For each PR, add an entry with: PR number and title, date, summary of what was implemented and why, and any important technical decisions made.
- During Milestone 1, only implement changes in `envs/dev/`. Do not mirror to `envs/prod/` until dev is stable and testable (end of M1). A single prod mirror + apply will be done at v1.0.0, with prod-specific adjustments (SKUs, retention, geo-redundancy).

## Project Overview

This is an Azure Infrastructure-as-Code project using Terraform. It provisions cloud resources across multiple environments (dev/prod) with a landing zone pattern.

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
- `resource_group/` — Azure resource groups (inputs: `name`, `location`)
- `network/` — VNets and subnets
- `compute/` — Compute resources (partially implemented)
- `data/` — Data resources (partially implemented)

**Module design rule:** one primary resource per module, plus resources intrinsically linked that have no meaning without it. If a secondary resource cannot exist independently of the primary, it goes in the module. If it can exist alone or be shared between multiple resources, it stays outside the module.

### State Backend

Remote state in Azure Storage (`stjftfstatefrc` storage account, `tfstate` container). Each environment has its own state file: `dev.tfstate`, `lz-dev.tfstate`, `lz-prod.tfstate`, `prod.tfstate`.

## CI/CD

- **PRs** → `.github/workflows/terraformPlan.yml`: runs `fmt -check`, `validate`, and `plan` across all 4 environments.
- **Push to main** → `.github/workflows/terraformApply.yml`: applies dev immediately; prod requires environment approval.

Authentication uses Azure OIDC (no stored credentials). Required GitHub secrets: `ARM_CLIENT_ID`, `ARM_TENANT_ID`, `ARM_SUBSCRIPTION_ID`.

## Key Details

- Azure provider pinned to `~> 3.0` (azurerm)
- Region: `francecentral`
- `lz_prod/` and `prod/` directories are partially empty — production infrastructure is not yet fully defined
- The `compute` module contains a reference to `t2.micro` (AWS naming) — this is a copy-paste artifact and should be updated for Azure

## Git Flow

- `main` → stable, production-ready, always tagged with `vMAJOR.MINOR.PATCH`
- `dev` → integration branch, base for all feature branches
- `feature/*` → one feature per branch, always from `dev`
- `hotfix/*` → urgent fix from `main`, merged back to both `main` and `dev`

### Branch rules
- Never push directly to `main` or `dev`
- All changes go through PRs
- `feature/*` → PR to `dev`
- `hotfix/*` → PR to `main`, then sync to `dev`
- `dev` → PR to `main` only when stable (triggers a version tag)

### Versioning (Semantic Versioning)
- `v1.0.0` → MAJOR.MINOR.PATCH
- PATCH → hotfix
- MINOR → new feature
- MAJOR → breaking change

### Workflow
- New feature : `git checkout -b feature/xxx dev`
- Hotfix      : `git checkout -b hotfix/xxx main`
- Release     : PR from `dev` to `main` + tag `vX.X.X` after merge

## Git Workflow

### Before creating a new feature branch
1. `git fetch origin`
2. `git checkout dev && git merge --ff-only origin/dev`
3. `git checkout -b feature/xxx`

### Before creating a hotfix branch
1. `git fetch origin`
2. `git checkout main && git merge --ff-only origin/main`
3. `git checkout -b hotfix/xxx`

### Before opening a PR, or if the branch is behind its base
1. `git stash` local WIP changes
2. `git rebase -i origin/<base>` — create atomic commits following Conventional Commits
3. `git rebase origin/<base>` (never merge)
4. `git push --force-with-lease`
5. `git stash pop` after switching branches

### Commit conventions (Conventional Commits)
- `feat:` new feature
- `fix:` bug fix
- `chore:` maintenance task
- `docs:` documentation
- `refactor:` code restructuring

### Rules
- Never open a PR with WIP or non-atomic commits
- Never use merge to catch up with the base branch, always rebase
- Never force push without `--force-with-lease`

## Code Review Standards

Enforced automatically by the Claude reviewer agent (`.github/reviewer-agent/system-prompt.md`). Naming conventions, required tags, and module usage are already defined above — the sections below cover what is not.

### Security
- No public IP unless explicitly justified in the PR description
- Storage accounts must not be publicly accessible
- Key Vault must have `purge_protection_enabled = true`
- NSG rules must not be open to `0.0.0.0/0`
- No passwords, secrets, or credentials hardcoded or in plain text

### Cost awareness
- Flag VM SKUs above `Standard_D4s_v3` in dev environments
- Flag any resource generating significant recurring cost
- Suggest cheaper alternatives when relevant

### Environment consistency
- Changes in `dev` should be mirrored in `prod` when relevant
- `lz_dev` and `lz_prod` must stay structurally consistent

### Lifecycle rules on critical resources
All of the following resource types must include `prevent_destroy = true`:
- `azurerm_key_vault`
- `azurerm_kubernetes_cluster`
- `azurerm_virtual_network`
- `azurerm_subnet`
- `azurerm_resource_group`
- `azurerm_policy_definition` / `azurerm_subscription_policy_assignment`

### Blocking criteria
A PR is blocked (REQUEST_CHANGES) if any of the following apply:
- Unexpected destroy or replacement of a critical resource (Key Vault, AKS, VNet, Subnet, Resource Group)
- Any security rule above is violated
- Required tags missing on any resource
- Hardcoded secrets or credentials present