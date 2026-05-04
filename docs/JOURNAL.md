# Journal de bord — job-finder

Ce fichier trace l'évolution du projet PR par PR. Il est mis à jour à chaque PR mergée.
Le contenu historique (template phase, PRs #1–18) est conservé en anglais. Les nouvelles entrées sont en français.

---

## Mise en place initiale

Réalisée avant l'ouverture du premier PR.

### Sécurité de base
- Mots de passe et codes de récupération stockés dans un gestionnaire de mots de passe
- Tous les mots de passe existants rotés à complexité maximale
- 2FA activé avec une application Authenticator sur tous les comptes

### Domaine et email
- Domaine professionnel enregistré
- Adresse email professionnelle associée au domaine créée

### Tenant Azure et abonnements
- Nouveau tenant Azure créé
- Resource group, storage account et blob container créés pour le state Terraform distant
- Resource locks appliqués sur le resource group et le storage account
- Un Management Group créé pour le projet, avec un sous-groupe et un abonnement par environnement (Dev et Prod)

### Dépôt Git
- Nouvelle organisation GitHub et dépôt privé créés
- `.gitignore` configuré pour Terraform (state files, `.terraform/`, etc.)
- Authentification par clé SSH configurée

### Structure Terraform de base
- Deux environnements : `dev` et `prod`
- Un dossier landing zone (`lz_dev`, `lz_prod`) et un dossier infrastructure applicative par environnement
- Backend state distant via le storage account Azure créé ci-dessus

### Pipelines CI/CD
- Credentials Azure créés (service principal + OIDC) pour authentifier les runners GitHub Actions
- **Workflow Terraform Plan** — se déclenche sur chaque PR, tourne sur les 4 environnements (`lz-dev`, `dev`, `lz-prod`, `prod`) : `terraform init`, `fmt -check`, `validate`, `plan`
- **Workflow Terraform Apply** — se déclenche sur push vers `main`, tourne par environnement avec contexte spécifique ; exécute `terraform init` et `apply`
- Objectif : aucun apply manuel — toutes les modifications passent par la CI/CD

---

## Journal des PRs

### PR #1 — feat: migrate state backend and enforce resource naming convention
**Date :** 2026-04-29

**Réalisé :**
- Migration du state Terraform de local vers un backend Azure Storage distant (`stjftfstatefrc`, container `tfstate`), avec un state file par environnement
- Convention de nommage appliquée : `{type}-{projet}-{environnement}-{région}` (ex: `rg-jf-dev-frc`, `vnet-jf-lz-dev-frc`)
- Formatage Terraform corrigé sur tous les environnements et modules
- Suppression de `fail-fast: true` dans la matrix du workflow Plan

**Décisions techniques :**
- Chaque environnement a son propre state file pour isoler le blast radius
- Les storage accounts omettent les tirets et sont limités à 24 caractères (`stjftfstatefrc`)

---

### PR #2 — docs: add CLAUDE.md with project conventions
**Date :** 2026-04-29

**Réalisé :**
- Ajout de `CLAUDE.md` à la racine documentant les conventions du projet pour Claude Code : stack technique, règles de nommage Terraform, structure des modules, aperçu CI/CD, et règle no-local-apply
- Ajout d'une section Git workflow couvrant le branching, le rebase, et les Conventional Commits

**Décisions techniques :**
- `CLAUDE.md` est commité pour que les conventions soient accessibles à tous les contributeurs et à Claude Code dans toute session

---

### PR #3 — fix: compute module AWS artifact + scaffold prod environments
**Date :** 2026-04-29

**Réalisé :**
- Correction d'un artefact copy-paste dans `modules/compute/variables.tf` : remplacement du type d'instance AWS `t2.micro` par l'équivalent Azure (`Standard_B2s`)
- Scaffold des environnements `lz_prod` et `prod` en miroir de `lz_dev` / `dev`

**Décisions techniques :**
- `lz_prod` utilise l'espace d'adressage `10.1.0.0/16` pour éviter les conflits avec `lz_dev` (`10.0.0.0/16`)

---

### PR #4 — chore: add JOURNAL.md project log and enforce update rule in CLAUDE.md
**Date :** 2026-04-29

**Réalisé :**
- Ajout de `DOC.md` (renommé `docs/JOURNAL.md` en PR #19) : log de mise en place initiale + journal des PRs
- Ajout d'une règle dans `CLAUDE.md` imposant la mise à jour du journal à chaque PR

---

### PR #5 — chore: set up GitFlow and branch protection
**Date :** 2026-04-29

**Réalisé :**
- Création de la branche `dev` depuis `main`
- Ajout de la section Git Flow dans `CLAUDE.md` : stratégie de branches, versioning sémantique, workflow de release
- Branch protection rules sur `main` et `dev` : les 4 jobs de plan CI doivent passer avant le merge, force push et suppressions bloqués

**Décisions techniques :**
- `dev` est la branche d'intégration : toutes les features y mergent en premier ; `main` n'est touché qu'aux releases et hotfixes

---

### PR #6 — fix: correct JOURNAL.md branch protection note
**Date :** 2026-04-29

**Réalisé :**
- Correction de l'entrée PR #5 : la branch protection a été appliquée avec succès après la mise en public du repo

---

### PR #7 — ANNULÉE
**Date :** 2026-04-30 | **Titre :** docs: Add project description to README.md

Fermée sans merge. Mise à jour du README hors scope à ce stade.

---

### PR #8 — ANNULÉE
**Date :** 2026-04-30 | **Titre :** feat: Create PR reviewer agent

Fermée sans merge. Ciblait `main` au lieu de `dev`. Réouverte en PR #9.

---

### PR #9 — feat: Create PR reviewer agent
**Date :** 2026-04-30

**Réalisé :**
- Ajout de `.github/workflows/reviewerAgent.yml` : workflow déclenchée après Terraform Plan, récupère le diff et les logs de plan des 4 environnements, appelle l'API Claude, et poste la review directement sur la PR (approve / request changes)
- Ajout de `.github/reviewer-agent/system-prompt.md` : persona du reviewer, contexte projet, checklist de review, format de sortie structuré

**Décisions techniques :**
- Le workflow utilise `workflow_run` pour se déclencher après `Terraform Plan` — le reviewer a toujours l'output de plan disponible avant de commenter
- Le system prompt est envoyé avec `cache_control: ephemeral` pour bénéficier du prompt caching Claude
- Un `REVIEWER_GITHUB_TOKEN` dédié est utilisé — `GITHUB_TOKEN` ne peut pas approuver ses propres PRs
- Le diff envoyé à Claude est plafonné à 15 000 caractères et chaque log de plan à 6 000 caractères

---

### PR #10 — feat: Add Azure allowed-locations policy across all environments
**Date :** 2026-04-30

**Réalisé :**
- Module Terraform réutilisable `modules/policy/` avec `azurerm_policy_definition` et `azurerm_subscription_policy_assignment` scopée à la subscription
- Appelé depuis les 4 environnements via un fichier `policy.tf` dédié, restreignant les déploiements à `francecentral` et `northeurope`

**Décisions techniques :**
- Assignment au scope subscription (pas resource group) — couvre tous les resource groups actuels et futurs
- Les tags requis sont embarqués dans le champ `metadata` JSON (seule solution pour `azurerm_subscription_policy_assignment` qui n'a pas de bloc `tags`)

---

### PR #11 — docs: update JOURNAL.md entries
**Date :** 2026-04-30

Mise à jour du journal uniquement. Aucun changement de code.

---

### PR #12 — chore: sync dev to main to activate reviewer agent
**Date :** 2026-04-30

**Réalisé :**
- Merge de `dev` vers `main` pour rendre l'agent reviewer opérationnel — le trigger `workflow_run` ne se déclenche que sur les workflows présents sur la branche par défaut (`main`)

---

### PR #13 — chore: bump actions/checkout and setup-terraform to v4
**Date :** 2026-04-30

**Réalisé :**
- `actions/checkout@v3 → @v4` et `hashicorp/setup-terraform@v3 → @v4` dans les workflows Plan et Apply pour résoudre les warnings de dépréciation Node.js 20

---

### PR #14 — feat: trigger Terraform Apply on push to dev for dev environments
**Date :** 2026-04-30

**Réalisé :**
- Extension de `terraformApply.yml` pour se déclencher aussi sur push vers `dev`, appliquant automatiquement `lz_dev` et `dev` quand une feature branch est mergée
- Conditions `if: github.ref` au niveau des jobs pour que chaque job tourne uniquement sur sa branche cible

---

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ⚠️   CHANGEMENT DE DIRECTION                                               ║
║                                                                              ║
║   L'infrastructure job-finder a été extraite en template réutilisable       ║
║   (azure-terraform-template). Les PRs #15–18 appartiennent à cette phase.   ║
║   Le développement de job-finder reprend après MILESTONE 0 COMPLETE.        ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

### PR #15 — chore: transform codebase into reusable infrastructure template
**Date :** 2026-04-30

**Réalisé :**
- Remplacement de toutes les valeurs hardcodées par des variables Terraform avec `default = "CHANGE_ME"`
- Valeurs concrètes déplacées dans les `terraform.tfvars` de chaque environnement
- Commentaires explicatifs ajoutés sur tous les fichiers Terraform et workflows CI/CD
- Tags requis ajoutés sur toutes les ressources non taggées
- Modèle Claude du reviewer agent passé de `claude-sonnet-4-5` à `claude-sonnet-4-6`
- Appel API et post GitHub enveloppés dans un `try/except` avec `sys.exit(1)` sur erreur

---

### PR #16 — feat: add variable validation and GETTING_STARTED guide
**Date :** 2026-04-30

**Réalisé :**
- Blocs `validation` ajoutés dans les 4 `variables.tf` : `project` (2-4 lettres minuscules), `location_short`, `location` (pas CHANGE_ME), `owner` (doit contenir @)
- `GETTING_STARTED.md` créé : guide d'onboarding en 5 étapes (Azure OIDC, GitHub config, substitution CHANGE_ME, init local, première PR)

---

### PR #17 — docs: add professional README and reset DOC.md as template changelog
**Date :** 2026-04-30

**Réalisé :**
- `README.md` professionnel avec badges CI/CD, diagramme ASCII, structure du repo, quick start, table des workflows et stack technique
- `DOC.md` remis à zéro comme changelog du template à partir de `v0.1.0`

---

### PR #18 — release: v0.1.0 — initial template release
**Date :** 2026-04-30

**Réalisé :**
- Promotion de `dev` vers `main`, marquant la release `v0.1.0` de `azure-terraform-template`
- Repo renommé `azure-terraform-template` sur GitHub et marqué comme Template Repository

---

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ✅  MILESTONE 0 TERMINÉ — azure-terraform-template v0.1.0 publié          ║
║                                                                              ║
║   ▶▶  MILESTONE 1 DÉMARRE — reprise du développement job-finder             ║
║                                                                              ║
║   Repo : vbo-cloud/job-finder (créé depuis azure-terraform-template)        ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

### PR #1 — docs: add architecture documentation (ADRs, ROADMAP, JOURNAL)
**Date :** 2026-05-03

**Réalisé :**
- Ajout de 13 Architecture Decision Records (`docs/adr/ADR-001` à `ADR-013`) couvrant l'ensemble des décisions techniques du projet job-finder
- Ajout de `docs/ROADMAP.md` : planning jour par jour calibré à 10h/jour, de M1 à M5
- Ajout de `docs/adr/SUMMARY.md` : table récapitulative des 13 ADRs
- Déplacement de `DOC.md` (racine) vers `docs/JOURNAL.md` avec nom plus explicite
- Mise à jour de `CLAUDE.md` et du system prompt reviewer pour référencer le nouveau chemin

**Décisions techniques :**
- ADR-001 : PostgreSQL Flexible Server B1ms (vs CosmosDB, MySQL)
- ADR-002 : Container Apps (M1) → AKS (M3) (vs VM, ACI)
- ADR-003 : pgvector dans PostgreSQL (vs Azure AI Search, Qdrant)
- ADR-004 : Alembic + SQLAlchemy (vs Flyway, migrations manuelles)
- ADR-005 : Azure Container Registry Basic (vs Docker Hub, GitHub Container Registry)
- ADR-006 : Azure OpenAI GPT-4o-mini via francecentral — données CVs/utilisateurs en EU (RGPD)
- ADR-007 : Azure Service Bus — découplage total des 4 agents via queues
- ADR-008 : text-embedding-3-small 1536 dims (~0.02$/M tokens)
- ADR-009 : FastAPI + uvicorn — async natif pour appels LLM non bloquants
- ADR-010 : France Travail API (~500K offres, gratuit, légal, structuré)
- ADR-011 : Azure AD B2C — 50K MAU gratuit, données EU, login social
- ADR-012 : Azure Monitor + Application Insights — 5Go/mois gratuit, métriques infra auto
- ADR-013 : Release branch + composants Terraform + staging éphémère (implémentation prévue transition M1→M2)

---

### PR #2 — feat: add Key Vault module
**Date :** 2026-05-03

**Réalisé :**
- Ajout du module Terraform réutilisable `modules/keyvault/` : `main.tf`, `variables.tf`, `outputs.tf`
- La data source `azurerm_client_config` est internalisée dans le module — `tenant_id` n'est pas exposé comme variable d'input
- Module appelé depuis `envs/dev/keyvault.tf` et `envs/prod/keyvault.tf` sans passer `tenant_id`
- Key Vault déployé dans le resource group `rg_core` de chaque environnement

**Décisions techniques :**
- `enable_rbac_authorization = true` — contrôle d'accès via Azure RBAC (pas les access policies legacy)
- `purge_protection_enabled = true` et `soft_delete_retention_days = 7` — conformes aux exigences de sécurité du projet
- `prevent_destroy = true` dans le lifecycle — ressource critique, destruction bloquée par convention
- `azurerm_client_config` dans le module plutôt qu'à l'appelant : le `tenant_id` est un détail d'implémentation interne, pas une préoccupation du caller

---

### PR #3 — feat: add PostgreSQL Flexible Server module with pgvector and private networking
**Date :** 2026-05-04

**Réalisé :**
- Ajout du module Terraform réutilisable `modules/postgresql/` : `main.tf`, `variables.tf`, `outputs.tf`
  - `random_password` pour le mot de passe administrateur (32 chars, stocké dans Key Vault, jamais exposé en output)
  - `azurerm_postgresql_flexible_server` : PostgreSQL 16, SKU B_Standard_B1ms, 32 Go, VNet injection via subnet délégué et DNS privée
  - `azurerm_postgresql_flexible_server_database` : base `jobfinder`, charset UTF8
  - `azurerm_postgresql_flexible_server_configuration` : activation de l'extension `VECTOR` (pgvector)
  - `azurerm_key_vault_secret` : connection string complète stockée dans le Key Vault de l'environnement
- Prérequis réseau créés dans `envs/dev/postgresql-network.tf` et `envs/prod/postgresql-network.tf` :
  - Subnet délégué `snet-jf-postgresql-{env}-frc` dans le VNet de la landing zone (10.0.3.0/24 pour dev, 10.1.3.0/24 pour prod)
  - `azurerm_private_dns_zone` : `privatelink.postgres.database.azure.com`
  - `azurerm_private_dns_zone_virtual_network_link` liant la zone DNS au VNet de la landing zone
- Module appelé depuis `envs/dev/postgresql.tf` et `envs/prod/postgresql.tf`
- Outputs `vnet_name` ajoutés à `lz_dev/outputs.tf` et `lz_prod/outputs.tf` (lz_prod n'avait aucun fichier outputs)
- Provider `random` ajouté aux `required_providers` de `envs/dev/main.tf` et `envs/prod/main.tf`

**Décisions techniques :**
- VNet injection plutôt que private endpoint : recommandé par Azure pour PostgreSQL Flexible Server, intégration réseau native sans règle NSG supplémentaire
- Subnet et DNS zone dans le resource group de la landing zone : ces ressources appartiennent à la couche réseau partagée (hub), pas à la couche applicative
- `random_password` dans le module : le mot de passe n'est jamais passé comme variable d'input — seule la connection string (stockée dans Key Vault) est exposée à l'appelant
- `prevent_destroy = true` sur le serveur et la base : ressources critiques avec état (données), destruction bloquée par convention
- `geo_redundant_backup_enabled = true` uniquement en prod : non disponible sur le tier Burstable B1ms en dev (limitation Azure) ; activé avec `backup_retention_days = 35` en prod pour la durabilité des données

---

### PR #4 — chore: increase reviewer agent context limits and add repo structure
**Date :** 2026-05-04

**Réalisé :**
- Plafond du diff envoyé à Claude : 15 000 → 40 000 caractères
- Plafond des logs de plan par environnement : 6 000 → 10 000 caractères
- Ajout de `git ls-files` dans le contexte utilisateur (section `### Repository structure`) avant le diff — permet au reviewer de connaître la structure complète du repo

**Décisions techniques :**
- `subprocess.check_output(["git", "ls-files"])` exécuté dans le script Python du workflow — pas de step shell supplémentaire, output directement injecté dans le message utilisateur

---

### PR #5 — fix: remove duplicate policy assignments and allow global location
**Date :** 2026-05-04

**Réalisé :**
- Suppression de `envs/dev/policy.tf` et `envs/prod/policy.tf` : la policy `allowed-locations` est assignée au scope subscription depuis `lz_dev` et `lz_prod` — les assignments dans la couche applicative étaient des doublons
- Ajout de `"global"` à `allowed_locations` dans `lz_dev/policy.tf` et `lz_prod/policy.tf`

**Décisions techniques :**
- `Microsoft.Network/privateDnsZones` est enregistré par Azure avec la location `"global"` — sans cet ajout, la policy `mode = "All"` bloquait leur création
- La policy est correctement scopée au niveau subscription depuis les landing zones ; les app layers ne doivent pas redéfinir leurs propres assignments

---

### PR #6 — fix: enforce landing zone apply order before app environments
**Date :** 2026-05-04

**Réalisé :**
- Refactoring de `terraformApply.yml` : remplacement des matrix `[lz_dev, dev]` et `[lz_prod, prod]` par 4 jobs séquentiels distincts
- `apply-lz-dev` → `apply-dev` (avec `needs: apply-lz-dev`) sur push vers `dev`
- `apply-lz-prod` → `apply-prod` (avec `needs: apply-lz-prod`) sur push vers `main`

**Décisions techniques :**
- La matrix déployait lz et app en parallèle — la landing zone pouvait ne pas être prête (VNet, subnets, Key Vault) quand l'app layer démarrait
- Si la landing zone échoue, GitHub Actions annule automatiquement le job dépendant

---

### PR #7 — fix: disable public network access on PostgreSQL Flexible Server
**Date :** 2026-05-04

**Réalisé :**
- Ajout de `public_network_access_enabled = false` dans `azurerm_postgresql_flexible_server` du module `modules/postgresql/`

**Décisions techniques :**
- Azure exige cet attribut explicite quand `delegated_subnet_id` est défini — le serveur est en mode VNet injection et ne doit accepter aucune connexion publique

---

### PR #8 — docs: update JOURNAL.md for PRs #4 to #7
**Date :** 2026-05-04

**Réalisé :**
- Rattrapage des entrées manquantes dans le journal pour les PRs #4 à #7 — ces PRs avaient été mergées sans mise à jour du journal

**Décisions techniques :**
- Le journal doit être mis à jour dans le même commit que les changements de code, avant toute ouverture de PR — règle désormais appliquée systématiquement

---

### PR #9 — feat: add KV Secrets Officer role assignment and fix data source placement
**Date :** 2026-05-04

**Réalisé :**
- Ajout d'un `azurerm_role_assignment` "Key Vault Secrets Officer" pour le service principal Terraform dans `envs/dev/keyvault.tf` et `envs/prod/keyvault.tf`
- Refactoring de `data "azurerm_client_config" "current"` : retiré des modules (`keyvault`, `policy`) et des fichiers de ressource (`keyvault.tf`), centralisé dans les `main.tf` de chaque environnement appelant
- `tenant_id` et `subscription_id` passés comme variables d'input dans les modules `keyvault` et `policy`

**Décisions techniques :**
- `data "azurerm_client_config"` appartient au root module (`main.tf`) — pas aux fichiers de ressource ni aux modules child, qui n'ont pas à connaître l'identité du caller
- Le service principal Terraform a besoin du rôle "Key Vault Secrets Officer" pour écrire les secrets depuis le workflow CI/CD

---

### PR #10 — fix: ignore availability zone drift on PostgreSQL Flexible Server
**Date :** 2026-05-04

**Réalisé :**
- Ajout de `ignore_changes = [zone]` dans le bloc `lifecycle` de `azurerm_postgresql_flexible_server`

**Décisions techniques :**
- Azure assigne automatiquement une availability zone au moment de la création du serveur, mais interdit ensuite tout changement de zone sur un serveur existant
- Sans `ignore_changes = [zone]`, Terraform détecte un drift et tente un update qui échoue systématiquement — cette règle supprime ce faux positif

---

### PR #11 — fix: enable public network access on Key Vault for CI/CD runners
**Date :** 2026-05-05

**Réalisé :**
- `public_network_access_enabled` passé de `false` à `true` dans le module `modules/keyvault/`
- Suppression du bloc `network_acls`
- Commentaire explicatif ajouté dans le code

**Décisions techniques :**
- Les runners GitHub-hosted ont besoin d'accéder au data plane du Key Vault pour écrire les secrets Terraform via la CI/CD
- `enable_rbac_authorization = true` est le contrôle d'accès primaire — la restriction réseau est une couche defense-in-depth, pas la barrière principale
- L'utilisation d'un runner self-hosted dans le VNet permettrait de désactiver l'accès public — voir BACKLOG.md
