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
- Cloud provider: Azure only — no AWS, GCP, or other provider resources allowed
- Environment folder names use underscores (`lz_dev`, `dev`). Tag values and Azure resource names use hyphens (`lz-dev`, `rg-jf-dev-frc`)
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

### Typage et documentation
- Type hints obligatoires sur toutes les fonctions — paramètres et valeur de retour
- Docstrings Google style sur tous les modules, classes et fonctions publiques
- Les fonctions sans docstring sont considérées incomplètes

### Constantes
- Les constantes (noms en MAJUSCULES) sont déclarées immédiatement après les imports, avant tout autre code de niveau module (loggers, variables d'environnement, initialisations de clients)

### Logging
- Utiliser `structlog` exclusivement — jamais `print()` ni `logging` standard
- JSON en production, coloré en dev (contrôlé par `LOG_LEVEL` depuis l'environnement)
- Chaque module configure son logger en tête de fichier : `logger = structlog.get_logger()`
- Les logs d'erreur incluent toujours l'exception : `logger.error("msg", exc_info=True)`

### Variables d'environnement
- Chargées au démarrage du module (niveau module, pas dans les fonctions)
- Une variable manquante lève une `ValueError` explicite avec le nom de la variable
- Ne jamais utiliser de valeur par défaut silencieuse pour une variable critique

### Gestion des erreurs
- Jamais de `except Exception` nu — toujours catcher une exception spécifique
- Dans un bloc `except` dont le seul but est de logger et relancer, utiliser `raise` nu — jamais `raise X(str(e)) from e`. `raise` nu préserve le type exact de l'exception originale. `raise X(str(e)) from e` n'est approprié que si on veut volontairement changer le type de l'exception (cas rare).
- Les ressources (sessions DB, clients Service Bus) sont toujours gérées via context managers (`with`)
- Toute fonction effectuant un appel externe (API, base de données, réseau) doit logger son entrée avec `logger.info` et entourer l'appel d'un `try/except` sur l'exception spécifique de la librairie concernée, avec `logger.error(..., exc_info=True)` et re-raise via `raise ... from e`

### Style
- f-strings exclusivement — pas de `.format()` ni de `%`
- Pas de logique métier dans `main.py` — il orchestre uniquement (appels aux autres modules)
- Une fonction = une responsabilité. Si une fonction fait plus de 40 lignes, la découper.

---

## SQL / Alembic Conventions

### Modèles SQLAlchemy
- Clés primaires : UUID v4 (`uuid.uuid4`) — jamais d'autoincrement
- Toutes les tables ont `created_at` (DateTime, default `utcnow`, `nullable=False`)
- Nommage des tables : snake_case pluriel (`offers`, `cvs`, `matches`)
- `nullable=True` et `nullable=False` toujours explicites — jamais implicites
- Toutes les colonnes DateTime utilisent `DateTime(timezone=True)` (mappe vers TIMESTAMPTZ en PostgreSQL) — jamais `DateTime` seul. Compatible avec `datetime.now(timezone.utc)`.

### Nommage des contraintes
- Index : `ix_{table}_{colonne}` (ex: `ix_offers_ft_id`)
- Contraintes d'unicité : `uq_{table}_{colonne}` (ex: `uq_offers_ft_id`)
- Clés étrangères : `fk_{table}_{colonne}_ref_{table_cible}` (ex: `fk_matches_cv_id_ref_cvs`)

### Migrations Alembic
- Une migration = un changement logique — jamais plusieurs features dans la même migration
- Nommage fichier : `{NNN}_{description_courte}.py` (ex: `001_initial_schema.py`)
- `down_revision` toujours renseigné — chaque migration doit implémenter `downgrade()`
- `alembic upgrade head` appelé au démarrage de chaque agent (idempotent)

---

## Frontend / Next.js Conventions

### Server Components vs Client Components
- **Par défaut, tout composant est un Server Component** — Next.js App Router. Ne jamais ajouter `"use client"` par réflexe.
- Ajouter `"use client"` uniquement si le composant utilise : hooks React (`useState`, `useEffect`, `useMsal`…), event handlers (`onClick`, `onChange`…), ou APIs navigateur (`window`, `document`, `localStorage`).
- Les composants MSAL (`useIsAuthenticated`, `useMsal`, `MsalProvider`) sont toujours `"use client"`.
- Pousser `"use client"` aussi bas que possible dans l'arbre : extraire la partie interactive dans un sous-composant plutôt que de marquer toute une page.

### Utilitaire `cn()` — classes Tailwind conditionnelles
- **Toujours utiliser `cn()` pour les classes conditionnelles**, jamais de concaténation de strings ou de template literals.
- `cn()` est défini dans `lib/utils.ts` (`clsx` + `tailwind-merge`) — dépendances : `clsx`, `tailwind-merge`.
- Exemple : `className={cn("rounded px-4 py-2", isActive && "bg-blue-600", className)}`
- Raison : `tailwind-merge` résout les conflits Tailwind silencieux (ex. `bg-blue-500 bg-red-500` → une seule couleur appliquée).

### Dynamic import — librairies lourdes et dépendantes du navigateur
- **Three.js et toute librairie accédant à `window`/`document` doivent être importées dynamiquement avec `ssr: false`.**
- Syntaxe obligatoire :
  ```typescript
  const OrbitAnimation = dynamic(
    () => import("@/components/upload/OrbitAnimation"),
    { ssr: false, loading: () => <div className="h-full w-full" /> }
  );
  ```
- Le composant cible (`OrbitAnimation.tsx`) doit avoir sa propre directive `"use client"`.
- Raison : Three.js appelle `window` à l'import → plante en SSR. Sans `dynamic`, le bundle initial s'alourdit inutilement.

### Three.js — cleanup obligatoire
- Tout composant Three.js **doit** libérer les ressources GPU dans le return de `useEffect`. Une fuite mémoire GPU n'est pas récupérée par le garbage collector JavaScript.
  ```typescript
  useEffect(() => {
    const renderer = new THREE.WebGLRenderer({ canvas: canvasRef.current! });
    const geometry = new THREE.SphereGeometry(1, 32, 32);
    const material = new THREE.MeshStandardMaterial();
    // ... setup scene, animation loop ...
    return () => {
      renderer.dispose();
      geometry.dispose();
      material.dispose();
    };
  }, []);
  ```
- Arrêter la boucle d'animation (`cancelAnimationFrame`) dans le même cleanup.

### Types API — source unique
- Les types des réponses API (ex. `ProfileData`, `CVData`, `MatchData`) sont définis dans **`lib/api/types.ts`**, jamais inline dans les pages.
- Les pages importent les types depuis `@/lib/api/types`.

### `next/image` et `next/font` — jamais de primitives brutes
- **Jamais de balise `<img>` brute** : toujours `next/image` (optimisation WebP, lazy loading, prévention layout shift).
- **Jamais de `<link>` Google Fonts** : toujours `next/font/google` dans `layout.tsx` (intégration au build, zéro flash).
- Exception : SVG inline décoratifs ne nécessitent pas `next/image`.

### Appels API backend
- **Tout appel vers la webapp FastAPI passe exclusivement par `apiClient`** (`lib/api/client.ts`), jamais par `fetch()` direct.
- Raison : `apiClient` injecte automatiquement le Bearer token via l'intercepteur Axios.
- `fetch()` natif est acceptable pour des ressources publiques externes (CDN, APIs tierces sans auth).

### Variables d'environnement publiques (`NEXT_PUBLIC_*`)
- **Toujours référencer une variable `NEXT_PUBLIC_*` en toutes lettres et statiquement** : `process.env.NEXT_PUBLIC_FOO`. Jamais via un accès dynamique (`process.env[name]`, déstructuration calculée, etc.).
- Raison : Next.js n'inline les `NEXT_PUBLIC_*` dans le bundle **client** qu'au prix d'un remplacement textuel à la compilation, qui n'a lieu **que** sur des références statiques. Un accès dynamique laisse la valeur `undefined` côté navigateur (alors qu'elle fonctionne côté serveur) → la page plante au chargement. Si une validation centralisée est souhaitée, lire la valeur statiquement puis la passer à une fonction de validation (ex. `requireEnv("NEXT_PUBLIC_FOO", process.env.NEXT_PUBLIC_FOO)`).
- Les variables sans `NEXT_PUBLIC_` sont uniquement accessibles côté serveur (Server Components, Route Handlers, Server Actions) — elles sont `undefined` dans un Client Component.

### Fichiers de route spéciaux — `loading.tsx` et `error.tsx`
- Toute route qui effectue un fetch de données **doit** avoir un `loading.tsx` (Suspense automatique) et un `error.tsx` (Error Boundary automatique).
- `loading.tsx` : skeleton ou spinner affiché pendant le fetch. Évite de gérer `isLoading` manuellement dans chaque page.
- `error.tsx` : composant `"use client"` avec `{ error, reset }` props. Affiche un message d'erreur et un bouton "Réessayer".

### Groupes de routes — layouts partagés sans impact URL
- Utiliser des route groups `(nom)/` pour partager un layout entre plusieurs pages sans modifier l'URL.
- Exemple : `app/(authenticated)/layout.tsx` — garde d'authentification partagée entre `/library`, `/cv/[id]`, `/profile`.
- Évite de dupliquer la logique de garde dans chaque `page.tsx`.

### Nommage des fichiers
- Composants React : `PascalCase.tsx` (`LoginButton.tsx`, `CVDropzone.tsx`, `OfferCard.tsx`)
- Utilitaires, config, clients : `camelCase.ts` (`msalConfig.ts`, `client.ts`, `utils.ts`)
- Segments de route : `kebab-case/` (`cv/[id]/`, `app/(authenticated)/`)
- Pas de fichier `index.ts` dans les composants (Next.js résout directement le nom de fichier)

### Taille et découpe des composants
- **Un composant = une responsabilité.** Si un composant dépasse ~80 lignes ou mélange deux préoccupations, le découper.
- Colocation : les sous-composants utilisés uniquement par une page vivent dans `app/<route>/_components/` (le `_` exclut le dossier du routing Next.js).
- Les composants réutilisables entre routes vivent dans `components/`.

### `useEffect` — exhaustivité des dépendances
- Ne jamais supprimer une dépendance du tableau pour faire taire ESLint (`react-hooks/exhaustive-deps`).
- Si une fonction cause des re-renders indésirables en dépendance, la stabiliser avec `useCallback`.
- Si une valeur change trop souvent, utiliser une ref (`useRef`) plutôt que de la supprimer des deps.

### `void` pour les promesses ignorées
- Préfixer par `void` les promesses dont on ignore délibérément le résultat dans les event handlers :
  `onClick={() => void handleSave()}`, `onClick={() => void instance.loginRedirect(loginRequest)}`
- Évite le warning TypeScript `no-floating-promises` et documente l'intention explicitement.

### Accessibilité minimale
- Tout bouton sans texte visible a un `aria-label` explicite.
- Toute image `next/image` a un `alt` (chaîne vide `alt=""` si purement décorative).
- Tous les éléments interactifs ont des styles focus visibles : `focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none`.
- HTML sémantique : `<header>`, `<nav>`, `<main>`, `<section>` selon le contexte — pas de `<div>` à la place.

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