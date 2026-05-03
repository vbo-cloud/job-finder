# Job Finder — Project Log

This document tracks the progress of the Job Finder infrastructure project. It is updated with each PR.

---

## Initial Setup

The following was completed before the PR-based workflow was established.

### Security baseline
- Stored all passwords and recovery codes in a password manager
- Rotated all existing passwords to maximum complexity
- Enabled 2FA with an Authenticator app on all accounts

### Domain and email
- Registered a professionnal domain
- Created a professional email address associated with that domain

### Azure tenant and subscriptions
- Created a new Azure tenant
- Created a resource group, storage account, and blob container to hold Terraform remote state files
- Applied resource locks on the resource group and storage account to prevent accidental deletion
- Created one Management Group for the project, with one child management group and one subscription per environment (Dev and Prod)

### Git repository
- Created a new GitHub organization and a new private repository
- Configured `.gitignore` for Terraform (state files, `.terraform/`, etc.)
- Set up SSH key authentication

### Terraform base structure
- Two environments: `dev` and `prod`
- One landing zone directory (`lz_dev`, `lz_prod`) and one application infrastructure directory per environment
- Remote state backend using the Azure Storage account created above

### CI/CD pipelines
- Created Azure credentials (service principal + OIDC) to authenticate GitHub Actions runners
- **Terraform Plan workflow** — triggers on every PR, runs across all four environments (`lz-dev`, `dev`, `lz-prod`, `prod`): `terraform init`, `fmt -check`, `validate`, `plan`
- **Terraform Apply workflow** — triggers on push to `main`, runs per environment with environment-specific context; executes `terraform init` and `apply`
- Goal: in a team setting, no one applies infrastructure manually — all changes go through the CI/CD pipeline. The PR review shows what `plan` proposes; merging to `main` applies it.

---

## PR Log

### PR #1 — feat: migrate state backend and enforce resource naming convention
**Date:** 2026-04-29

**What was done:**
- Migrated Terraform state from local to a remote Azure Storage backend (`stjftfstatefrc` storage account, `tfstate` container), with one state file per environment
- Enforced the project-wide resource naming convention: `{type}-{project}-{environment}-{region}` (e.g., `rg-jf-dev-frc`, `vnet-jf-lz-dev-frc`)
- Fixed Terraform formatting across all environments and modules
- Removed `fail-fast: true` from the Plan workflow matrix so a failure in one environment does not cancel the others

**Technical decisions:**
- Each environment gets its own state file (`dev.tfstate`, `lz-dev.tfstate`, etc.) to isolate blast radius
- Storage accounts omit hyphens and are capped at 24 characters per Azure constraints (`stjftfstatefrc`)

---

### PR #2 — docs: add CLAUDE.md with project conventions
**Date:** 2026-04-29

**What was done:**
- Added `CLAUDE.md` at the repo root documenting project conventions for Claude Code: tech stack, Terraform naming rules, module structure, CI/CD overview, and the no-local-apply rule
- Added a Git workflow section covering branching, rebasing, and Conventional Commits
- Gitignored `.claude/settings.local.json` to avoid leaking personal tool configuration

**Technical decisions:**
- `CLAUDE.md` is checked in so conventions are available to all contributors and to Claude Code in any session on this repo
- `settings.local.json` is kept local-only since it contains personal permission overrides

---

### PR #3 — fix: compute module AWS artifact + scaffold prod environments
**Date:** 2026-04-29

**What was done:**
- Fixed a copy-paste artifact in `modules/compute/variables.tf`: replaced the AWS `t2.micro` instance type and EC2-specific naming with the Azure equivalent (`Standard_B2s`), and renamed the variable from `instance_type` to `vm_size`
- Scaffolded minimal `lz_prod` and `prod` environments mirroring the `lz_dev` / `dev` structure, completing the four-environment layout declared in the CI/CD workflows

**Technical decisions:**
- `lz_prod` uses address space `10.1.0.0/16` to avoid overlap with `lz_dev` (`10.0.0.0/16`)
- Prod environments share the same subscription and tenant as dev for now (single-subscription portfolio project)

---

### PR #4 — chore: add DOC.md project log and enforce update rule in CLAUDE.md
**Date:** 2026-04-29

**What was done:**
- Added `DOC.md` at the repo root, structured as: initial setup log (security, Azure tenant, Git, Terraform, CI/CD) followed by a PR log
- Added a rule to `CLAUDE.md` requiring `DOC.md` to be updated on every PR

**Technical decisions:**
- `DOC.md` is written in English and kept concise — one entry per PR, no noise

---

### PR #5 — chore: set up GitFlow and branch protection
**Date:** 2026-04-29

**What was done:**
- Created and pushed the `dev` integration branch from `main`
- Added a `## Git Flow` section to `CLAUDE.md` defining the branch strategy (`main`, `dev`, `feature/*`, `hotfix/*`), versioning rules (Semantic Versioning), and the release workflow
- Updated the `## Git Workflow` section in `CLAUDE.md` to align with GitFlow (feature branches from `dev`, hotfix branches from `main`)
- Set up branch protection rules on GitHub for `main` and `dev`: all four CI plan jobs must pass before merge, force pushes and deletions are blocked, rules apply to admins as well (applied after making the repo public)

**Technical decisions:**
- `dev` is the integration branch: all features merge here first; `main` is only touched on releases and hotfixes
- Semantic versioning is enforced via tags on `main` at release time (`vMAJOR.MINOR.PATCH`)
- This PR targets `dev` (not `main`) — the first PR to follow the new GitFlow

---

### PR #6 — fix: correct DOC.md branch protection note
**Date:** 2026-04-29

**What was done:**
- Corrected the PR #5 entry in `DOC.md`: branch protection was successfully applied to `main` and `dev` after the repo was made public, but the merged note still reflected an earlier, incomplete state

**Technical decisions:**
- No code change — documentation correction only

---

### PR #7 — CANCELLED
**Date:** 2026-04-30
**Title:** docs: Add project description to README.md

Closed without merging. The README update was deemed out of scope at this stage and will be revisited later.

---

### PR #8 — CANCELLED
**Date:** 2026-04-30
**Title:** feat: Create PR reviewer agent

Closed without merging. Was incorrectly targeting `main` instead of `dev`. Reopened as PR #9.

---

### PR #9 — feat: Create PR reviewer agent
**Date:** 2026-04-30

**What was done:**
- Added `.github/workflows/reviewerAgent.yml`: a GitHub Actions workflow that triggers after the Terraform Plan workflow completes, fetches the PR diff and plan logs for all four environments, calls the Claude API, and posts the review directly on the PR (approve / request changes on plan success; informational comment on plan failure)
- Added `.github/reviewer-agent/system-prompt.md`: the system prompt that defines the reviewer's persona, project context (Azure-only, azurerm ~> 3.0, naming conventions, required tags), review checklist (Terraform, security, cost, environment consistency, documentation, Git hygiene), and structured output format
- Added `.env` to `.gitignore` to prevent accidental credential leaks

**Technical decisions:**
- The workflow uses `workflow_run` to trigger after `Terraform Plan` so the reviewer always has plan output available before commenting
- The system prompt is sent with `cache_control: ephemeral` to benefit from Claude's prompt caching and reduce API costs on repeated runs
- A dedicated `REVIEWER_GITHUB_TOKEN` secret is used (separate from `GITHUB_TOKEN`) to allow the bot to post reviews — `GITHUB_TOKEN` cannot approve its own PRs
- On plan failure the agent posts a comment only (no approve / request changes) to avoid blocking a PR on a CI infrastructure issue rather than a code issue
- The diff sent to Claude is capped at 15 000 characters and each plan log at 6 000 characters to stay within token limits

---

### PR #10 — feat: Add Azure allowed-locations policy across all environments
**Date:** 2026-04-30

**What was done:**
- Created a reusable Terraform module `modules/policy/` with an `azurerm_policy_definition` (Custom, mode All) and an `azurerm_subscription_policy_assignment` scoped to the subscription, so the policy covers all resource groups automatically
- Called the module from each of the four environments (`lz_dev`, `dev`, `lz_prod`, `prod`) via a dedicated `policy.tf` file, restricting deployments to `francecentral` and `northeurope`
- Resources follow the project naming convention: `pd-jf-{env}-frc-allowed-locations` (definition) and `pa-jf-{env}-frc-allowed-locations` (assignment)

**Technical decisions:**
- Assignment is at subscription scope (not resource group) so a single assignment covers all current and future resource groups in the subscription
- `azurerm_subscription_policy_assignment` has no native `tags` block; required tags (`environment`, `project`, `owner`) are embedded in the `metadata` JSON field, which is the Azure-native equivalent for policy resources
- The `allowed_locations` list is a module input with a default of `["francecentral", "northeurope"]`, making it easy to extend for future regions without touching the module internals

---

### PR #11 — docs: update DOC.md with PR #11 and #12 entries
**Date:** 2026-04-30

**What was done:**
- Added DOC.md entries for PR #11 (this PR) and PR #12 (dev → main sync)

**Technical decisions:**
- No code change — documentation only

---

### PR #12 — chore: sync dev to main to activate reviewer agent
**Date:** 2026-04-30

**What was done:**
- Merged `dev` into `main` to make the Claude reviewer agent operational on GitHub — the `workflow_run` trigger on `reviewerAgent.yml` only fires on workflows that exist on the default branch (`main`), so the agent was inactive until this sync

**What's included:**
- Full Terraform foundation: remote state backend, four-environment layout (`lz_dev`, `dev`, `lz_prod`, `prod`), reusable modules (`resource_group`, `network`, `compute`, `data`), consistent naming convention
- CI/CD pipelines: Terraform Plan on every PR, Terraform Apply on merge to main, Azure OIDC authentication
- GitFlow branch strategy with branch protection rules on `main` and `dev`
- Claude reviewer agent: automated PR reviews after Terraform Plan completes
- Project conventions in `CLAUDE.md` and `DOC.md`

**Not included (in progress):**
- Azure allowed-locations policy — PR #10 (`feature/lz-azure-policies-location`)

---

### PR #13 — chore: bump actions/checkout and setup-terraform to v4
**Date:** 2026-04-30

**What was done:**
- Updated `actions/checkout@v3 → @v4` and `hashicorp/setup-terraform@v3 → @v4` in `terraformPlan.yml` and `terraformApply.yml` to resolve Node.js 20 deprecation warnings in all four plan outputs
- `reviewerAgent.yml` was already on `@v4` and required no change

**Technical decisions:**
- No Terraform or infrastructure change — CI tooling update only

---

### PR #14 — feat: trigger Terraform Apply on push to dev for dev environments
**Date:** 2026-04-30

**What was done:**
- Extended `terraformApply.yml` to also trigger on push to `dev`, applying `lz_dev` and `dev` environments automatically when a feature branch is merged
- Added `if: github.ref == 'refs/heads/dev'` on `apply-dev` and `if: github.ref == 'refs/heads/main'` on `apply-prod` so each job runs only on its intended branch
- `lz_prod` and `prod` remain gated on push to `main` only

**Technical decisions:**
- Job-level `if:` conditions keep a single workflow file with a clear branch-to-environment mapping, avoiding duplication into two separate workflow files
- This completes the GitFlow apply loop: feature → dev (auto-applies dev) → main (auto-applies prod)

---

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ⚠️   CHANGE OF DIRECTION                                                  ║
║                                                                              ║
║   At this point, the job-finder infrastructure was extracted into a          ║
║   standalone, reusable template (azure-terraform-template).                  ║
║                                                                              ║
║   Motivation: the Terraform foundation (OIDC CI/CD, GitFlow, reviewer        ║
║   agent, naming conventions) was project-agnostic and worth sharing.         ║
║   Rather than keeping it buried in a portfolio repo, it was published as     ║
║   a proper GitHub Template Repository.                                       ║
║                                                                              ║
║   PRs #15–18 below belong to that template phase.                            ║
║   Job-finder development resumes after MILESTONE 0 COMPLETE.                 ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

### PR #15 — chore: transform codebase into reusable infrastructure template
**Date:** 2026-04-30

**What was done:**
- Replaced all hardcoded project-specific values across all four environments with Terraform variables: `project` (`jf`), `location_short` (`frc`), `location` (`francecentral`), `owner` (email)
- Added the three new variables to `variables.tf` of each environment with `type`, `description`, and `default = "CHANGE_ME"` to make the template intent explicit
- Moved the concrete values into `terraform.tfvars` of each environment; replaced `tenant_id` and `subscription_id` values with `CHANGE_ME` as well
- Replaced hardcoded storage account names in all four `backend.tf` files with `CHANGE_ME` and a comment explaining the Terraform variable limitation
- Added explanatory comments to every Terraform file (modules + all four environments) and all three GitHub Actions workflows — documenting the WHY behind each block for developers discovering the template
- Added required tags (`environment`, `project`, `owner`) to all previously untagged resources: `azurerm_resource_group` and `azurerm_key_vault` in `lz_dev/main.tf` and `lz_prod/main.tf`, `azurerm_virtual_network` in `lz_dev/network.tf` and `lz_prod/network.tf`, and all three resource groups in `dev/resourcegroups.tf` and `prod/resourcegroups.tf`
- Bumped the reviewer agent Claude model from `claude-sonnet-4-5` to `claude-sonnet-4-6`
- Wrapped the reviewer agent's API call and GitHub post in a `try/except` block that prints an explicit error message and calls `sys.exit(1)` so the GitHub Actions job fails visibly on error instead of passing silently
- Extended the `try` block to also cover file reads and payload construction, so any I/O error is caught and reported with the same mechanism

**Technical decisions:**
- `default = "CHANGE_ME"` rather than no default: keeps `terraform validate` working without a tfvars file while making the required substitution obvious to anyone cloning the template
- `terraform.tfvars` are committed (already allowed by `.gitignore` negation rules) because the values they carry are non-sensitive — secrets remain in CI/CD environment variables and GitHub secrets
- Backend configuration cannot use Terraform variables; `CHANGE_ME` literals with an explanatory comment are the only viable approach
- `azurerm_subnet` intentionally excluded from tagging — the resource type does not support a `tags` block in the azurerm provider

---

### PR #16 — feat: add variable validation and GETTING_STARTED guide
**Date:** 2026-04-30

**What was done:**
- Added `validation` blocks to all four `variables.tf` files (`lz_dev`, `dev`, `lz_prod`, `prod`) for the four template variables: `project` (2-4 lowercase letters), `location_short` (2-4 lowercase letters), `location` (not CHANGE_ME), `owner` (must contain @) — any remaining placeholder value is caught at `terraform plan` time with an actionable error message
- Created `GETTING_STARTED.md` at the repo root with a five-step onboarding guide: Azure resource creation (state storage + OIDC service principal), GitHub configuration (secrets, variables, environments), CHANGE_ME substitution checklist, local `terraform init` verification, and first PR walkthrough

**Technical decisions:**
- `can(regex(...))` is used for the regex-based validations (project, location_short, owner) rather than a plain `!=` check — the regex implicitly rejects CHANGE_ME without a separate condition
- `location` uses an explicit `!= "CHANGE_ME"` check since any non-empty string is a valid Azure region name and a regex would be too restrictive
- Validation blocks are evaluated during `terraform plan` and `terraform apply` using the resolved variable values (tfvars or environment) — a clone with unfilled CHANGE_ME defaults will fail at plan time with an actionable error message, which is the intended behavior
- Each variable has its own validation block rather than a single combined check because Terraform only reports the first validation failure it encounters — separate blocks ensure each unfilled placeholder produces its own distinct error message
- The `owner` validation uses `^[^@]+@[^@]+\.[^@]+$` (requires a domain extension) rather than the looser `.+@.+` — this rejects values like `user@local` that contain `@` but are not valid email addresses

---

### PR #17 — docs: add professional README and reset DOC.md as template changelog
**Date:** 2026-04-30

**What was done:**
- Replaced the placeholder `README.md` (`# job-finder`) with a professional template README: CI/CD status badges, feature list, ASCII architecture diagram, repo structure, quick start (3 commands), CI/CD workflows table, and tech stack
- Reset `DOC.md` from a project-specific PR log to a template changelog starting at `v0.1.0`, summarizing everything the initial release provides

**Technical decisions:**
- Quick start intentionally uses "Use this template" wording — the repo is marked as a GitHub Template Repository, not meant to be forked
- `DOC.md` is reset rather than archived so template users start with a clean log; the full job-finder project history is preserved separately in `DOC_job-finder.md`

---

### PR #18 — release: v0.1.0 — initial template release
**Date:** 2026-04-30

**What was done:**
- Promoted `dev` to `main`, marking the v0.1.0 release of `azure-terraform-template` — the first complete, production-ready version of the template

**What's included in this release:**

- **Template transformation (PR #15):** full parameterization via `terraform.tfvars` with `CHANGE_ME` defaults, explanatory comments across all Terraform files and CI/CD workflows, required tags on all resources, reviewer agent bumped to `claude-sonnet-4-6` with `try/except` error handling and OIDC-only provider config
- **Validation and onboarding (PR #16):** variable validation blocks in all four `variables.tf` catching unfilled placeholders at plan time, `GETTING_STARTED.md` covering Azure OIDC setup (App Registration, 4 federated credentials, 2 role assignments), GitHub bot account setup, CHANGE_ME substitution checklist, and local init verification
- **Documentation (PR #17):** professional `README.md` with architecture diagram, repo structure, quick start, CI/CD workflow table, and tech stack; `DOC.md` reset as a template changelog
- **Earlier work (PRs #10, #13, #14):** Azure Policy allowed-locations module applied at subscription scope across all 4 environments; GitHub Actions bumped to `@v4` with `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24`; Terraform Apply extended to auto-apply dev environments on push to `dev`

**Technical decisions:**
- Repo renamed from `job-finder` to `azure-terraform-template` on GitHub and marked as a Template Repository
- The reviewer agent's `workflow_run` trigger requires the workflow file to be on the default branch (`main`) — this release makes the agent fully operational for all future template users

---

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ✅  MILESTONE 0 COMPLETE — azure-terraform-template v0.1.0 released       ║
║                                                                              ║
║   The template is production-ready, publicly available, and reusable.       ║
║   Terraform foundation · OIDC CI/CD · Claude reviewer agent · Onboarding   ║
║                                                                              ║
║   ▶▶  MILESTONE 1 STARTS — resuming job-finder development                 ║
║                                                                              ║
║   Repo: vbo-cloud/job-finder (created from azure-terraform-template)        ║
║   Goal: build the application infrastructure on top of the template         ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   ▶▶  RESUMING THE JOB-FINDER PROJECT                                       │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

### PR #19 — docs: add architecture documentation (ADRs, ROADMAP, SUMMARY)
**Date:** 2026-05-03

**What was done:**
- Added 13 Architecture Decision Records (`docs/adr/ADR-001` through `ADR-013`) covering every major technical choice for the job-finder application: database (PostgreSQL on Azure), compute platform (AKS), vector search (pgvector), schema migration (Alembic), container registry (ACR), LLM provider (Claude API), agent orchestration (LangGraph), embedding model (text-embedding-3-small), API framework (FastAPI), job offer collection (scraping via Playwright), user authentication (Clerk), monitoring (Azure Monitor + Prometheus), and Git/Terraform CI/CD (existing template)
- Added `docs/ROADMAP.md` listing the planned milestones and their order of delivery
- Added `docs/adr/SUMMARY.md` as an index table linking each ADR to its title and decision outcome

**Technical decisions:**
- ADRs are the single authoritative source for architectural choices — all decisions are documented before implementation begins
- `SUMMARY.md` provides a quick overview so contributors don't have to read all 13 ADRs to understand the stack
- Documentation lives in `docs/` to keep the repo root clean
