# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Job-Finder Infrastructure Project

## Collaborative workflow

This project is managed by two Claude instances with distinct roles:

**Claude Cowork** — pedagogical and design role. Answers questions, explains concepts, and produces detailed prompts broken into tasks for Claude Code. May modify documentation files (`docs/`, `memory/`, `CLAUDE.md`). Has read-only access to all other project files and never touches Terraform, Python, or PowerShell code.

**Claude Code** — execution role. Applies decisions made with Claude Cowork. Owns the full feature lifecycle: branch creation, implementation, PR opening. Has exclusive ownership of Terraform, Python, and PowerShell code.

## Context
Portfolio project for a Cloud/AI career transition.
Unity developer transitioning to Azure + AI.
Az-104 certification obtained.

## Tech Stack
- Cloud: Azure
- IaC: Terraform
- CI/CD: GitHub Actions with OIDC
- Target: AKS (Kubernetes)
- AI: Azure OpenAI (GPT-4o-mini + text-embedding-3-small, francecentral) — agents via Container App Jobs + Service Bus

## Repo Structure
- lz-dev/   → Landing Zone dev (network core, RBAC, policies)
- dev/      → Application infrastructure dev
- lz-prod/  → (coming soon)
- prod/     → (coming soon)
- iam/dev/, iam/prod/ → RBAC management, applied manually by the user (not via CI/CD, not via sp-jf-github). The identity running `terraform apply` is the current session user (`data.azurerm_client_config.current`). Never add iam/ to the Plan/Apply workflows.

## Terraform Conventions

→ See `docs/conventions-terraform.md`. Read this file before writing or editing any Terraform code.

## CI/CD

- **PRs** → `.github/workflows/terraformPlan.yml`: runs `fmt -check`, `validate`, and `plan` on `lz_dev` and `dev` (change-detection via git diff).
- **Push to dev** → `.github/workflows/terraformApply.yml`: applies `lz_dev` then `dev` sequentially (landing zone first).

Authentication uses Azure OIDC (no stored credentials). Required GitHub variables: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_PLATFORM_CLIENT_ID`, `SP_GITHUB_OBJECT_ID`. GitHub secrets (sensitive): `CLAUDE_API_KEY`, `REVIEWER_GITHUB_TOKEN`.

## Key Details

- Azure provider pinned to `~> 4.0` (azurerm)
- Region: `francecentral`
- `lz_prod/` and `prod/` directories removed until release v1.0.0 — production infrastructure will be provisioned from scratch at that point
- The `compute`, `data`, and `network` modules are placeholders — not yet implemented

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
- A PR never mixes platform (`envs/lz_*`) and app (`envs/dev/`, `envs/prod/`) changes.
  If a feature touches both layers, use two separate PRs — platform first, app second.
  Module changes (`modules/`) that accompany an app feature go in a dedicated PR first.

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

## Python Conventions

→ See `docs/conventions-python.md`. Read this file before writing or editing any Python code.

---

## SQL / Alembic Conventions

→ See `docs/conventions-sql.md`. Read this file before writing or editing any SQLAlchemy models or Alembic migrations.

---

## Frontend / Next.js Conventions

→ See `docs/conventions-frontend.md`. Read this file before writing or editing any Next.js / React / TypeScript frontend code.

---

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
- Prod mirror is deferred to v1.0.0 — do not mirror dev changes to prod until then.

### Lifecycle rules on critical resources
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

### Blocking criteria
A PR is blocked (REQUEST_CHANGES) if any of the following apply:
- Unexpected destroy or replacement of a critical resource (Key Vault, AKS, VNet, Subnet, Resource Group, PostgreSQL, Service Bus, Azure OpenAI, ACR, Container App Environment, Application Insights, Log Analytics Workspace)
- Missing `protect = "true"` tag on a critical resource — intentional exception: Resource Groups do not carry this tag (see note in "Lifecycle rules")
- Any security rule above is violated
- Required tags missing on any resource
- Hardcoded secrets or credentials present