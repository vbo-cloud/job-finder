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

→ Enforced via the `conventions-terraform` skill (`.claude/skills/conventions-terraform/`). Consult it before writing or editing any Terraform code.

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

### Enforcement via hooks

The rules above that are mechanically checkable are enforced by a `PreToolUse` hook on
the Bash tool (`.claude/settings.json` → `.claude/hooks/pre_bash_guard.py`), not just
documented here. It blocks, for either Claude instance:
- Direct `git push` to `main`/`dev`
- Force-push without `--force-with-lease`
- `git merge` used to catch up a branch (the `--ff-only` local sync in the workflow above stays allowed)
- Local `terraform apply`/`terraform destroy` (CI-only, see Terraform Conventions)
- Mutating Azure CLI commands (`az ... create/update/delete/set/remove/assign/deploy/restore/purge/...`) — read-only verbs (`show`, `list`, `get`...) stay allowed
- Mutating Azure PowerShell cmdlets (`New-Az*`, `Remove-Az*`, `Set-Az*`, `Update-Az*`)
- `gh pr create` if `docs/JOURNAL.md` wasn't updated on the branch, if any commit since the base branch is a WIP marker or doesn't follow Conventional Commits, or if the `doc-writer` subagent hasn't run since the last edit (see Reviewer subagents below)

This same hook applies identically inside `claude-code-action` CI runs (see `.github/CLAUDE_ACTION.md`), since the action runs the real Claude Code engine against the checked-out repo and reads the same `.claude/settings.json`. The Azure CLI/PowerShell verb list is a backstop, not exhaustive — it covers common mutating verb families, not every possible destructive command; `reviewer-infra`'s own judgment and the CI-only apply pipeline remain the primary controls.

A `PostToolUse` hook (`.claude/hooks/post_edit_format.py`) best-effort runs `terraform fmt`
after editing a `.tf` file and `eslint --fix` after editing a frontend file, to preempt
CI formatting failures. It never blocks — PostToolUse can't undo an edit that already happened.

Known limitation: hooks can't technically distinguish a Claude Cowork session from a
Claude Code session (no reliable signal exposed to hook scripts for that), so the
Cowork/Code role boundary described above is still enforced by instruction only, not
by a hook.

## Python Conventions

→ Enforced via the `conventions-python` skill (`.claude/skills/conventions-python/`). Consult it before writing or editing any Python code.

---

## SQL / Alembic Conventions

→ Enforced via the `conventions-sql` skill (`.claude/skills/conventions-sql/`). Consult it before writing or editing any SQLAlchemy models or Alembic migrations.

---

## Frontend / Next.js Conventions

→ Enforced via the `conventions-frontend` skill (`.claude/skills/conventions-frontend/`). Consult it before writing or editing any Next.js / React / TypeScript frontend code.

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

### Documentation subagent

`doc-writer` (`.claude/agents/doc-writer.md`) checks that docstrings, WHY-comments,
and the `docs/JOURNAL.md` entry for the current PR are accurate and complete —
and, unlike the reviewer subagents below, has `Edit`/`Write` and fixes what it
finds directly instead of only reporting it. It's meant to run before the
reviewers, around the time a PR is opened.

**Enforcement:** the same `pre_bash_guard.py` hook that requires `docs/JOURNAL.md`
to be part of the PR also blocks `gh pr create` unless `doc-writer` was called
(via the `Task`/`Agent` tool) after the last `Edit`/`Write`/`NotebookEdit` in the
session transcript. This guarantees it ran before the PR before opening it, but
does **not** mechanically guarantee it ran *before* the reviewer subagents
specifically — that ordering is enforced by instruction only (`doc-writer`'s own
description says to call it before the reviewers), since the reviewers are
Stop-hook-enforced (must run before the session ends) rather than tied to
`gh pr create` itself, and reliably sequencing two independently-triggered
subagents relative to each other from a hook wasn't worth the added fragility.

### Reviewer subagents

Three read-only reviewer subagents live in `.claude/agents/`, one per layer:
- **`reviewer-frontend`** — `.ts`/`.tsx`/`.jsx`/`.js` under `JobFinder/frontend/`, checked against the `conventions-frontend` skill. Tools: `Read, Grep, Glob` only — no Edit/Write/Bash, so it is structurally unable to modify anything.
- **`reviewer-backend`** — `.py` under `JobFinder/python/` (excluding migrations), checked against `conventions-python`. Same read-only tool set.
- **`reviewer-infra`** — `.tf`, Alembic migrations, PowerShell/Azure CLI scripts, checked against `conventions-terraform` and `conventions-sql`. Tools: `Read, Grep, Glob, Bash` — Bash is scoped by instruction to read-only commands (`terraform plan`, `terraform validate`, `terraform fmt -check`, `tflint`); it must never run `terraform apply` or a mutating `az`/`New-Az*`/`Set-Az*`/`Remove-Az*` command. The `pre_bash_guard.py` hook independently blocks `terraform apply` regardless of caller, but that's a backstop, not the primary control.

Every reviewer's job is to report findings (verdict + `file:line` + violated rule), never to fix them itself.

**Enforcement:** a `Stop` hook (`.claude/hooks/require_reviewer.py`) inspects the session transcript before Claude finishes responding. Per category, it tracks the position of the *last* edit and the position of the *last* call to the matching reviewer subagent — if a category was edited more recently than its reviewer was last called, the stop is blocked. It then also reads the reviewer's actual report text (the `tool_result` of that last call) and blocks again if it doesn't read as `APPROUVÉ` (contains `CHANGEMENTS REQUIS`, or the verdict can't be identified at all — ambiguous is treated as not-approved here, on purpose). Concretely: calling the reviewer once doesn't cover edits made afterwards, and getting a `CHANGEMENTS REQUIS` verdict doesn't let the task end either — both require the loop to continue (fix → re-review → `APPROUVÉ`) before Claude can stop.

Known limitation: this is a keyword match on the reviewer's own report text, not semantic understanding of whether the underlying issues were actually fixed — it can't tell a genuine fix from a reviewer that was talked into changing its verdict. It also fails open (allows the stop) if the transcript itself can't be parsed (unreadable file, unexpected schema) so a structural mismatch never leaves a session stuck — but an ambiguous or negative verdict on a successfully-parsed report is deliberately NOT treated as one of those failures, and blocks. Treat it as a safety net on top of the instruction to call reviewers and act on their feedback, not as a substitute for it.

**Cycle limit:** each reviewer gets at most 3 consecutive blocks (a small counter persisted next to the transcript, reset as soon as that reviewer comes back `APPROUVÉ` or stops being touched). Past that, the hook stops enforcing that specific reviewer and lets the stop through with a non-blocking warning instead of blocking forever — this deliberately does *not* rely on Claude Code's `stop_hook_active` flag, because that flag lets a single retry through unconditionally regardless of whether anything actually changed, which would have defeated the verdict check above.