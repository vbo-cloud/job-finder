# Getting Started

This template provisions an Azure infrastructure foundation (landing zones + application environments) with Terraform, GitHub Actions CI/CD, and an automated Claude code reviewer.

---

## Prerequisites

- **Azure subscription** — a free account works for initial setup
- **GitHub account** with Actions enabled on your repository
- **Terraform CLI** ≥ 1.3 — [install guide](https://developer.hashicorp.com/terraform/downloads)
- **Azure CLI** — [install guide](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)

---

## Step 1 — Create Azure resources

### 1.1 Terraform state storage

Terraform stores a state file that tracks which resources it manages. This file must live somewhere persistent — an Azure Storage Account is the standard choice.

```bash
# Log in first if you haven't already
az login

# Resource group to hold the state backend.
# This resource group is created manually and is NOT managed by Terraform itself.
az group create --name rg-tfstate --location francecentral

# Storage account — name must be globally unique, no hyphens, max 24 chars.
# Write this name down: you'll need it in Step 3 (backend.tf).
az storage account create \
  --name <your-storage-account-name> \
  --resource-group rg-tfstate \
  --location francecentral \
  --sku Standard_LRS \
  --allow-blob-public-access false

# Container that will hold one .tfstate file per environment
az storage container create \
  --name tfstate \
  --account-name <your-storage-account-name>

# Verify the storage account is reachable before moving on
az storage account show-connection-string \
  --name <your-storage-account-name> \
  --resource-group rg-tfstate \
  --query connectionString -o tsv
# A connection string starting with "DefaultEndpointsProtocol=https" confirms success.
```

### 1.2 App Registration and Service Principal

GitHub Actions needs an Azure identity to call the Azure API. The recommended approach is **OIDC (OpenID Connect)**: GitHub generates a short-lived token per job — no passwords or secrets to rotate.

This requires two Azure objects:
- An **App Registration** (the identity definition — like a user account)
- A **Service Principal** (the concrete instance of that identity in your subscription — like the user's membership in an org)

```bash
# Retrieve your subscription ID — you'll need it in several commands below
az account show --query id -o tsv
# → copy the output, e.g. xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Create the App Registration.
# This is the identity that GitHub Actions will authenticate as.
az ad app create --display-name sp-<project>-github
# → copy the "appId" from the output (this is ARM_CLIENT_ID)
# ⚠️  Use the appId, NOT the objectId — they look similar but are different identifiers.
#    appId  (also called client_id): xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx  ← this one
#    id / objectId:                  yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy  ← not this one

# Create the Service Principal linked to the App Registration.
# Replace <app-id> with the appId from the previous command.
az ad sp create --id <app-id>
```

### 1.3 Role assignments

The Service Principal needs two roles at the subscription level:

- **Contributor** — create, update, and delete resources (VNets, Key Vaults, AKS, etc.)
- **Resource Policy Contributor** — create and assign Azure Policy definitions (required by the allowed-locations policy module)

```bash
# Contributor — allows Terraform to manage all resources in the subscription
az role assignment create \
  --assignee <app-id> \
  --role Contributor \
  --scope /subscriptions/<subscription-id>

# Resource Policy Contributor — allows Terraform to create and assign Azure Policy definitions
az role assignment create \
  --assignee <app-id> \
  --role "Resource Policy Contributor" \
  --scope /subscriptions/<subscription-id>
```

> If you skip the second role, `terraform plan` will succeed but `terraform apply` will fail when it tries to create the policy assignment.

### 1.4 Federated credentials (OIDC)

A federated credential tells Azure: "trust a token from GitHub Actions if its `subject` claim matches this pattern." You need one credential per trigger type because GitHub generates a different subject depending on how the workflow was started.

This template uses four triggers — one per CI/CD scenario:

| Credential name | GitHub subject | Used by |
|-----------------|---------------|---------|
| `github-oidc-pr` | `repo:<org>/<repo>:pull_request` | `terraformPlan.yml` (runs on every PR) |
| `github-oidc-env-dev` | `repo:<org>/<repo>:environment:dev` | `terraformApply.yml` apply-dev job |
| `github-oidc-env-prod` | `repo:<org>/<repo>:environment:prod` | `terraformApply.yml` apply-prod job |
| `github-oidc-main` | `repo:<org>/<repo>:ref:refs/heads/main` | future workflows targeting main directly |

```bash
# Replace <app-id> with your App Registration appId
# Replace <org>/<repo> with your GitHub org and repo name (e.g. vbo-cloud/job-finder)

# 1. Pull requests — Terraform Plan runs on every PR
az ad app federated-credential create \
  --id <app-id> \
  --parameters '{
    "name": "github-oidc-pr",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:<org>/<repo>:pull_request",
    "audiences": ["api://AzureADTokenExchange"]
  }'

# 2. GitHub environment "dev" — Terraform Apply for dev environments
az ad app federated-credential create \
  --id <app-id> \
  --parameters '{
    "name": "github-oidc-env-dev",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:<org>/<repo>:environment:dev",
    "audiences": ["api://AzureADTokenExchange"]
  }'

# 3. GitHub environment "prod" — Terraform Apply for prod environments
az ad app federated-credential create \
  --id <app-id> \
  --parameters '{
    "name": "github-oidc-env-prod",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:<org>/<repo>:environment:prod",
    "audiences": ["api://AzureADTokenExchange"]
  }'

# 4. Push to main — for any future workflow triggered directly on main
az ad app federated-credential create \
  --id <app-id> \
  --parameters '{
    "name": "github-oidc-main",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:<org>/<repo>:ref:refs/heads/main",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

> **Why four credentials and not one?** Azure matches the `subject` claim exactly — there is no wildcard. A PR run has subject `pull_request`, an environment-gated run has subject `environment:dev`, etc. A single credential can only match one subject pattern.

### 1.5 Collect the three values for GitHub

You now have everything you need for Step 2. Run these commands to retrieve the values:

```bash
# ARM_CLIENT_ID — the App Registration appId
az ad app list --display-name sp-<project>-github --query '[0].appId' -o tsv

# ARM_TENANT_ID — your Azure AD tenant
az account show --query tenantId -o tsv

# ARM_SUBSCRIPTION_ID — your Azure subscription
az account show --query id -o tsv
```

These three values are **not secrets** — they are identifiers, not credentials. The actual authentication happens via the short-lived OIDC token that GitHub generates per job. Store them as **GitHub Actions variables** (not secrets) in Step 2.

---

## Step 2 — Configure GitHub

### 2.1 Create a bot account for the reviewer agent

The reviewer agent posts reviews and comments on PRs. It cannot use the built-in `GITHUB_TOKEN` for this — a token cannot approve the PR of the workflow that generated it. You need a **separate GitHub account** that acts as the bot.

1. Create a new GitHub account (e.g. `your-project-reviewer-agent`) with a dedicated email address
2. Add it as a collaborator on your repository with **Write** access:
   - Repository → Settings → Collaborators → Add people → search the bot account → select **Write**
3. Accept the invitation from the bot account
4. Log in as the bot account and generate a **Personal Access Token (classic)**:
   - Settings → Developer settings → Personal access tokens → Tokens (classic) → Generate new token
   - Scopes to enable: `repo` (full), `pull_requests: write`
   - Set an expiration and copy the token — you will not see it again
5. Log back into your main account and add the token as a repository secret named `REVIEWER_GITHUB_TOKEN` (see below)

> Write access is required because posting a pull request review (approve / request changes) needs more than read-only scope — the bot account must be a recognized collaborator on the repository.

### 2.2 Secrets (Settings → Secrets and variables → Actions → Secrets)

| Secret | Value |
|--------|-------|
| `CLAUDE_API_KEY` | Your Anthropic API key (powers the reviewer agent) |
| `REVIEWER_GITHUB_TOKEN` | PAT generated in step 2.1 above |

### 2.3 Variables (Settings → Secrets and variables → Actions → Variables)

These are identifiers, not credentials — store them as **Variables**, not Secrets:

| Variable | Value |
|----------|-------|
| `AZURE_CLIENT_ID` | App Registration `appId` from Step 1 |
| `AZURE_TENANT_ID` | Your Azure tenant ID from Step 1 |
| `AZURE_SUBSCRIPTION_ID` | Your Azure subscription ID from Step 1 |

### 2.4 Environments (Settings → Environments)

Create two environments named **`dev`** and **`prod`**.  
Add required reviewers to **`prod`** to gate production applies behind manual approval before Terraform runs.

---

## Step 3 — Replace all CHANGE_ME values

**`backend.tf`** — 4 files (`lz_dev`, `dev`, `lz_prod`, `prod`):

```hcl
storage_account_name = "your-storage-account-name"  # from Step 1
```

**`terraform.tfvars`** — 4 files (`lz_dev`, `dev`, `lz_prod`, `prod`):

```hcl
project        = "jf"                       # 2-4 lowercase letters, used in all resource names
location       = "francecentral"            # Azure region for resource deployment
location_short = "frc"                      # Short region code used in resource names
owner          = "you@example.com"          # Applied to all resource tags
```

> Validation blocks in `variables.tf` will catch any remaining placeholder at `terraform plan` time.

---

## Step 4 — Run terraform init locally to verify

Run these commands from the **root of the cloned repository** (the directory that contains `JobFinder/`, `DOC.md`, etc.). The `-chdir` flag tells Terraform which environment directory to use, so the working directory never changes.

```bash
# Navigate to the repo root first
cd /path/to/job-finder

terraform -chdir=JobFinder/Terraform/envs/lz_dev init && terraform -chdir=JobFinder/Terraform/envs/lz_dev validate
terraform -chdir=JobFinder/Terraform/envs/dev     init && terraform -chdir=JobFinder/Terraform/envs/dev     validate
terraform -chdir=JobFinder/Terraform/envs/lz_prod init && terraform -chdir=JobFinder/Terraform/envs/lz_prod validate
terraform -chdir=JobFinder/Terraform/envs/prod     init && terraform -chdir=JobFinder/Terraform/envs/prod     validate
```

A successful `init` + `validate` on all four environments confirms the backend connection, provider download, and variable values are correct.

---

## Step 5 — Open your first PR and watch the CI/CD run

1. Create a feature branch from `dev`:
   ```bash
   git checkout -b feature/my-first-change dev
   ```
2. Make a small change — for example, add a tag to a resource group in `dev/resourcegroups.tf`
3. Push and open a PR targeting `dev`
4. **Terraform Plan** runs automatically across all 4 environments in parallel
5. **Claude Reviewer Agent** posts an automated review with approve or request-changes
6. Merge to `dev` → `apply-dev` applies `lz_dev` and `dev` automatically
7. When ready for production: open a PR from `dev` to `main`, get approval, merge → `apply-prod` runs (gated by the `prod` environment)
