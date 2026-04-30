# azure-tf-template

A production-ready Azure infrastructure template with multi-environment Terraform, GitHub Actions CI/CD (OIDC), and an automated Claude AI code reviewer.

[![Terraform Plan](https://github.com/vbo-cloud/job-finder/actions/workflows/terraformPlan.yml/badge.svg)](https://github.com/vbo-cloud/job-finder/actions/workflows/terraformPlan.yml)
[![Terraform Apply](https://github.com/vbo-cloud/job-finder/actions/workflows/terraformApply.yml/badge.svg)](https://github.com/vbo-cloud/job-finder/actions/workflows/terraformApply.yml)

---

## What this template provides

- **Multi-environment Terraform structure** — landing zones (`lz_dev`, `lz_prod`) and application layers (`dev`, `prod`), each with isolated remote state
- **GitHub Actions CI/CD with OIDC** — federated credentials, no static secrets; Plan on every PR, Apply on merge
- **Claude AI reviewer agent** — posts automated reviews on every PR using Terraform plan output as context
- **GitFlow conventions** — `main` / `dev` / `feature/*` / `hotfix/*` with branch protection and Conventional Commits
- **Full parameterization via `tfvars`** — all project-specific values isolated; `CHANGE_ME` placeholders with validation blocks that catch unfilled values at plan time

---

## Architecture overview

```
Azure Subscription
├── Landing Zone Dev (lz_dev)              Landing Zone Prod (lz_prod)
│   · VNet hub  · Key Vault                    · VNet hub  · Key Vault
│   · Subscription-level Policy                · Subscription-level Policy
│           │                                           │
│           │ (future VNet peering)                     │
├── App Layer Dev (dev)                    App Layer Prod (prod)
    · Resource groups: core / app / data       · Resource groups: core / app / data
    · AKS, services (coming)                   · AKS, services (coming)
```

```
CI/CD flow
──────────
PR opened
  └─→ Terraform Plan  (lz_dev, dev, lz_prod, prod — parallel)
          └─→ Claude Reviewer Agent  →  APPROVE or REQUEST_CHANGES

Merge to dev
  └─→ Terraform Apply  →  lz_dev, dev  (automatic)

Merge to main  (PR from dev, prod environment approval gate)
  └─→ Terraform Apply  →  lz_prod, prod
```

---

## Repository structure

```
.
├── .github/
│   ├── workflows/
│   │   ├── terraformPlan.yml       # CI: fmt-check, validate, plan on every PR
│   │   ├── terraformApply.yml      # CD: apply on merge to dev or main
│   │   └── reviewerAgent.yml       # AI: Claude review posted after plan completes
│   └── reviewer-agent/
│       └── system-prompt.md        # System prompt defining the reviewer's rules
├── JobFinder/Terraform/
│   ├── envs/
│   │   ├── lz_dev/                 # Landing zone dev — VNet, Key Vault, Policy
│   │   ├── dev/                    # App layer dev — resource groups, future AKS
│   │   ├── lz_prod/                # Landing zone prod
│   │   └── prod/                   # App layer prod
│   └── modules/
│       ├── resource_group/         # Reusable resource group with required tags
│       ├── network/                # VNet and subnet scaffold
│       ├── compute/                # Compute resources scaffold (VM / AKS)
│       └── policy/                 # Allowed-locations policy — definition + subscription assignment
├── GETTING_STARTED.md              # Step-by-step onboarding guide
├── DOC.md                          # Template changelog
└── CLAUDE.md                       # Conventions for Claude Code
```

---

## Quick start

1. Click **Use this template** → **Create a new repository**, then complete the setup steps in [GETTING_STARTED.md](GETTING_STARTED.md)
2. Replace all `CHANGE_ME` values in `backend.tf` (×4) and `terraform.tfvars` (×4)
3. Open a PR — Terraform Plan and the Claude reviewer will run automatically

---

## CI/CD workflows

| Workflow | Trigger | Role |
|----------|---------|------|
| `terraformPlan.yml` | Every pull request | Runs `fmt -check`, `validate`, and `plan` across all 4 environments in parallel |
| `terraformApply.yml` | Push to `dev` or `main` | Applies `lz_dev` + `dev` on push to `dev`; applies `lz_prod` + `prod` on push to `main` (with approval gate) |
| `reviewerAgent.yml` | After Terraform Plan completes | Fetches plan logs, calls Claude API, posts APPROVE or REQUEST_CHANGES on the PR |

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Cloud | Microsoft Azure |
| IaC | Terraform — `azurerm ~> 3.0` |
| CI/CD | GitHub Actions with OIDC (no stored credentials) |
| AI reviewer | Claude API (`claude-sonnet-4-6`) via Anthropic SDK |
