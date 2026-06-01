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

### PR #8 — CLOSE
**Date :** 2026-05-04 | **Titre :** docs: update JOURNAL.md for PRs #4 to #7

Fermée sans merge. Réouverte en PR #12 avec un périmètre élargi (#4 à #11).

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

---

### PR #12 — docs: update JOURNAL.md for PRs #4 to #11
**Date :** 2026-05-05

**Réalisé :**
- Rattrapage des entrées manquantes dans le journal pour les PRs #4 à #11 — ces PRs avaient été mergées sans mise à jour du journal
- Ajout de `docs/MANUAL_OPERATIONS.md` : guide des opérations manuelles Azure réalisées hors Terraform (création du service principal OIDC, storage account state, etc.)
- Suppression de `GETTING_STARTED.md` : ce fichier avait été créé dans la phase template (`azure-terraform-template`) pour guider l'onboarding sur un nouveau projet depuis le template — il n'a pas de raison d'être dans `job-finder`, qui est un projet concret et non un template

**Décisions techniques :**
- Le journal doit être mis à jour dans le même commit que les changements de code, avant toute ouverture de PR — règle désormais appliquée systématiquement

---

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   🏷️   RELEASE v0.1.0 — job-finder                                          ║
║   Date : 2026-05-05                                                          ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║   Infrastructure déployée                                                    ║
║   ─────────────────────────────────────────────────────────────────────      ║
║   • Key Vault          SKU configurable, RBAC, purge protection,             ║
║                        soft delete, Key Vault Secrets Officer assigné        ║
║   • PostgreSQL         PostgreSQL 16, pgvector, VNet injection,              ║
║                        DNS privée, connection string dans Key Vault          ║
║   • Policy Azure       Restriction francecentral / northeurope / global      ║
║                        assignée au scope subscription depuis les LZ          ║
║                                                                              ║
║   CI/CD                                                                      ║
║   ─────────────────────────────────────────────────────────────────────      ║
║   • Ordering enforced  apply-lz-dev → apply-dev                              ║
║                        apply-lz-prod → apply-prod (via needs:)               ║
║   • Reviewer agent     Diff 40k chars, logs 10k/env, git ls-files injecté    ║
║                                                                              ║
║   Documentation                                                              ║
║   ─────────────────────────────────────────────────────────────────────      ║
║   • 13 ADRs couvrant l'ensemble des décisions d'architecture                 ║
║   • docs/ROADMAP.md, docs/JOURNAL.md, docs/MANUAL_OPERATIONS.md              ║
║                                                                              ║
║   Correctifs                                                                 ║
║   ─────────────────────────────────────────────────────────────────────      ║
║   • ignore_changes = [zone] sur PostgreSQL (drift availability zone)         ║
║   • public_network_access_enabled = true sur Key Vault (runners GitHub)      ║
║   • Suppression des doublons de policy dans dev/ et prod/                    ║
║   • data "azurerm_client_config" centralisé dans les main.tf root            ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

### Changement de process — Mirror prod différé

**Date :** 2026-05-05

Décision : pendant le Milestone 1, les changements sont implémentés uniquement dans `envs/dev/`. Le mirror vers `envs/prod/` est différé à la fin du M1, lors du passage en v1.0.0.

**Raison :** déployer prod en parallèle de dev n'apporte aucune valeur tant qu'il n'y a pas d'application fonctionnelle et testable. Cela ajoute de la complexité à chaque PR et multiplie les erreurs de bootstrap. Un seul apply prod massif sera effectué quand dev sera stable, avec les ajustements prod appropriés (SKUs, rétention, geo-redundancy).

---

### PR #13 — feat: add vnet and subnet modules with prevent_destroy and migrate existing resources
**Date :** 2026-05-05

**Réalisé :**
- Ajout du module Terraform réutilisable `modules/vnet/` (`main.tf`, `variables.tf`, `outputs.tf`) : `azurerm_virtual_network` avec `prevent_destroy = true` et variables `name`, `location`, `resource_group_name`, `address_space`, `environment`, `project`, `owner`
- Ajout du module Terraform réutilisable `modules/subnet/` (`main.tf`, `variables.tf`, `outputs.tf`) : `azurerm_subnet` avec `prevent_destroy = true`, bloc `dynamic "delegation"` conditionnel (`delegation_name != null`), validation empêchant `delegation_name` sans `delegation_service` ; variables `environment`/`project`/`owner` absentes (`azurerm_subnet` ne supporte pas les tags)
- Migration de `lz_dev/network.tf` et `lz_prod/network.tf` : remplacement des ressources inline `azurerm_virtual_network` et `azurerm_subnet` par des appels aux modules `vnet` et `subnet`
- Création de `lz_dev/keyvault.tf` et `lz_prod/keyvault.tf` : appels au module `keyvault` avec les valeurs appropriées (`soft_delete_retention_days = 90` en lz_prod) ; suppression des ressources `azurerm_key_vault` inline des `main.tf`
- Migration de `dev/network.tf` et `prod/network.tf` : remplacement du `azurerm_subnet.postgresql` inline par un appel au module `subnet` avec délégation PostgreSQL
- Mise à jour des `outputs.tf` de `lz_dev` et `lz_prod` pour référencer les outputs des modules
- Mise à jour de `dev/postgresql.tf` et `prod/postgresql.tf` : `azurerm_subnet.postgresql.id` → `module.subnet_postgresql.id`
- Ajout de `moved {}` blocks dans `lz_dev/moved.tf`, `lz_prod/moved.tf`, `dev/moved.tf` et `prod/moved.tf` (exception M1) pour migrer les adresses de state sans destroy

**Décisions techniques :**
- Les modules `vnet` et `subnet` sont séparés (un module = une ressource) pour permettre de les composer librement — une VNet peut avoir N subnets sans que le module vnet ait à les connaître
- Le bloc `dynamic "delegation"` est conditionnel sur `var.delegation_name != null` : les subnets sans délégation n'ont pas à passer ces variables ; une validation Terraform bloque le cas `delegation_name` fourni sans `delegation_service`
- `prevent_destroy = true` dans les modules garantit qu'aucun destroy accidentel ne peut supprimer VNets, subnets ou Key Vaults — même si l'appelant oublie de le mettre
- `moved {}` blocks : migration sans destroy des ressources inline existantes vers les nouveaux chemins de module — ces blocs peuvent être supprimés après le premier apply réussi (voir BACKLOG.md)
- `prod/moved.tf` ajouté exceptionnellement pour éviter un destroy au plan malgré la règle M1 de ne pas toucher prod — le fichier sera supprimé lors du mirror prod en fin de M1
- `soft_delete_retention_days = 90` en lz_prod (vs 7 par défaut en lz_dev) : rétention maximale sur l'environnement de production

---

### PR #14 — feat: add vnet and subnet modules with prevent_destroy and migrate existing resources
**Date :** 2026-05-05

**Réalisé :**
- Ajout du module Terraform réutilisable `modules/vnet/` : `azurerm_virtual_network` avec `prevent_destroy = true`
- Ajout du module Terraform réutilisable `modules/subnet/` : `azurerm_subnet` avec `prevent_destroy = true`, bloc `dynamic "delegation"` conditionnel (`delegation_name != null`)
- Migration de `lz_dev/network.tf` et `lz_prod/network.tf` : ressources inline remplacées par des appels aux modules `vnet` et `subnet`
- Déplacement des Key Vault inline de `lz_dev/main.tf` et `lz_prod/main.tf` vers des fichiers `keyvault.tf` dédiés appelant `modules/keyvault/` (`soft_delete_retention_days = 90` en lz_prod)
- Migration de `dev/network.tf` : subnet postgresql migré vers `module.subnet_postgresql` avec inputs de délégation
- Ajout de `moved {}` blocks dans `lz_dev/moved.tf`, `lz_prod/moved.tf`, `dev/moved.tf` pour migrer les adresses de state sans destroy
- Mise à jour des `outputs.tf` de `lz_dev` et `lz_prod` pour référencer les outputs des modules
- Changements `prod/` différés à la fin du M1

**Décisions techniques :**
- Un module par ressource (`vnet` et `subnet` séparés) — permet de composer N subnets par VNet sans couplage
- `prevent_destroy = true` dans le module (pas chez l'appelant) — les ressources critiques sont protégées quelle que soit la façon d'appeler le module
- `dynamic "delegation"` avec `for_each = var.delegation_name != null ? [1] : []` — garde le module propre pour les subnets sans délégation
- `moved {}` blocks : mécanisme Terraform correct pour refactorer des ressources inline en modules sans destroy/recreate ; supprimables après le premier apply réussi
- Les Key Vaults de `lz_dev` et `lz_prod` n'existaient pas encore dans Azure — aucun import requis, la CI/CD les crée à l'apply
- `soft_delete_retention_days = 90` en lz_prod (vs défaut 7 en lz_dev) : rétention maximale sur la landing zone de production

---

### PR #15 — feat: add blob storage module with private endpoint
**Date :** 2026-05-05

**Réalisé :**
- Ajout du module Terraform réutilisable `modules/private_endpoint/` (`main.tf`, `variables.tf`, `outputs.tf`) : `azurerm_private_endpoint` générique avec variables `name`, `location`, `resource_group_name`, `subnet_id`, `private_connection_resource_id`, `subresource_name`, `private_dns_zone_ids` (list(string)) ; outputs `id` et `private_ip_address`
- Ajout du module Terraform réutilisable `modules/storage/` (`main.tf`, `variables.tf`, `outputs.tf`) : `azurerm_storage_account` uniquement — Standard_LRS, TLS 1.2, accès public désactivé, nested public items interdits, `prevent_destroy = true`, soft delete blob et container à 7 jours ; outputs `id`, `name`, `primary_blob_endpoint`
- Refactoring de `dev/network.tf` : fichier réduit aux data sources VNet/subnet app et au `module.subnet_postgresql` ; les DNS zones déplacées dans les fichiers service
- Déplacement de `azurerm_private_dns_zone.postgresql` et son VNet link vers `dev/postgresql.tf` (co-localisation avec le module postgresql)
- Création de `envs/dev/storage.tf` : DNS zone `privatelink.blob.core.windows.net` + VNet link dans `rg_core`, appel `module.storage` (storage account dans `rg_data`), `azurerm_storage_container` x2 (`cvs`, `offers`), `azurerm_management_lock` CanNotDelete, appel `module.private_endpoint_blob` — containers, lock et private endpoint sont définis à l'env level, pas dans le module

**Décisions techniques :**
- `modules/private_endpoint/` est générique et réutilisable pour tout service exposé via private endpoint — `subresource_name` et `private_dns_zone_ids` (list) permettent de l'appeler pour blob, file, table, etc.
- `modules/storage/` ne gère que le storage account : containers, private endpoint et management lock sont des décisions de l'appelant — un module = une ressource
- `azurerm_management_lock` au niveau env (pas dans le module) : le lock est une décision opérationnelle spécifique à l'environnement ; le module ne doit pas imposer une politique de lock à l'appelant
- DNS zone et VNet link dans le fichier service (`storage.tf` pour blob, `postgresql.tf` pour PostgreSQL) : pattern "un fichier par service", plus lisible qu'un `network.tf` fourre-tout
- Storage account dans `rg_data` (ressource stateful), DNS zone et VNet link dans `rg_core` (infrastructure partagée)
- `public_network_access_enabled = false` : le storage est exclusivement accessible via le private endpoint
- Soft delete (7 jours blob + container) : protection contre les suppressions accidentelles de données, récupérable depuis le portail Azure
- Nommage storage account : `st${project}dev${location_short}` = `stjfdevfrc` (pas de tirets, max 24 chars)

---

### PR #16 — feat: separate IAM into a dedicated Terraform project
**Date :** 2026-05-05

**Réalisé :**
- Scaffold de `JobFinder/Terraform/iam/dev/` et `iam/prod/` : deux projets Terraform indépendants dédiés à la gestion des role assignments, chacun avec son propre state (`iam-dev.tfstate`, `iam-prod.tfstate`)
- `iam/dev/main.tf` : data source sur `kv-jf-dev-frc`, `azurerm_role_assignment` "Key Vault Secrets Officer" pour le service principal
- `iam/prod/main.tf` : idem pour `kv-jf-prod-frc` (déployé lors du mirror prod)
- Suppression du `azurerm_role_assignment` de `envs/dev/keyvault.tf` — la responsabilité RBAC quitte la couche applicative
- Documentation ajoutée dans `docs/MANUAL_OPERATIONS.md` : procédure d'apply IAM manuel et révocation du rôle temporaire `User Access Administrator`

**Décisions techniques :**
- Les role assignments sont appliqués manuellement avec le compte utilisateur (pas via `sp-jf-github`) : le service principal ne peut pas s'auto-assigner des droits sans `User Access Administrator`, et ce rôle temporaire sera révoqué après l'apply IAM
- `iam/` est un projet Terraform racine distinct (pas un module, pas sous `envs/`) : le périmètre IAM est orthogonal aux environnements applicatifs et mérite son propre cycle de vie et son propre state

---

### PR #17 — fix: remove shared_access_key_enabled=false — blocked by azurerm 3.x provider limitation
**Date :** 2026-05-06

**Réalisé :**
- Suppression de `shared_access_key_enabled = false` dans `modules/storage/main.tf`
- Ajout d'une entrée BACKLOG pour réactiver ce paramètre lors de la migration vers azurerm ~> 4.0

**Décisions techniques :**
- Le provider azurerm 3.x utilise les access keys en interne lors de la création du storage account — positionner `shared_access_key_enabled = false` provoque une erreur à l'apply
- Le paramètre est fonctionnellement souhaitable (désactiver les clés partagées renforce la sécurité) mais nécessite azurerm ~> 4.0 qui a revu cette dépendance interne
- Tracé en BACKLOG pour ne pas perdre l'intention sécurité ; à traiter en même temps que la migration provider

---

### PR #18 — feat: auto-lock policy on protect=true resources and storage RBAC
**Date :** 2026-05-06

**Réalisé :**
- Ajout de `azurerm_role_assignment` "Storage Blob Data Contributor" dans `iam/dev/main.tf` scopé sur `rg-jf-dev-frc-data` — le service principal `sp-jf-github` peut lire et écrire les blobs
- Suppression de l'`azurerm_management_lock` manuel dans `envs/dev/storage.tf` — remplacé par la policy auto-lock
- Création de `envs/lz_dev/lock-policy.tf` :
  - `azurerm_policy_definition` : effect `deployIfNotExists`, cible toute ressource taguée `protect=true`, déploie un lock `CanNotDelete` via un ARM template inline si aucun lock n'existe déjà
  - `azurerm_subscription_policy_assignment` : identity `SystemAssigned` — Azure attribue automatiquement le rôle `Owner` à cette identité managée pour pouvoir déployer le lock
  - `prevent_destroy = true` sur les deux ressources
- Ajout du tag `protect = "true"` dans les modules `storage`, `postgresql` et `keyvault` — toutes les ressources critiques déclenchent automatiquement la policy

**Décisions techniques :**
- `azurerm_management_lock` en Terraform nécessite que le service principal dispose du rôle `User Access Administrator` pour être posé — contrainte difficile à justifier durablement. La policy `deployIfNotExists` avec Managed Identity délègue ce droit uniquement à l'identité de la policy, pas au SP Terraform
- L'approche policy est plus robuste qu'un lock Terraform : elle s'applique à toute ressource taguée `protect=true`, même créée hors Terraform ou manuellement
- Le tag `protect=true` est posé dans les modules (pas chez l'appelant) : toute instance de ces modules critiques bénéficie automatiquement du lock sans que l'appelant ait à s'en souvenir
- `roleDefinitionId` `8e3af657-a8ff-443c-a75c-2fe8c4bcb635` = Owner built-in role — requis pour que la Managed Identity de la policy puisse poser un lock au niveau ressource

---

### Décision technique — Owner temporaire sur sp-jf-github pour Milestone 1

**Date :** 2026-05-06

**Contexte :**
Le développement du M1 a mis en évidence une limite structurelle : `sp-jf-github` est le SP unique qui gère à la fois les landing zones et les couches applicatives. En entreprise suivant Azure CAF, ces responsabilités sont portées par deux SPs distincts — un SP platform avec des droits élevés pour la gouvernance (lz), un SP applicatif limité pour les ressources métier (dev/prod). Faute de cette séparation, chaque opération de gouvernance (policy assignment, management lock, role assignment) échoue avec une 403.

**Décision :**
Pour débloquer le développement du Milestone 1, `sp-jf-github` reçoit temporairement le rôle **Owner** au niveau subscription. Cette décision est délibérée, documentée, et bornée dans le temps.

**Justification :**
- La valeur de M1 est dans les modules applicatifs (Service Bus, Azure OpenAI, Container Apps), pas dans la résolution de la dette IAM
- Le workaround `iam/` (apply manuel avec compte Owner) crée plus de friction que le rôle Owner temporaire sur le SP
- La migration vers un SP platform dédié est planifiée et documentée en BACKLOG

**Ce qui sera fait à la transition M1→M2 :**
- Création de `sp-jf-platform` avec Owner, OIDC configuré pour GitHub Actions
- Migration des jobs lz_dev/lz_prod vers `sp-jf-platform` dans les workflows CI/CD
- Déplacement des policy assignments et role assignments de `iam/` vers `lz_dev/` (géré par `sp-jf-platform`)
- Révocation du rôle Owner sur `sp-jf-github` — retour au Contributor + rôles data-plane

**Voir BACKLOG.md** — section "Architecture IAM / Gouvernance" pour le processus détaillé.

---

### Opération — Migration IAM vers lz_dev
**Date :** 2026-05-06

- sp-jf-github reçoit les rôles Contributor + User Access Administrator +
  Storage Blob Data Contributor au niveau subscription
- Rôle Owner révoqué sur sp-jf-github
- Contenu de `iam/dev/` migré dans `lz_dev/` :
  - `lz_dev/rbac.tf` : role assignments Key Vault Secrets Officer (x2) et
    Storage Blob Data Contributor gérés directement par CI/CD
  - `lz_dev/lock-policy.tf` : policy assignment déplacé depuis iam/dev/
- `iam/dev/` supprimé — le projet iam/ est désormais réservé au bootstrap
  one-shot de sp-jf-platform lors de la transition M1→M2
- Décision : User Access Administrator permet à sp-jf-github de gérer les
  role assignments sans Owner ; la permission `elevateAccess` (auto-élévation
  Owner) n't est plus présente

---

### PR #19 — fix: enable public network access on storage account for CI/CD runners
**Date :** 2026-05-07

**Réalisé :**
- `public_network_access_enabled` passé de `false` à `true` dans `modules/storage/main.tf`
- Commentaire explicatif ajouté dans le code

**Décisions techniques :**
- Les runners GitHub-hosted ont besoin d'accéder au data plane blob du storage account pour créer les containers (`azurerm_storage_container` appelle l'API blob, pas l'API ARM management) — sans accès public, l'apply échoue avec une 403 sur l'endpoint blob
- Même pattern que le Key Vault : RBAC (`Storage Blob Data Contributor`) est le contrôle d'accès primaire, l'accès réseau public est une concession opérationnelle temporaire
- Tracé en BACKLOG pour désactivation quand un runner self-hosted dans le VNet sera disponible

---

### PR #20 — feat: add Service Bus module with 3 queues for agent pipeline
**Date :** 2026-05-07

**Réalisé :**
- Ajout du module Terraform réutilisable `modules/servicebus/` : `azurerm_servicebus_namespace` (SKU Standard, `prevent_destroy = true`, tag `protect=true`) + `azurerm_servicebus_queue` en `for_each` (TTL 7j, dead-letter après 10 tentatives)
- Appel du module depuis `envs/dev/servicebus.tf` avec 3 queues pour le pipeline d'agents : `offer-ready`, `cv-ready`, `match-ready`
- Connection string stockée dans le Key Vault (`servicebus-connection-string`) via `azurerm_key_vault_secret`
- Règle ajoutée dans `CLAUDE.md` : toujours référencer les ressources via les outputs de module

**Décisions techniques :**
- SKU Standard : le Basic ne supporte pas les topics ; Standard suffit pour le volume M1
- `for_each = toset(var.queues)` : ajout/suppression de queues sans recréer le namespace
- `default_message_ttl = "P7D"` + `enable_dead_lettering_on_message_expiration = true` : les messages non consommés ne sont pas silencieusement perdus — ils partent en dead-letter queue pour investigation
- Agent 4 (daily cleanup) est timer-triggered et ne passe pas par une queue

---

### PR #21 — refactor: introduce var.env and replace hardcoded environment strings
**Date :** 2026-05-07

**Réalisé :**
- Ajout de `variable "env"` dans les `variables.tf` des 4 environnements, avec une valeur par défaut correspondant à l'environnement (`"dev"`, `"lz-dev"`, `"lz-prod"`, `"prod"`)
- Remplacement de tous les strings d'environnement hardcodés (`environment = "dev"`, etc.) par `var.env` dans tous les fichiers `.tf` des 4 environnements :
  - `envs/dev/` : `keyvault.tf`, `postgresql.tf`, `resourcegroups.tf`, `storage.tf`
  - `envs/lz_dev/` : `main.tf`, `keyvault.tf`, `network.tf`, `policies.tf`
  - `envs/lz_prod/` : `main.tf`, `keyvault.tf`, `network.tf`, `policies.tf`
  - `envs/prod/` : `keyvault.tf`, `network.tf`, `postgresql.tf`, `resourcegroups.tf`

**Décisions techniques :**
- Le `default` de `var.env` est codé en dur dans chaque `variables.tf` (ex. `default = "dev"`), ce qui évite d'injecter une variable supplémentaire via CI/CD — les `terraform.tfvars` sont gitignorés et non committés
- Le tag `environment` reflètera maintenant toujours la valeur réelle de l'environnement, sans risque de dérive si une ressource est copiée d'un env à l'autre

---

### PR #22 — refactor: enforce module consistency for resource groups and KV secrets
**Date :** 2026-05-07

**Réalisé :**
- Ajout du module `modules/keyvault_secret/` : wrapper réutilisable autour de `azurerm_key_vault_secret` avec tags standardisés
- Remplacement de la ressource `azurerm_key_vault_secret` inline dans `envs/dev/servicebus.tf` par un appel au module (`module "secret_servicebus"`)
- Extension du module `modules/resource_group/` : ajout des variables `environment`, `project`, `owner` (tags) et output `location`
- Remplacement des 3 ressources `azurerm_resource_group` inline dans `envs/dev/` par des appels au module (`rg_core`, `rg_app`, `rg_data`)
- Remplacement de la ressource `azurerm_resource_group` inline dans `envs/lz_dev/` par un appel au module (`rg`)
- Mise à jour de toutes les références dans `envs/dev/` et `envs/lz_dev/` (`keyvault.tf`, `network.tf`, `outputs.tf`, `postgresql.tf`, `servicebus.tf`, `storage.tf`)
- Blocs `moved {}` ajoutés dans `envs/dev/moved.tf` (3 blocs) et `envs/lz_dev/moved.tf` (1 bloc) pour la migration d'état sans destroy

**Décisions techniques :**
- `prod` et `lz_prod` laissés intentionnellement intacts — la migration prod se fera en bloc à la fin de M1
- Le bloc `moved {}` est la seule façon de renommer une adresse d'état sans détruire la ressource Azure sous-jacente
- `modules/resource_group/` étendu plutôt que de créer un nouveau module — backward-compatible car les nouvelles variables n'ont pas de `default` mais les seuls appelants sont mis à jour dans ce même PR

---

### PR #23 — feat: add Azure OpenAI module and deploy gpt-4o-mini + text-embedding-3-small
**Date :** 2026-05-07

**Réalisé :**
- Ajout du module Terraform réutilisable `modules/openai/` : `azurerm_cognitive_account` (kind OpenAI, `prevent_destroy = true`, tag `protect=true`) + `azurerm_cognitive_deployment` en `for_each` sur une map d'objets
- Déploiement depuis `envs/dev/openai.tf` avec 2 modèles : `gpt-4o-mini` (Agent 3 — matching) et `text-embedding-3-small` (Agent 2 — embeddings), 10K TPM chacun
- Clé API et endpoint stockés dans le Key Vault via `modules/keyvault_secret/` (`openai-api-key`, `openai-endpoint`)

**Décisions techniques :**
- `public_network_access_enabled = true` : les agents tournent hors VNet en M1 ; commentaire de rappel pour restriction via private endpoint dès que les runners self-hosted seront disponibles
- Région `francecentral` : conformité GDPR — les données CV/utilisateur restent en EU (ADR-006)
- `capacity_tpm = 10` (10K TPM) : suffisant pour le volume dev ; à ajuster selon la charge réelle
- `for_each` sur une map d'objets : ajout/suppression de déploiements sans recréer le compte OpenAI

**Correctif post-merge (2026-05-07) :**
- L'apply a échoué avec une 400 — SKU `Standard` non disponible pour gpt-4o-mini et text-embedding-3-small en `francecentral` ; seul `GlobalStandard` est supporté
- `scale_type` extrait en variable dans le module (`modules/openai/`) et passé à `"GlobalStandard"` dans `envs/dev/openai.tf`
- Note ajoutée dans ADR-006 (résidence des données : le compute peut transiter hors francecentral mais la facturation et les données restent en EU)

---

### PR #24 — feat: add Container Registry module and deploy ACR in dev
**Date :** 2026-05-07

**Réalisé :**
- Ajout du module Terraform réutilisable `modules/container_registry/` : `azurerm_container_registry` (admin désactivé, `prevent_destroy = true`, tag `protect=true`)
- Déploiement depuis `envs/dev/container_registry.tf` : ACR Basic pour stocker les images des 4 agents (`agent-offer-fetching`, `agent-embedding`, `agent-matching`, `agent-cleanup`)
- Login server stocké dans le Key Vault via `modules/keyvault_secret/` (`acr-login-server`)

**Décisions techniques :**
- `admin_enabled = false` : les agents s'authentifient via Managed Identity avec le rôle AcrPull (M2) — pas de credentials statiques
- SKU Basic : suffisant pour le volume dev ; Standard/Premium pour prod (geo-replication, Private Link)
- Login server en KV : les Container Apps récupèrent l'URL du registry sans hardcoder de valeur

---

### PR #25 — feat: add Application Insights and Log Analytics module for agent telemetry
**Date :** 2026-05-07

**Réalisé :**
- Ajout du module Terraform réutilisable `modules/application_insights/` : `azurerm_log_analytics_workspace` (SKU PerGB2018, rétention configurable, quota journalier 1 GB) + `azurerm_application_insights` (type `other`, `prevent_destroy = true`) liés par `workspace_id`
- Déploiement depuis `envs/dev/monitoring.tf` : une seule instance partagée par les 4 agents, rétention 30 jours
- Connection string stockée dans le Key Vault via `modules/keyvault_secret/` (`appinsights-connection-string`)

**Décisions techniques :**
- Une seule ressource Application Insights pour tous les agents : chaque agent se différencie via `cloud_role_name` dans son code — évite la multiplication de ressources et centralise les dashboards
- `application_type = "other"` : les agents sont des workers Python, pas des apps web
- Log Analytics Workspace en mode PerGB2018 : facturation à la donnée ingérée, pas de commitment tier nécessaire en dev
- `daily_quota_gb = 1` : plafond d'ingestion pour éviter les coûts incontrôlés en cas de boucle d'agent

---

### PR #26 — feat: add Container App Jobs module and deploy 5 agent jobs
**Date :** 2026-05-08

**Réalisé :**
- Ajout du module Terraform réutilisable `modules/container_app_job/` : `azurerm_container_app_job` avec support des triggers `timer` (cron) et `queue` (Service Bus via KEDA) via blocs `dynamic`
- Ajout de l'output `workspace_id` sur `modules/application_insights/`
- Déploiement dans `envs/dev/container_apps.tf` :
  - `azurerm_container_app_environment` partagé par tous les agents, lié au Log Analytics Workspace
  - 5 Container App Jobs avec images placeholder (`containerapps-helloworld`) — images réelles construites et poussées en M2 :
    - `job-offer-fetching` — timer, 12:00 et 20:00 UTC (écrit dans `offer-ready`)
    - `job-embedding-offer` — queue `offer-ready`
    - `job-embedding-cv` — queue `cv-ready`
    - `job-matching` — queue `match-ready`
    - `job-cleanup` — timer, 02:00 UTC
- Bloc `validation` ajouté sur `trigger_type` dans le module : valeurs acceptées `"timer"` et `"queue"` uniquement
- Variable `env_vars` étendue pour supporter les deux types : `value` (plain-text) et `secret_name` (secret-backed) en `optional(string)`
- Secret Service Bus câblé dans les 4 jobs qui interagissent avec les queues :
  - `job-embedding-offer`, `job-embedding-cv`, `job-matching` : secret injecté via le bloc KEDA `authentication`
  - `job-offer-fetching` : secret injecté comme variable d'environnement `AZURE_SERVICEBUS_CONNECTION_STRING` (le job écrit dans la queue, pas de bloc KEDA)
- `local.servicebus_connection_string` utilise `module.servicebus.primary_connection_string` directement — la syntaxe `@Microsoft.KeyVault(SecretUri=...)` est propre à App Service, non supportée par Container Apps en M1

**Décisions techniques :**
- Un job par agent : scaling, trigger et lifecycle indépendants dans le même environment
- Trigger queue via KEDA (`azure-servicebus`) : scale-to-zero natif, pas de polling permanent
- Images placeholder en M1 : l'infrastructure est provisionnée et validée avant que les images agents n'existent — découplage infrastructure / code applicatif
- `job-offer-fetching` reçoit le secret via `env_vars` (pas via KEDA) : il n'a pas de bloc `authentication` car il n'est pas déclenché par une queue, il l'alimente
- M2 : basculer `local.servicebus_connection_string` sur `key_vault_secret_id` avec Managed Identity dès que les identités managées des agents seront configurées

---

### PR #27 — chore: post-M1 cleanup — remove prod envs, moved.tf blocks, update CI/CD matrix
**Date :** 2026-05-08

**Réalisé :**
- Correction du `resource_group_name` du backend state : `rg-tfstate` → `rg-jf-tfstate-frc` dans les 4 `backend.tf` (dev, lz_dev, lz_prod, prod)
- Suppression de `envs/lz_prod/` et `envs/prod/` : environnements nettoyés dans Azure, recréés from scratch à la release/1.0.0
- Suppression de `envs/iam/dev/` et `envs/iam/prod/` : projet IAM devenu obsolète après la migration des role assignments vers `lz_dev/rbac.tf`
- Retrait de `lz_prod` et `prod` de la matrice `terraformPlan.yml` : seuls `lz_dev` et `dev` actifs jusqu'à la release
- Suppression des jobs `apply-lz-prod` et `apply-prod` de `terraformApply.yml` et retrait de `main` du trigger — le workflow ne se déclenche plus que sur `dev`
- Suppression de `envs/lz_dev/moved.tf` et `envs/dev/moved.tf` : blocs `moved {}` temporaires devenus inutiles après apply réussi
- Mise à jour de `CLAUDE.md` (ajout de la règle `validation` sur les variables de module) et `docs/BACKLOG.md`

**Décisions techniques :**
- Les environnements prod sont supprimés du dépôt plutôt que maintenus vides : évite les faux positifs dans les plans CI et clarifie le périmètre actif du projet
- Un seul apply prod massif sera effectué à la release/1.0.0 avec les ajustements prod appropriés (SKUs, rétention, geo-redundancy)

---

### PR #28 — chore: upgrade azurerm provider to ~> 4.0
**Date :** 2026-05-08

**Réalisé :**
- Bump du provider azurerm `~> 3.0` → `~> 4.0` dans `envs/dev/main.tf` et `envs/lz_dev/main.tf`
- Suppression du bloc `required_providers` dans `modules/postgresql/main.tf` — les versions de providers se déclarent uniquement au root module
- Mise à jour des `.terraform.lock.hcl` de `dev` et `lz_dev` : azurerm v4.72.0
- Breaking changes azurerm 4.0 corrigés :
  - `modules/openai/` : bloc `scale {}` renommé en `sku {}`, attribut `type` renommé en `name` ; variable `scale_type` renommée en `sku_name` dans le module et son appelant (`envs/dev/openai.tf`)
  - `envs/dev/storage.tf` : `storage_account_name` remplacé par `storage_account_id` sur les deux `azurerm_storage_container`
  - `modules/keyvault/` : `enable_rbac_authorization` renommé en `rbac_authorization_enabled` (déprécié en 4.x, supprimé en 5.0)
- `terraform validate` passe sur `lz_dev` et `dev` — aucune erreur bloquante

**Décisions techniques :**
- Migration ciblée 3.x → 4.x uniquement : les breaking changes 4.x sont limités et tous corrigés dans cette PR
- `required_providers` dans les modules child est une mauvaise pratique en Terraform : le root module est le seul responsable de la sélection des versions — supprimé de `modules/postgresql/` qui était le dernier module à en avoir un

---

### PR #29 — feat: introduce sp-jf-platform for landing zone governance
**Date :** 2026-05-09

**Réalisé :**
- Introduction de `sp-jf-platform` comme SP dédié à la CI/CD des landing zones (lz_dev, lz_prod), séparé de `sp-jf-github` qui reste limité à la couche app
- `terraformPlan.yml` remplacé par deux workflows scopés avec path filters : `terraformPlan-platform.yml` (lz_dev, lz_prod, modules) et `terraformPlan-app.yml` (dev, prod)
- `terraformApply.yml` : job `apply-lz-dev` migré vers `AZURE_PLATFORM_CLIENT_ID`
- `envs/lz_dev/backend.tf` : container migré vers `lz-tfstates` (dédié à sp-jf-platform) + `use_azuread_auth = true`
- `envs/lz_dev/rbac.tf` : ajout de `Contributor` subscription et `Storage Blob Data Contributor` sur `app-tfstates` pour sp-jf-github — géré ici par sp-jf-platform (RBAC Administrator conditionné)
- `powershell/setup-sp-jf-platform.ps1` : script de bootstrap idempotent pour créer sp-jf-platform (App Registration, SP, federated credentials OIDC, role assignments)
- `CLAUDE.md` : règle "un PR ne mélange jamais platform et app" formalisée dans les branch rules
- `docs/MANUAL_OPERATIONS.md` : documentation de la création manuelle de sp-jf-platform

**Décisions techniques :**
- Deux SPs distincts pour le principe de moindre privilège : sp-jf-platform a `RBAC Administrator` (conditionné aux rôles non-privilégiés) + `Resource Policy Contributor` ; sp-jf-github a `Contributor` + `Storage Blob Data Contributor` sur son container
- La séparation des workflows par path filter élimine la dépendance circulaire : un PR app ne déclenche plus le plan lz_dev, et inversement
- `use_azuread_auth = true` requis car sp-jf-platform n'a que `Storage Blob Data Contributor` sur `lz-tfstates` — `listKeys` nécessiterait `Storage Account Contributor` ou `Owner`
- Les role assignments de sp-jf-github sont gérés depuis lz_dev/rbac.tf (et non depuis iam/) car sp-jf-platform a RBAC Administrator, ce qui rend la CI/CD autonome sans intervention manuelle
### PR #30 — feat: configure sp-jf-github backend and OIDC setup
**Date :** 2026-05-09

**Réalisé :**
- `envs/dev/backend.tf` : container migré vers `app-tfstates` (dédié à sp-jf-github) + `use_azuread_auth = true` — authentification via OIDC/AAD directement sur le blob, sans passer par `listKeys`
- `powershell/setup-sp-jf-github.ps1` : script de bootstrap rendu idempotent (vérification existence avant création) ; la section role assignments est retirée — les rôles de sp-jf-github sont désormais gérés par sp-jf-platform via `lz_dev/rbac.tf`

**Décisions techniques :**
- `use_azuread_auth = true` est requis car sp-jf-github n'a que `Storage Blob Data Contributor` sur son container — `listKeys` nécessite `Storage Account Contributor` ou `Owner`, ce qui violerait le principe de moindre privilège
- La délégation des role assignments à `lz_dev/rbac.tf` élimine le couplage entre le script de bootstrap et les permissions réelles : sp-jf-platform est la seule identité autorisée à assigner des rôles

---

### PR #31
```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   🔀  MERGE dev → main — 2026-05-09                                         ║
║   🏷️  v0.1.1                                                                 ║
║   Full dev infrastructure + two-SP CI/CD governance  (PRs #14 à #30)       ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║   Infrastructure déployée                                                    ║
║   ─────────────────────────────────────────────────────────────────────      ║
║   • Service Bus        Namespace Standard, 3 queues agents (offer /         ║
║                        cv / match), dead-letter, TTL 7j                     ║
║   • Azure OpenAI       GPT-4o-mini + text-embedding-3-small,                ║
║                        GlobalStandard, francecentral                        ║
║   • Container Registry ACR Basic, admin désactivé                           ║
║   • App Insights       Log Analytics Workspace + Application Insights,      ║
║                        quota 1 Go/jour, rétention 30j                       ║
║   • Container App Jobs 5 agents (offer-fetching, embedding x2,             ║
║                        matching, cleanup) — images placeholder M1           ║
║                                                                              ║
║   Réseau & stockage                                                          ║
║   ─────────────────────────────────────────────────────────────────────      ║
║   • Storage account    Blob private endpoint, containers cvs / offers,      ║
║                        soft delete 7j, accès public runners CI/CD           ║
║   • Modules vnet/subnet  prevent_destroy, delegation PostgreSQL             ║
║                                                                              ║
║   CI/CD & gouvernance                                                        ║
║   ─────────────────────────────────────────────────────────────────────      ║
║   • Dual SP            sp-jf-platform (lz) / sp-jf-github (app),           ║
║                        OIDC, moindre privilège                              ║
║   • Apply trigger      push vers dev → apply lz_dev + dev                  ║
║   • Provider           azurerm ~> 4.0, breaking changes corrigés           ║
║   • Auto-lock policy   deployIfNotExists sur protect=true → lock            ║
║                        CanNotDelete via Managed Identity                    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

### PR #32 — fix(lz_dev): grant Reader on tfstate storage account to sp-jf-github
**Date :** 2026-05-09

**Réalisé :**
- Ajout d'une entrée `tfstate_reader` dans `sp_role_assignments` de `lz_dev/rbac.tf` : rôle `Reader` sur le storage account `stjftfstatefrc` pour `sp-jf-github`

**Décisions techniques :**
- `Reader` au scope du storage account permet à sp-jf-github d'énumérer le compte via l'API ARM sans `listKeys` — nécessaire pour `terraform init` avec `use_azuread_auth = true`
- Scope volontairement limité au storage account (pas au resource group) pour respecter le principe de moindre privilège

---

### PR #33 — fix(lz_dev): grant Reader on lz_dev resource group to sp-jf-github
**Date :** 2026-05-09

**Réalisé :**
- Ajout d'une entrée `lz_rg_reader` dans `sp_role_assignments` de `lz_dev/rbac.tf` : rôle `Reader` sur le resource group principal de lz_dev (`module.rg.id`) pour `sp-jf-github`

**Décisions techniques :**
- `Reader` sur le RG de lz_dev permet à sp-jf-github de résoudre les data sources qui lisent des ressources de la landing zone via l'API ARM sans avoir de droits de modification sur ce RG

---

### Sync dev → main (2026-05-10)

Merge de `dev` vers `main` incluant les PRs #29 à #33. Déclenche l'apply lz_dev + dev en CI.

---

### chore: update docs and memory post-M1
**Date :** 2026-05-10 — commits directs sur `dev` (pas de GitHub PR)

**Réalisé :**
- `docs/MANUAL_OPERATIONS.md` : refonte complète — procédures manuelles remplacées par les scripts PowerShell, documentation des deux SPs, ajout checklist reconstruction prod
- `memory/project-job-finder.md` : mise à jour complète — stack, infrastructure déployée, statut M1 terminé / M2 en cours
- `memory/next-steps.md` : réécriture pour M2 — plan agents Python, ordre des tâches, décisions techniques à prendre
- `CLAUDE.md` : correction "Claude API agents" → "Azure OpenAI agents via Container App Jobs + Service Bus"

**Décisions techniques :**
- ADR-013 (refacto Terraform par composant) délibérément mis de côté — valeur portfolio insuffisante au regard de la complexité ; à réévaluer après M2

---

### PR #34 — chore: audit conventions — modules, CI/CD, doc
**Date :** 2026-05-12

**Réalisé :**
- **C-01** : `description` ajoutée sur tous les outputs sans description dans `modules/resource_group/`, `modules/servicebus/`, `modules/keyvault_secret/` — règle "No exceptions" du CLAUDE.md
- **C-02/C-03** : tag `protect=true` ajouté dans `modules/vnet/` et `modules/resource_group/` — sans ce tag, la policy auto-lock ne déclenchait pas le lock CanNotDelete sur ces ressources
- **M-02** : blocs `validation` ajoutés sur les variables à contraintes évidentes dans `modules/keyvault/`, `modules/postgresql/`, `modules/servicebus/`, `modules/container_registry/`, `modules/openai/`, `modules/application_insights/`, `modules/container_app_job/`
- **M-03/M-04** : tag `protect=true` ajouté dans `modules/container_app_environment/` et `modules/application_insights/` (les deux ressources avaient `prevent_destroy = true` mais pas le tag)
- **M-01** : artefacts AWS (`instance_type`/`t2.micro`) retirés des placeholders `modules/data/variables.tf` et `modules/network/variables.tf`
- **A-04** : `prevent_destroy = true` sur `azurerm_servicebus_queue` — déjà présent sur `dev`, aucun changement appliqué dans cette PR
- **A-03** : outputs `id`/`name` manquants ajoutés sur `modules/application_insights/` et `modules/keyvault/`
- **CI-01/02/03** : system prompt du reviewer agent mis à jour — provider `~> 4.0`, lz_prod retiré des envs actifs, lifecycle rules étendues, section env consistency corrigée
- **CI-04** : `fmt -check` et `validate` ajoutés dans les jobs `apply-lz-dev` et `apply-dev` — protection minimale pour les hotfixes qui passeraient hors workflow Plan
- **D-01 à D-06** : `CLAUDE.md` mis à jour — version provider, trigger CI/CD, credentials GitHub, liste des modules (16 entrées), note t2.micro supprimée, lifecycle rules étendues, section env consistency corrigée
- `docs/MANUAL_OPERATIONS.md` : refonte pour refléter l'architecture dual-SP actuelle

**Décisions techniques :**
- Le tag `protect=true` est la condition déclenchant la policy `deployIfNotExists` pour le lock automatique — un `prevent_destroy` sans ce tag ne couvre pas la policy auto-lock
- `validation` blocks uniquement sur les contraintes bien définies : enums, plages numériques, format regex — pas sur les champs libres validés par Azure à l'apply
- `fmt -check` + `validate` dans Apply : garde-fou minimal indépendant du workflow Plan

---

### PR #35 — refactor(dev): migrate container_app_environment inline resource to module
**Date :** 2026-05-12

**Réalisé :**
- `envs/dev/container_apps.tf` : la ressource inline `azurerm_container_app_environment` est remplacée par un appel à `module.container_app_environment` — le module apporte le tag `protect=true` et `prevent_destroy = true` que la ressource inline n'avait pas
- Bloc `moved {}` ajouté pour migrer l'adresse de state sans destroy

**Décisions techniques :**
- La ressource inline était protégée par `prevent_destroy = true` mais sans le tag `protect=true` — la policy auto-lock ne déclenchait pas de lock CanNotDelete dessus
- Le bloc `moved {}` est supprimable après le premier apply réussi confirmant la migration de state

---

### PR #36 — fix: remove protect tag from resource groups to avoid auto-lock conflict
**Date :** 2026-05-12

**Réalisé :**
- `modules/resource_group/main.tf` : suppression du tag `protect = "true"` — `prevent_destroy = true` est conservé dans le bloc `lifecycle`
- `CLAUDE.md` : entrée `azurerm_resource_group` dans "Lifecycle rules" précisée — `prevent_destroy = true` uniquement, avec note explicative ; "Blocking criteria" mis à jour pour documenter l'exception intentionnelle
- `.github/reviewer-agent/system-prompt.md` : exception ajoutée pour `azurerm_resource_group` dans la checklist lifecycle
- `.github/workflows/terraformPlan.yml` : condition `app=true` étendue aux changements dans `modules/` — un changement de module impacte les deux layers (`lz_dev` et `dev`), les deux plans sont désormais déclenchés en parallèle

**Décisions techniques :**
- Le tag `protect = "true"` déclenche la policy `deployIfNotExists` qui applique un lock `CanNotDelete` sur la ressource. Appliqué sur un Resource Group, ce lock bloque les opérations Terraform sur ses ressources enfants (création, modification, suppression)
- Accorder à `sp-jf-github` les droits nécessaires pour contourner ce lock (`Microsoft.Authorization/locks/delete`) imposerait un scope subscription trop large — en contradiction avec le principe de moindre privilège
- La protection est assurée par `prevent_destroy = true` seul, ce qui est suffisant pour prévenir les destructions accidentelles via Terraform
- `modules/` est partagé entre `lz_dev` et `dev` — ne déclencher que `plan-platform` sur un changement de module laissait `plan-app` aveugle à l'impact réel

---

### PR #37 — fix: add Contributor role to sp-jf-platform for lz_dev resource management
**Date :** 2026-05-12

**Réalisé :**
- `JobFinder/powershell/setup-sp-jf-platform.ps1` : ajout d'un role assignment `Contributor` au scope subscription, section 3. Role Assignments, après `Resource Policy Contributor` ; commentaire d'en-tête mis à jour
- `docs/MANUAL_OPERATIONS.md` : `Contributor` ajouté à la liste des rôles de sp-jf-platform
- Script exécuté manuellement pour appliquer le role assignment sur le SP existant

**Décisions techniques :**
- sp-jf-platform applique `lz_dev` via la CI/CD — sans `Contributor`, il ne peut ni créer ni modifier les ressources Azure de la landing zone (VNet, subnets, Key Vault, policies)
- `RBAC Administrator` (conditionné) couvre uniquement les opérations IAM ; `Resource Policy Contributor` couvre uniquement les policies — aucun des deux ne suffit pour provisionner des ressources
- Scope subscription nécessaire : lz_dev déploie dans son propre resource group (`rg-jf-lz-dev-frc`), qui n'existe pas au moment du premier apply — un scope RG serait donc circulaire

---

### PR #38 — docs: journal v0.2.0 merge entry + backlog hardening sp-jf-platform
**Date :** 2026-05-18

**Réalisé :**
- Ajout d'un item BACKLOG (section Sécurité) pour réduire le scope `Contributor` de `sp-jf-platform` de la subscription vers `rg-jf-lz-dev-frc` une fois la landing zone stable

---

### PR #39
```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   🔀  MERGE dev → main — 2026-05-18                                         ║
║   🏷️  v0.2.0                                                                 ║
║   Full dev infrastructure cleaned  (PRs #34 à #38)                         ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║   Audit & conventions                                                        ║
║   ─────────────────────────────────────────────────────────────────────      ║
║   • PR #34  Descriptions outputs, tag protect, validations modules,         ║
║             review agent ~> 4.0, fmt/validate dans Apply                    ║
║   • PR #35  Migration azurerm_container_app_environment → module            ║
║             (protect tag + moved block)                                     ║
║                                                                              ║
║   Corrections gouvernance                                                    ║
║   ─────────────────────────────────────────────────────────────────────      ║
║   • PR #36  Retrait tag protect des Resource Groups (auto-lock conflit),    ║
║             plan CI étendu aux modules/, CLAUDE.md traduit en anglais       ║
║   • PR #37  Rôle Contributor ajouté à sp-jf-platform (scope subscription)  ║
║                                                                              ║
║   Documentation                                                              ║
║   ─────────────────────────────────────────────────────────────────────      ║
║   • PR #38  Entrée journal + item backlog hardening sp-jf-platform scope    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

### PR #40 — fix: remove job-embedding-cv Container App Job and cv-ready Service Bus queue
**Date :** 2026-05-18

**Réalisé :**
- `envs/dev/container_apps.tf` : suppression du bloc `module "job_embedding_cv"` (job-jf-dev-frc-embedding-cv, trigger queue `cv-ready`)
- `envs/dev/servicebus.tf` : suppression de la queue `cv-ready` de la liste `queues` ; mise à jour du commentaire d'en-tête

**Décisions techniques :**
- L'embedding CV se fait désormais de manière synchrone dans la web app (M3) via `shared/embedder.py`, appelé directement au moment de l'upload utilisateur
- Un Container App Job queue-triggered pour une action utilisateur unique (upload CV) ajoutait un cold start de 15-30s sans bénéfice réel — la latence est plus acceptable en synchrone dans la requête HTTP
- La queue `cv-ready` n'a plus de producteur ni de consommateur — la supprimer évite de provisionner une ressource inutilisée

---

### PR #41 — feat: Python foundation — shared layer and agent scaffolding
**Date :** 2026-05-19

**Réalisé :**
- `JobFinder/python/requirements.txt` : dépendances communes à tous les agents (SQLAlchemy, psycopg2, pgvector, azure-servicebus, azure-storage-blob, openai, alembic, python-dotenv, structlog)
- `JobFinder/python/.env.example` : template des variables d'environnement requis, commité sans vraies valeurs
- `JobFinder/python/shared/models.py` : modèles SQLAlchemy avec `Base` partagée — tables `offers`, `cvs`, `matches` ; UUID v4, contraintes nommées (`uq_offers_ft_id`, `fk_matches_cv_id_ref_cvs`, `fk_matches_offer_id_ref_offers`), embeddings `Vector(1536)` via `pgvector.sqlalchemy`
- `JobFinder/python/shared/db.py` : `get_engine()` singleton via `lru_cache` ; `get_session()` via `Session(get_engine())` (SQLAlchemy 2.0, rollback automatique) ; `run_migrations()` via Alembic programmatique
- `JobFinder/python/shared/bus.py` : `send_message()` sérialise en JSON ; `receive_messages()` décode le JSON et yield un `dict` — le ack/nack Service Bus est géré en interne
- `JobFinder/python/shared/embedder.py` : `embed(texts: list[str]) -> list[list[float]]` — un seul appel API pour tout le batch, `try/except openai.OpenAIError` avec re-raise
- Squelettes `# TODO` pour 4 agents dans `JobFinder/python/agents/` : `offer_fetching/`, `embedding_offer/`, `matching/`, `cleanup/`

**Décisions techniques :**
- Variables d'environnement et constantes lues au niveau module : une variable manquante échoue au démarrage du container — fail-fast
- `Session(get_engine())` en context manager (SQLAlchemy 2.0) : remplace `sessionmaker(bind=...)` déprécié, `close()` géré par le context manager
- `receive_messages()` yielde un `dict` : le décodage JSON est encapsulé dans `bus.py`, les agents ne manipulent pas le message Service Bus brut
- `embed()` accepte un batch : un seul appel API pour N textes, réduit la latence et le coût par rapport à N appels unitaires

---

### PR #42 — feat: Alembic migration configuration and initial schema
**Date :** 2026-05-19

**Réalisé :**
- `JobFinder/python/migrations/alembic.ini` : configuration Alembic — `script_location = migrations`, `prepend_sys_path = .` pour que `shared` soit importable, `sqlalchemy.url` laissé en placeholder (la connexion réelle vient de `get_engine()` dans env.py)
- `JobFinder/python/migrations/env.py` : environnement Alembic en mode online uniquement — importe `Base.metadata` depuis `shared.models` et `get_engine()` depuis `shared.db` ; aucune dépendance directe à `sqlalchemy.url` de l'ini
- `JobFinder/python/migrations/versions/001_initial_schema.py` : migration initiale créant les trois tables dans l'ordre des dépendances FK — `offers`, `cvs`, `matches` ; active l'extension `vector` (pgvector) avant la création des tables ; `downgrade()` supprime dans l'ordre inverse

**Décisions techniques :**
- `DateTime(timezone=True)` sur toutes les colonnes datetime : aligné sur la convention `datetime.now(timezone.utc)` des modèles — stockage UTC garanti côté base
- `postgresql.UUID(as_uuid=True)` pour les PK et FK : cohérent avec `UUID(as_uuid=True)` dans les modèles SQLAlchemy
- `CREATE EXTENSION IF NOT EXISTS vector` dans `upgrade()` : idempotent — pas d'erreur si l'extension est déjà présente ; nécessite que l'extension pgvector soit installée sur le serveur PostgreSQL (déjà activée via Terraform : `azurerm_postgresql_flexible_server_configuration` avec `azure.extensions = VECTOR`)
- `run_migrations_offline()` explicitement défini dans env.py pour lever `NotImplementedError` — évite toute misconfiguration silencieuse si alembic est invoqué en mode offline
- `downgrade()` implémenté (`matches` → `cvs` → `offers`) : convention de projet — toute migration doit être réversible

**Corrections post-review :**
- `server_default=sa.text("now()")` ajouté sur les trois colonnes `created_at` — garantit la valeur même lors d'un INSERT sans ORM (ex : scripts de migration de données)
- Index ajoutés sur les FK de `matches` (`ix_matches_cv_id`, `ix_matches_offer_id`) — les FK sans index entraînent des full scans lors des JOINs
- Contrainte d'unicité composite `uq_matches_cv_offer` (`cv_id`, `offer_id`) ajoutée dans la migration et dans `Match.__table_args__` — empêche un double matching du même couple CV/offre

---

### Décisions architecturales M2 — 2026-05-20

Session de design ayant conduit à une refonte complète de l'architecture M2.
Ces décisions sont reflétées dans `docs/ROADMAP.md` (section M2 réécrite).

**Pivot fetch des offres**
Le Container App Job `job-offer-fetching` (timer) est remplacé par un GitHub Actions
cron. L'embedding des offres se fait inline dans le script de fetch — pas d'agent
séparé. Raison : un Container App Job timer pour appeler une API externe est du
sur-engineering. GitHub Actions est plus simple, sans coût infra, et démontre les
mêmes compétences (OAuth2, pagination, gestion d'erreurs).

**Pipeline multi-agent stabilisé**

```
GitHub Actions cron (2x/jour)
  → fetch France Travail (OAuth2, pagination, par codes ROME)
  → embedding batch inline
  → stockage offers table + rome_code
  → post offer-ready

job-matching (queue: offer-ready)         ← Agent LLM 1
  → filtre par rome_codes du profil utilisateur
  → vector search pgvector
  → GPT-4o-mini : score + explication
  → post match-ready

job-cv-review (queue: match-ready)        ← Agent LLM 2 (dernière feature)
  → analyse CV vs top-3 offres
  → GPT-4o-mini : gaps + suggestions personnalisées
  → notification utilisateur
```

**Domaines de fetch — design intent-first**
- Le fetch n'est pas total (tous les domaines IT) mais ciblé par codes ROME.
- Les codes ROME viennent des profils utilisateurs, pas d'une config statique.
- Onboarding : l'utilisateur sélectionne des **catégories lisibles** (Développement,
  Data, DevOps…) — le mapping vers les codes ROME est fait en interne. Aucun code
  ROME n'est exposé dans l'UI.
- Upload CV : un agent CV-analysis (GPT-4o-mini) extrait et affine les codes ROME
  depuis le texte du CV — le profil devient plus précis automatiquement.
- Bootstrap (DB vide) : liste de secours prédéfinie (M1805, M1802, M1806…).
- Le cron GitHub Actions lit l'union des `rome_codes` depuis `user_profiles` en DB.

**Fetch et upload CV — déclenchement**
- Le cron tourne 2x/jour indépendamment des uploads.
- À l'upload d'un CV : matching immédiat contre les offres existantes en base
  (max 12h de retard). L'utilisateur voit des résultats sans attendre le prochain cron.
- Pas de fetch déclenché par l'upload — évite la dépendance à l'API GitHub depuis
  la web app.

**Nettoyage des codes ROME orphelins**
- Le `job-cleanup` supprime les offres pour des codes ROME n'ayant plus aucun
  utilisateur actif, avec une grace period de 7 jours.
- La DB reste propre sans mécanisme dédié.

**Schéma DB — ajouts M2**
- Table `user_profiles` : `rome_codes TEXT[]`, `job_categories TEXT[]`,
  `location TEXT`, `contract_types TEXT[]`
- Table `offers` : colonne `rome_code TEXT` ajoutée (filtrage au matching)

**Azure AI Search — note**
pgvector reste le choix correct pour ce volume (<50K offres en dev). Azure AI Search
(hybrid search BM25 + vectoriel + semantic reranker) devient pertinent au-delà de
200-500K vecteurs ou si la recherche devient un goulot d'étranglement sur PostgreSQL.
Tracé en BACKLOG comme évolution future (déjà documenté en ADR-003).

---

### PR #43 — feat(m2): GitHub Actions offer-fetch cron, user_profiles schema, Terraform M2 pivot
**Date :** 2026-05-20

**Réalisé :**

*Terraform*
- `envs/dev/container_apps.tf` : suppression des blocs `module "job_offer_fetching"` (timer) et `module "job_embedding_offer"` (queue offer-ready) — remplacés par le cron GitHub Actions
- `envs/dev/container_apps.tf` : `module "job_matching"` rebranchée sur la queue `offer-ready` (anciennement `match-ready`) — le matching est déclenché dès qu'une nouvelle offre est disponible en base
- `envs/dev/container_apps.tf` : suppression du bloc `moved {}` hérité de PR #35 — apply de migration de state confirmé lors du merge dev→main du 2026-05-18
- `envs/dev/servicebus.tf` : commentaire d'en-tête mis à jour ; les deux queues `offer-ready` et `match-ready` sont conservées

*Schéma DB*
- `shared/models.py` : modèle `UserProfile` ajouté (`rome_codes`, `job_categories`, `location`, `contract_types`) ; colonnes `rome_code` et `ft_updated_at` ajoutées sur `Offer`
- `migrations/versions/002_add_user_profiles_and_rome_code.py` : migration Alembic — table `user_profiles`, colonnes `offers.rome_code` (index `ix_offers_rome_code`) et `offers.ft_updated_at`

*Python / scripts*
- `agents/offer_fetching/` et `agents/embedding_offer/` supprimés
- `scripts/ft_client.py` : client France Travail — `get_access_token()` OAuth2, `fetch_offers(token, rome_code)` avec pagination curseur par tranches de 50 ; `requests.Session` réutilisé entre les pages ; arrêt sur `Content-Range` total en plus de `len(page) < PAGE_SIZE`
- `scripts/fetch_offers.py` : script cron complet — codes ROME depuis `user_profiles` (fallback liste IT prédéfinie), fetch par code ROME, upsert batch unique par code ROME avec `RETURNING xmax` pour comptage atomique des inserts, embedding réinitialisé conditionnellement via `case()` si `ft_updated_at` est plus récent ; session SELECT et session UPDATE séparées autour de l'appel OpenAI dans `_embed_pending_offers` ; mutation ORM + `add_all` pour batcher les UPDATEs en un seul flush ; `send_message(offer-ready)` conditionnel (`total_new > 0`)
- `shared/db.py` : `POSTGRESQL_CONNECTION_STRING` → `DATABASE_URL`
- `requirements.txt` : `requests` ajouté

*Workflow & infra*
- `.github/workflows/offerFetch.yml` : cron 12:00/20:00 UTC + `workflow_dispatch` ; secrets récupérés depuis Key Vault via `${{ vars.AZURE_KEYVAULT_NAME }}` (variable GitHub) via OIDC — aucun GitHub Secret applicatif ; `pip install --no-cache-dir` pour reproductibilité CI
- `envs/dev/container_apps.tf` : note ajoutée en tête de section Agent Jobs indiquant que le fetch est désormais géré par GitHub Actions
- `.gitignore` : patterns Python ajoutés (`__pycache__/`, `*.pyc`, `*.pyo`)
- `docs/MANUAL_OPERATIONS.md` : section "France Travail API — Credentials" — procédure d'inscription et stockage des secrets dans le Key Vault
- `docs/ROADMAP.md` : architecture M2 réécrite

**Décisions techniques :**
- Container App Jobs `job-offer-fetching` et `job-embedding-offer` supprimés : GitHub Actions cron élimine deux ressources Azure et leur coût de provisionnement ; embedding inline dans le script coélimine un aller-retour Service Bus
- `job_matching` sur `offer-ready` (pas `match-ready`) : le matching est déclenché par l'arrivée de nouvelles offres — `match-ready` reste le signal de fin de matching pour la notification utilisateur (M3) et le futur agent cv-review
- Pagination curseur (`range: 0-49, 50-99...`) : format imposé par l'API France Travail via le header `range` ; la boucle s'arrête dès qu'une page est incomplète
- Upsert `ON CONFLICT (ft_id) DO UPDATE` avec réinitialisation conditionnelle de `embedding` : l'embedding est remis à `NULL` uniquement si `ft_updated_at` entrant est plus récent que la valeur stockée (ou si la valeur stockée est `NULL`) — les offres non modifiées conservent leur vecteur, économie de tokens OpenAI
- Embedding batch après tous les upserts : un seul appel API pour toutes les nouvelles offres, quel que soit le nombre de codes ROME traités dans le run
- Session DB fermée avant l'appel OpenAI dans `_embed_pending_offers` : un appel externe lent ou défaillant ne maintient pas de connexion ouverte inutilement
- `RETURNING xmax` pour compter les vrais inserts dans `_upsert_offers` : atomique dans la même transaction, sans race condition possible avec un pre-fetch `SELECT`
- Message `offer-ready` conditionnel (`total_new > 0`) : évite de déclencher `job-matching` inutilement si aucune nouvelle offre n'a été insérée
- Secrets depuis Key Vault via OIDC : les secrets applicatifs vivent en un seul endroit ; pas de synchronisation manuelle ni de rotation en double entre KV et GitHub Secrets
- `add-mask` avant injection dans `$GITHUB_ENV` : masquage dans les logs de l'étape courante, pas seulement des suivantes

---

### PR #44 — feat(matching): job-matching agent with pgvector cosine similarity
**Date :** 2026-05-26

**Réalisé :**

*Python / agents*
- `agents/matching/main.py` : agent de matching — consomme un message `offer-ready`, requête tous les CVs avec embedding, calcule le top-20 des offres les plus proches par similarité cosine (pgvector `<=>`) pour chaque CV, upsert dans `matches`, poste un message `match-ready` avec résumé
- `agents/matching/Dockerfile` : image Python 3.12-slim, workdir `/app`, `CMD ["python", "agents/matching/main.py"]`

**Décisions techniques :**
- Similarité cosine via pgvector `<=>` (distance) : score = `1 - cosine_distance`, tri `ORDER BY distance ASC` pour les K plus proches — pas de GPT-4o-mini à ce stade, score brut suffisant pour le ranking
- `_get_top_matches` et `_upsert_matches` prennent une session en paramètre : une seule session ouverte par run de matching, partagée entre les deux fonctions pour éviter la multiplicité de connexions
- `RETURNING xmax` dans `_upsert_matches` : comptage atomique des vrais inserts, cohérent avec le pattern établi dans `fetch_offers.py`
- Si aucun CV en base : log `matching_no_cvs_found` et sortie propre (ack du message via `receive_message` contextmanager) — pas d'erreur, pas de message `match-ready`
- `distance_expr` extrait en variable locale dans `_get_top_matches` : évite de dupliquer l'expression pgvector dans `select()` et `order_by()`

---

### PR #45 — feat(cleanup): cleanup agent — purge stale offers and orphaned matches
**Date :** 2026-05-26

**Réalisé :**

*Python / agents*
- `agents/cleanup/main.py` : agent de cleanup — supprime les offres périmées (> `CLEANUP_OFFER_MAX_AGE_DAYS` jours) et leurs matches associés en 3 étapes atomiques dans une seule transaction ; aucune interaction avec Service Bus, déclenché par timer KEDA à 02:00 UTC
- `agents/cleanup/Dockerfile` : image Python 3.12-slim, workdir `/app`, `PYTHONPATH=/app`, `CMD ["python", "agents/cleanup/main.py"]`

*Python / scripts*
- `scripts/ft_client.py` : `fetch_offers()` accepte un paramètre `min_date: str | None` — si fourni, ajoute `minDateActualisation` aux params de la requête API France Travail pour ne récupérer que les offres récentes
- `scripts/fetch_offers.py` : calcul de `min_date` basé sur `CLEANUP_OFFER_MAX_AGE_DAYS` avant la boucle sur les codes ROME — même variable d'environnement que le cleanup, une seule valeur à configurer

**Décisions techniques :**
- Suppression en 3 étapes ordonnées (`SELECT id` → `DELETE matches` → `DELETE offers`) dans une session unique : garantit l'atomicité et évite les violations de contrainte FK — une suppression directe des offres laisserait les matches orphelins si la FK n'est pas `ON DELETE CASCADE`
- `CLEANUP_OFFER_MAX_AGE_DAYS` partagée entre cleanup et fetch : la rétention est un paramètre métier unique, pas deux constantes à synchroniser
- `ft_updated_at` prioritaire sur `collected_at` pour la date de référence : une offre sans `ft_updated_at` est traitée sur sa date de collecte en fallback

---

### PR #46 — feat: CI/CD build and push Docker images to ACR
**Date :** 2026-05-26

**Réalisé :**

*GitHub Actions*
- `.github/workflows/buildAgents.yml` : workflow déclenché sur push vers `dev` quand `JobFinder/python/**` change (+ `workflow_dispatch`) — build et push deux images Docker vers ACR avec `docker/build-push-action@v6` : `agents/matching` et `agents/cleanup`, tags `:latest` + `:sha`, layer cache via ACR

**Décisions techniques :**
- Auth ACR via `az acr login` après `azure/login@v2` OIDC : pas de service principal password stocké, même pattern que `offerFetch.yml`
- Login server ACR lu depuis Key Vault (`acr-login-server`) avec `add-mask` : évite d'exposer le nom du registry dans les logs
- `docker/setup-buildx-action@v3` requis avant `docker/build-push-action@v6` pour activer BuildKit — nécessaire pour le cache de type `registry`
- Layer cache stocké dans ACR (`agents/<agent>:cache`, `mode=max`) : réduit le temps de build en réutilisant les layers `pip install` entre les runs
- Tags `:latest` + `:<sha>` : `:latest` pour le déploiement Terraform, `:<sha>` pour la traçabilité et le rollback
- Build context `JobFinder/python/` : couvre `shared/` requis par les deux agents
- Path filter `JobFinder/python/**` : le workflow ne se déclenche que si du code Python change, pas sur des commits Terraform ou docs

---

### PR #47 — feat(lz): grant conditioned RBAC Administrator to sp-jf-github on dev resource groups
**Date :** 2026-05-26

**Réalisé :**

*Terraform / lz_dev*
- `lz_dev/rbac.tf` : `azurerm_role_assignment.sp_github_rbac_admin` ajouté — RBAC Administrator conditionné scopé aux trois resource groups dev (`rg_core`, `rg_app`, `rg_data`), via `for_each` sur `local.sp_github_rbac_admin_scopes`

**Décisions techniques :**
- Même condition anti-escalade que `sp-jf-platform` : interdit d'assigner Owner, User Access Administrator, ou Role Based Access Control Administrator — sp-jf-github ne peut pas s'auto-élever
- Scopé aux RGs dev uniquement (pas à la subscription) : surface d'exposition minimale
- Géré dans `lz_dev/` plutôt que `iam/` : `sp-jf-platform` (qui possède RBAC Administrator) peut appliquer via CI/CD, sans intervention manuelle

---

### PR #48 — feat(module): add identity and registry support to container_app_job module
**Date :** 2026-05-26

**Réalisé :**

*Terraform / modules*
- `modules/container_app_job/variables.tf` : trois variables ajoutées — `identity_ids` (list, défaut `[]`), `registry_server` (string nullable), `registry_identity` (string nullable)
- `modules/container_app_job/main.tf` : deux blocs `dynamic` ajoutés après `secret` — `identity` (UserAssigned, conditionné sur `length(identity_ids) > 0`) et `registry` (conditionné sur `registry_server != null`)

**Décisions techniques :**
- Blocs `dynamic` conditionnels : si aucune identité ou registry n'est passé, les blocs sont absents du plan — rétrocompatibilité totale avec les callers existants sans modification
- `identity_ids` en `list(string)` : l'azurerm provider attend une liste même pour une seule identité
- `registry_identity` accepte `null` par défaut : permet d'utiliser `registry_server` avec une auth par token si besoin, sans forcer une UAMI

---

### PR #49 — feat: create UAMI and AcrPull role assignment for Container App Jobs
**Date :** 2026-05-26

**Réalisé :**

*Terraform / envs/dev*
- `container_apps.tf` : `azurerm_user_assigned_identity.caj` créée (`id-jf-dev-frc-caj`) — identité partagée pour tous les agent jobs
- `container_apps.tf` : `azurerm_role_assignment.caj_acr_pull` — rôle `AcrPull` assigné sur l'ACR, scopé à `module.container_registry.id`
- `job_matching` et `job_cleanup` : `identity_ids`, `registry_server`, `registry_identity` câblés sur la UAMI

**Décisions techniques :**
- UAMI partagée entre les deux jobs : un seul objet à gérer, une seule assignation AcrPull — les jobs n'ont pas de secrets distincts liés à l'identité
- `AcrPull` scopé à l'ACR (pas au RG) : surface minimale, le job peut seulement puller des images, pas pousser ni gérer le registry
- Les images restent en placeholder (`mcr.microsoft.com/azuredocs/containerapps-helloworld`) sur cette branche — le câblage ACR est prêt, les images réelles seront poussées par `buildAgents.yml` et référencées dans une PR distincte

---

### PR #50 — feat(terraform): wire secrets and ACR images for matching and cleanup jobs
**Date :** 2026-05-26

**Réalisé :**

*Terraform / envs/dev*
- `container_apps.tf` — `job_matching` : image basculée sur ACR, 4 secrets ajoutés (servicebus, postgresql, openai-api-key, openai-endpoint), 5 env vars câblées dont `MATCHING_TOP_K`
- `container_apps.tf` — `job_cleanup` : image basculée sur ACR, secret postgresql ajouté, 2 env vars câblées dont `CLEANUP_OFFER_MAX_AGE_DAYS`
- Commentaire TODO `M2: basculer sur key_vault_secret_id` supprimé du bloc `locals`

*Terraform / modules*
- `modules/postgresql/outputs.tf` : output `connection_string` ajouté — expose la valeur de la connection string (sensitive) plutôt que le resource ID du KV secret

**Décisions techniques :**
- `module.postgresql.connection_string` (valeur en clair, sensitive) plutôt que `connection_string_secret_id` (resource ID) : les Container App Jobs consomment la chaîne de connexion directement dans le bloc `secret`
- `MATCHING_TOP_K` et `CLEANUP_OFFER_MAX_AGE_DAYS` passés en valeur directe (`value = "20"` / `"60"`) : paramètres de tuning non sensibles, pas des secrets
- La connection string Service Bus reste en `local.servicebus_connection_string` (plain string) — migration vers KV reference avec Managed Identity prévue en M3

---

### PR #51 — refactor(lz): move UAMI and AcrPull to lz_dev, update CAJ image on push
**Date :** 2026-05-26

**Contexte :**
L'approche PR #47 (RBAC Administrator conditionné sur sp-jf-github) est impossible : la condition ABAC sur sp-jf-platform interdit à ce dernier d'assigner le rôle `Role Based Access Control Administrator`, même conditionné. La UAMI et le rôle AcrPull doivent donc être gérés directement par sp-jf-platform depuis lz_dev.

**Réalisé :**

*Terraform / lz_dev*
- `lz_dev/rbac.tf` : suppression de `azurerm_role_assignment.sp_github_rbac_admin` et des locals associés (`sp_github_rbac_admin_scopes`, `rbac_admin_condition`) — approche impossible
- `lz_dev/rbac.tf` : ajout de `azurerm_user_assigned_identity.caj` (`id-jf-dev-frc-caj`, dans `rg_core`) — géré par sp-jf-platform
- `lz_dev/rbac.tf` : ajout de `data "azurerm_container_registry" "acr"` et `azurerm_role_assignment.caj_acr_pull` — rôle `AcrPull` assigné directement par sp-jf-platform
- `lz_dev/outputs.tf` : outputs `caj_identity_id` et `caj_identity_principal_id` exposés pour référencement depuis dev/

*Terraform / envs/dev*
- `container_apps.tf` : `resource "azurerm_user_assigned_identity" "caj"` remplacé par `data "azurerm_user_assigned_identity" "caj"` — lit la UAMI créée par lz_dev
- `container_apps.tf` : `resource "azurerm_role_assignment" "caj_acr_pull"` supprimé — désormais géré dans lz_dev

*GitHub Actions*
- `buildAgents.yml` : step `Update Container App Job images` ajouté après le push — met à jour les Container App Jobs avec le SHA précis via `az containerapp job update`

**Décisions techniques :**
- La condition ABAC de sp-jf-platform (`ForAnyOfAllValues:GuidNotEquals`) bloque l'assignation de `Role Based Access Control Administrator` — rôle exclus par la condition elle-même. L'approche RBAC Admin délégué est donc structurellement inapplicable.
- UAMI déplacée dans `rg_core` (et non `rg_app`) : la Managed Identity est une ressource d'infrastructure partagée, pas une ressource applicative
- `az containerapp job update --image` : force le job à utiliser l'image SHA précis du commit — évite les dérives de `:latest` entre deux builds
- Séquencement d'apply : lz_dev doit être appliqué avant dev (la data source échoue si la UAMI n'existe pas)

---

### PR #52 — docs: mise à jour JOURNAL.md — entrée merge PR #53
**Date :** 2026-05-27

**Réalisé :**
- Ajout de l'entrée de merge PR #53 dans `docs/JOURNAL.md` — récapitulatif des PRs #40 à #52 dans le format de PR #39

---

### PR #53
```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   🔀  MERGE dev → main — 2026-05-27                                         ║
║   🏷️  v0.3.0                                                                 ║
║   Milestone 2 — Agents Python + CI/CD images  (PRs #40 à #52)              ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║   Architecture M2 — Pivot                                                    ║
║   ─────────────────────────────────────────────────────────────────────      ║
║   • PR #40  Suppression job-embedding-cv et queue cv-ready                  ║
║   • PR #43  Cron GitHub Actions offer-fetch, schéma user_profiles,          ║
║             pivot Terraform (jobs offer-fetching + embedding supprimés)     ║
║                                                                              ║
║   Agents Python                                                              ║
║   ─────────────────────────────────────────────────────────────────────      ║
║   • PR #41  Couche shared (models, db, bus, embedder) + scaffolding         ║
║   • PR #42  Alembic — migration initiale (tables offers, cvs, matches)      ║
║   • PR #44  Agent matching — pgvector cosine similarity, upsert matches     ║
║   • PR #45  Agent cleanup — purge offres périmées + matches orphelins       ║
║                                                                              ║
║   CI/CD & images Docker                                                      ║
║   ─────────────────────────────────────────────────────────────────────      ║
║   • PR #46  Workflow build/push images Docker → ACR (matching, cleanup)     ║
║             tags :latest + :sha, layer cache ACR, az containerapp update    ║
║                                                                              ║
║   Infrastructure Terraform                                                   ║
║   ─────────────────────────────────────────────────────────────────────      ║
║   • PR #47  RBAC Admin conditionné sp-jf-github — inapplicable              ║
║             (condition ABAC sp-jf-platform) ; remplacé par PR #51           ║
║   • PR #48  Module container_app_job — support UAMI et registry             ║
║   • PR #49  UAMI caj + rôle AcrPull sur ACR pour les Container App Jobs     ║
║   • PR #50  Câblage secrets et images ACR (job_matching + job_cleanup)      ║
║   • PR #51  UAMI migrée dans lz_dev, gérée par sp-jf-platform               ║
║                                                                              ║
║   Documentation                                                              ║
║   ─────────────────────────────────────────────────────────────────────      ║
║   • PR #52  Mise à jour journal — entrée merge PR #53                       ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

### PR #54 — feat: migrate offer-fetching from GitHub Actions to Container App Job
**Date :** 2026-05-27

**Réalisé :**
- `agents/offer_fetching/main.py` : contenu de `scripts/fetch_offers.py` déplacé ici — import mis à jour (`from ft_client import` au lieu de `from scripts.ft_client import`)
- `agents/offer_fetching/ft_client.py` : contenu de `scripts/ft_client.py` déplacé ici
- `scripts/` : supprimé (dossier devenu vide)
- `agents/offer_fetching/Dockerfile` : image Python 3.12-slim identique aux autres agents
- `envs/dev/container_apps.tf` : ajout de `module "job_offer_fetching"` — trigger timer `0 12,20 * * *`, image ACR, UAMI caj, 5 secrets (servicebus, postgresql, openai-api-key, ft-client-id, ft-client-secret) ; data sources `ft_client_id` et `ft_client_secret` ajoutés ; locals étendus (`postgresql_connection_string`, `openai_api_key`, `openai_endpoint`, `ft_client_id`, `ft_client_secret`)
- `.github/workflows/buildAgents.yml` : step build/push `offer-fetching` ajouté, build summary et `az containerapp job update` mis à jour pour `job-jf-dev-frc-fetch`
- `.github/workflows/offerFetch.yml` : supprimé

**Décisions techniques :**
- `scripts/fetch_offers.py` et `scripts/ft_client.py` déplacés dans `agents/offer_fetching/` : la logique métier vit au plus près de l'agent qui l'exécute — `scripts/` n'a plus de raison d'exister
- `from ft_client import` (import bare) : le CMD Docker `python agents/offer_fetching/main.py` ajoute `/app/agents/offer_fetching` à `sys.path[0]`, rendant `ft_client.py` importable directement
- `AZURE_OPENAI_ENDPOINT` passé en `value` (pas secret-backed) : l'endpoint OpenAI est une URL non sensible
- `ft-client-id` et `ft-client-secret` lus depuis le Key Vault via data sources : secrets déjà posés manuellement en KV, cohérent avec le pattern des autres agents
- Horaires conservés à 12:00/20:00 UTC (cron `0 12,20 * * *`) : identiques à l'ancien `offerFetch.yml`

---

### PR #55 — feat(lz): add dedicated subnet for Container App Environment VNet injection
**Date :** 2026-05-27

**Réalisé :**
- `lz_dev/network.tf` : ajout de `module "subnet_cae"` — `/23` (`10.0.4.0/23`), délégation `Microsoft.App/environments` avec action `join/action`
- `lz_dev/outputs.tf` : ajout de l'output `subnet_cae_id` exposant le resource ID du subnet pour référencement depuis `dev/`

**Décisions techniques :**
- `/23` (512 adresses) : taille minimale imposée par Azure pour un CAE en VNet injection — un `/24` est insuffisant et provoque une erreur à la création
- Délégation `Microsoft.App/environments` obligatoire : Azure refuse d'injecter un CAE dans un subnet non délégué
- Subnet géré dans `lz_dev` (pas dans `dev`) : appartient à la couche réseau partagée du hub, comme `subnet_app` et `subnet_postgresql`
- `subnet_cae_id` exposé en output : `dev/container_apps.tf` le consommera via `data "terraform_remote_state"` pour injecter le CAE sans hardcoder l'ID

---

### PR #56 — fix(lz): correct subnet_cae CIDR — 10.0.2.0/23 → 10.0.4.0/23
**Date :** 2026-05-27

**Réalisé :**
- `lz_dev/network.tf` : `address_prefixes` de `module "subnet_cae"` corrigé de `10.0.2.0/23` à `10.0.4.0/23`

**Décisions techniques :**
- `10.0.2.0/23` couvre `10.0.2.0–10.0.3.255` et chevauche `10.0.3.0/24` déjà réservé par le subnet PostgreSQL
- `10.0.4.0/23` (`10.0.4.0–10.0.5.255`) est libre dans le VNet `10.0.0.0/16`

---

### PR #57 — feat: inject Container App Environment into VNet via subnet_cae
**Date :** 2026-05-27

**Réalisé :**
- `modules/container_app_environment/variables.tf` : ajout de `infrastructure_subnet_id` (nullable, défaut `null`) — rétrocompatible, pas de VNet injection si non fourni
- `modules/container_app_environment/main.tf` : `infrastructure_subnet_id` câblé sur la ressource ; `prevent_destroy = true` retiré temporairement (`lifecycle {}`) pour autoriser le destroy + recreate imposé par la propriété immutable
- `envs/dev/network.tf` : ajout de `data "azurerm_subnet" "lz_vnet_cae"` — appel ARM direct sur le subnet existant, cohérent avec le pattern `lz_vnet_app`
- `envs/dev/container_apps.tf` : `infrastructure_subnet_id` câblé sur `data.azurerm_subnet.lz_vnet_cae.id`

**Décisions techniques :**
- `infrastructure_subnet_id` est une propriété immutable sur `azurerm_container_app_environment` — toute modification force un destroy + recreate ; `prevent_destroy = true` bloquerait le plan, d'où son retrait temporaire
- `default = null` : les callers existants sans VNet injection ne sont pas impactés — le module reste rétrocompatible
- `data "azurerm_subnet"` plutôt que `terraform_remote_state` : appel API ARM direct, cohérent avec le pattern `network.tf` ; sp-jf-github a déjà `Reader` sur le resource group `lz_dev` depuis PR #33
- PR 3 minimale prévue après apply réussi pour remettre `prevent_destroy = true`

---

### PR #59 — fix(module): remove create_before_destroy from container_app_environment — incompatible with Azure naming constraint
**Date :** 2026-05-27

**Réalisé :**
- `modules/container_app_environment/main.tf` : suppression de `create_before_destroy = true` du bloc `lifecycle` — le bloc ne contient plus que le commentaire de rappel pour `prevent_destroy`

**Décisions techniques :**
- `create_before_destroy = true` impose à Terraform de créer la nouvelle ressource avant de détruire l'ancienne — Azure refuse car les deux porteraient le même nom (`cae-jf-dev-frc`) dans le même resource group simultanément
- Le comportement par défaut (destroy puis create) est ici le seul viable : le CAE doit être détruit avant que le nouveau puisse être créé avec `infrastructure_subnet_id`
- La branche `feature/m2-cae-restore-prevent-destroy` (PR #58) sera rebasée sur dev après merge de cette PR

---

### PR #60 — fix(lz): grant Network Contributor on subnet_cae to sp-jf-github
**Date :** 2026-05-27

**Réalisé :**
- `lz_dev/rbac.tf` : ajout de `subnet_cae_network_contributor` dans `local.sp_role_assignments` — rôle `Network Contributor` scopé à `module.subnet_cae.id` pour `sp-jf-github`

**Décisions techniques :**
- Azure exige `Microsoft.Network/virtualNetworks/subnets/join/action` sur le subnet cible quand une ressource d'un resource group différent s'y attache — c'est le cas du CAE (`rg-jf-dev-frc-app`) sur le subnet (`rg-jf-lz-dev-frc`)
- `Network Contributor` est le rôle minimal incluant cette action — `Contributor` sur le RG ne suffit pas car il ne couvre pas les opérations réseau cross-RG
- Géré dans `lz_dev/rbac.tf` (par sp-jf-platform) : sp-jf-github ne peut pas s'auto-assigner ce rôle
- Ce fix doit être appliqué (lz_dev apply) avant de re-tenter l'apply de dev pour la VNet injection du CAE

---

### PR #58 — feat(module): restore prevent_destroy on container_app_environment after VNet injection
**Date :** 2026-05-27

**Réalisé :**
- `modules/container_app_environment/main.tf` : `prevent_destroy = true` restauré dans le bloc `lifecycle` aux côtés de `create_before_destroy = true`

**Décisions techniques :**
- `prevent_destroy` avait été temporairement retiré en PR #57 pour permettre le replace forcé imposé par `infrastructure_subnet_id` (propriété immuable)
- Une fois l'apply réussi, la protection est immédiatement rétablie — aucune fenêtre de vulnérabilité prolongée
- Les deux flags coexistent : `create_before_destroy = true` assure la continuité lors d'un futur replace éventuel ; `prevent_destroy = true` bloque toute destruction accidentelle via Terraform

---

### PR #61 — fix(shared): resolve alembic.ini path from __file__ instead of WORKDIR
**Date :** 2026-05-27

**Réalisé :**
- `shared/db.py` : `Config("alembic.ini")` remplacé par un chemin absolu construit dynamiquement depuis `__file__`

**Décisions techniques :**
- `Config("alembic.ini")` résout depuis le répertoire courant (`/app`, le WORKDIR Docker) — le fichier est en réalité dans `/app/migrations/alembic.ini`
- `os.path.dirname(__file__)` pointe vers le répertoire de `db.py` (`/app/shared`) quelle que soit la CWD au démarrage — le chemin construit est robuste à tout changement de WORKDIR ou de point d'entrée

---

### PR #62 — fix(offer-fetching): correct FT_SCOPE constant
**Date :** 2026-05-27

**Réalisé :**
- `agents/offer_fetching/ft_client.py` : `FT_SCOPE` corrigé — `"api_offresdemploi_v2 o2dsillage"` → `"api_offresdemploiv2 o2dsoffre"`

**Décisions techniques :**
- La valeur incorrecte provoquait une erreur 401 à la demande de token OAuth2 — le scope ne correspond pas aux APIs déclarées dans le portail France Travail

---

### PR #63 — fix(offer-fetching): deduplicate raw_offers by ft_id before upsert
**Date :** 2026-05-27

**Réalisé :**
- `agents/offer_fetching/main.py` : déduplication par `ft_id` ajoutée au début de `_upsert_offers`, avant la construction de `values`

**Décisions techniques :**
- L'API France Travail peut retourner la même offre sur plusieurs pages consécutives — sans déduplication, l'upsert batcherait des doublons, entraînant des conflits `ON CONFLICT (ft_id)` sur plusieurs lignes du même batch dans la même transaction

---

### PR #64 — fix(dev): increase replica_timeout for job_offer_fetching to 3600s
**Date :** 2026-05-27

**Réalisé :**
- `envs/dev/container_apps.tf` : `replica_timeout_in_seconds = 3600` ajouté sur `module "job_offer_fetching"`

**Décisions techniques :**
- Le défaut du module (300 s) est trop court — l'embedding de ~3 000 offres dépasse 5 minutes avec les retries sur les 429 OpenAI ; Azure tue le container avant la fin
- 3600 s (1 heure) absorbe les retries sans approcher la limite maximale du module (86 400 s)
- Les autres jobs (matching, cleanup) conservent le défaut de 300 s — leurs opérations sont bornées en temps

---

### PR #65 — fix(shared): set max_retries=10 on AzureOpenAI client
**Date :** 2026-05-27

**Réalisé :**
- `shared/embedder.py` : `max_retries=10` ajouté sur le client `AzureOpenAI`

**Décisions techniques :**
- Le SDK OpenAI applique un backoff exponentiel avec jitter sur les 429 (rate limit) — `max_retries=10` donne jusqu'à ~10 tentatives avant d'abandonner, suffisant pour absorber les bursts de 429 lors de l'embedding de plusieurs milliers d'offres
- Le défaut SDK est 2 retries — trop faible pour un batch de ~3 000 offres contre un quota de 10K TPM

---

### PR #70 — fix(shared): materialize Service Bus msg.body generator before json.loads
**Date :** 2026-05-27

**Réalisé :**
- `shared/bus.py` : `json.loads(msg.body)` → `json.loads(b"".join(msg.body))`

**Décisions techniques :**
- Le SDK Azure Service Bus retourne `msg.body` comme un générateur de chunks de bytes (format AMQP), pas un `str` ou `bytes` directement — `json.loads()` lève `TypeError: the JSON object must be str, bytes or bytearray, not generator`
- `b"".join(msg.body)` matérialise le générateur en un seul objet `bytes` que `json.loads()` peut parser

---

### PR #69 — fix(offer-fetching): correct bulk embedding UPDATE to ORM bulk-by-PK pattern
**Date :** 2026-05-27

**Réalisé :**
- `agents/offer_fetching/main.py` : remplacement du bulk `UPDATE` via `bindparam` par le pattern ORM bulk UPDATE par clé primaire de SQLAlchemy 2.x — clés du dict passées de `_id`/`_embedding` à `id`/`embedding`, suppression de `.where()`, `.values()` et `.execution_options(synchronize_session=None)`, suppression de l'import `bindparam` devenu inutile

**Décisions techniques :**
- SQLAlchemy 2.x route `session.execute(update(Model), list_of_dicts)` via le chemin "ORM bulk UPDATE by primary key" — il génère lui-même `UPDATE ... WHERE id = ?` à partir de la clé PK dans chaque dict ; `.where()` et `.values()` sont ignorés sur ce chemin, ce qui était la source de l'`InvalidRequestError: No primary key value supplied` (la clé `_id` ne correspondait pas au nom de colonne PK)
- `bindparam` n'est plus utilisé dans le fichier — import supprimé

---

### PR #68 — fix(offer-fetching): bulk UPDATE synchronize_session + ft_client 429 retry
**Date :** 2026-05-27

**Réalisé :**
- `agents/offer_fetching/main.py` : ajout de `.execution_options(synchronize_session=None)` sur le statement `update(Offer)` dans `_embed_pending_offers()` — corrige le `InvalidRequestError` SQLAlchemy lors du bulk UPDATE des embeddings
- `agents/offer_fetching/ft_client.py` : ajout de `import time`, constantes `MAX_RETRIES = 5` et `INTER_PAGE_SLEEP = 0.5` ; boucle de retry sur HTTP 429 dans `fetch_offers()` — lit le header `Retry-After` (fallback 2s) et sleep avant chaque nouvelle tentative ; `time.sleep(INTER_PAGE_SLEEP)` ajouté entre les pages (pas après la dernière)

**Décisions techniques :**
- `synchronize_session=None` : SQLAlchemy refuse par défaut de synchroniser la session identity map lors d'un `UPDATE` bulk avec `WHERE` additionnel — l'option `None` bypasse cette synchronisation, ce qui est correct ici car les objets `Offer` chargés dans la session précédente ne sont plus référencés
- `MAX_RETRIES = 5` avec `for/else` Python : si les 5 tentatives retournent toutes 429, le `else` raise une `HTTPError` explicite — le `for/else` évite un flag booléen et reste idiomatique
- `Retry-After` fallback à 2s : si le header est absent (comportement non standard de certaines API), on attend 2s avant de réessayer plutôt que de réessayer immédiatement
- `INTER_PAGE_SLEEP = 0.5` uniquement entre les pages intermédiaires (pas après la dernière) : réduit la pression sur le rate limiter sans allonger la durée totale d'un run sur une série courte de pages

---

### PR #67 — fix(shared): batch embed() calls to avoid TPM limit on large corpora
**Date :** 2026-05-27

**Réalisé :**
- `shared/embedder.py` : ajout de la constante `BATCH_SIZE = 100` ; `embed()` découpe maintenant `texts` en chunks de 100, appelle l'API une fois par chunk, collecte les vecteurs en ordre, et attend `time.sleep(1)` entre chaque batch (pas après le dernier)
- Log `embedding_batch_progress` ajouté à chaque chunk avec `batch`, `total_batches`, `count`
- `import time` ajouté

**Décisions techniques :**
- Avec ~3 185 offres (~1,5 M tokens total), un seul appel API dépassait systématiquement le quota TPM, générant des 429 malgré les 10 retries — le batching résout le problème structurellement, indépendamment de la capacité TPM configurée
- `BATCH_SIZE = 100` : taille empiriquement sûre pour rester sous les limites TPM Azure OpenAI, quelle que soit la taille du modèle d'embedding
- `sleep(1)` inter-batch (pas après le dernier) : laisse le fenêtre TPM se réinitialiser partiellement sans bloquer inutilement en fin de run
- La signature `embed(texts: list[str]) -> list[list[float]]` est inchangée — aucun impact sur les appelants

---

### PR #66 — fix(dev): raise OpenAI capacity_tpm from 10 to 1000 for both deployments
**Date :** 2026-05-27

**Réalisé :**
- `envs/dev/openai.tf` : `capacity_tpm` passé de `10` à `1000` sur `gpt-4o-mini` et `text-embedding-3-small`

**Décisions techniques :**
- `capacity_tpm` est exprimé en milliers : `10` = 10 000 TPM, `1000` = 1 000 000 TPM
- Chaque apply Terraform réinitialise cette valeur — toute augmentation manuelle dans le portail Azure est écrasée au prochain apply
- 10 000 TPM était insuffisant pour embedder ~3 000 offres en un seul run, générant des 429 en cascade malgré les retries

---

### PR #71 — docs: mise à jour JOURNAL.md — entrée merge PR #72 et tags versions
**Date :** 2026-05-28

**Réalisé :**
- Ajout de l'entrée de merge PR #72 dans `docs/JOURNAL.md` — récapitulatif des PRs #54 à #71 dans le format de PR #53
- Ajout des tags de version sur toutes les entrées de merge dev→main (`v0.1.1`, `v0.2.0`, `v0.3.0`, `v0.4.0`)

---

### PR #72
```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   🔀  MERGE dev → main — 2026-05-28                                         ║
║   🏷️  v0.4.0 — Pipeline end-to-end opérationnel  (PRs #54 à #71)           ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║   Container App Job — offer-fetching                                         ║
║   ─────────────────────────────────────────────────────────────────────      ║
║   • PR #54  Migration offer-fetching GitHub Actions → Container App Job     ║
║   • PR #55/#56  Subnet CAE /23 (10.0.4.0/23, fix CIDR overlap)             ║
║   • PR #57/#58/#59  VNet injection CAE — infrastructure_subnet_id,          ║
║             prevent_destroy restauré, create_before_destroy retiré          ║
║   • PR #60  Network Contributor sur subnet_cae → sp-jf-github               ║
║                                                                              ║
║   Python — Pipeline fixes                                                    ║
║   ─────────────────────────────────────────────────────────────────────      ║
║   • PR #61  Fix alembic.ini path (__file__ au lieu de WORKDIR)              ║
║   • PR #62  Fix FT_SCOPE OAuth (api_offresdemploiv2 + o2dsoffre)            ║
║   • PR #63  Déduplication raw_offers avant upsert (CardinalityViolation)    ║
║   • PR #64  replica_timeout 300s → 3600s (embedding ~3000 offres)          ║
║   • PR #65  max_retries=10 sur AzureOpenAI client                           ║
║   • PR #66  capacity_tpm 10 → 1000 (10K → 1M TPM)                         ║
║   • PR #67  Batching embed() — BATCH_SIZE=100, sleep(1) inter-batch         ║
║   • PR #68  synchronize_session=None + retry 429 FT avec Retry-After        ║
║   • PR #69  ORM bulk UPDATE par PK (fix InvalidRequestError SQLAlchemy)     ║
║   • PR #70  Service Bus msg.body — b"".join() avant json.loads()            ║
║                                                                              ║
║   Documentation                                                              ║
║   ─────────────────────────────────────────────────────────────────────      ║
║   • PR #71  Mise à jour journal + tags versions sur tous les merges main     ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

### PR #73 — feat(lz): grant Service Bus Data Owner to UAMI for managed identity auth
**Date :** 2026-05-28

**Réalisé :**
- `lz_dev/rbac.tf` : ajout d'une data source `azurerm_servicebus_namespace "dev"` pointant sur `sb-jf-dev-frc` dans `module.rg_app.name`
- `lz_dev/rbac.tf` : ajout de `azurerm_role_assignment.caj_servicebus_owner` — rôle `Azure Service Bus Data Owner` assigné sur le namespace Service Bus pour l'UAMI `id-jf-dev-frc-caj`

**Décisions techniques :**
- `Azure Service Bus Data Owner` est le rôle minimal permettant à la fois le send (agents Python), le receive (agents Python) et le manage (KEDA scaler pour le déclenchement des Container App Jobs) via l'identité managée — sans connection string.
- Géré dans `lz_dev/rbac.tf` (par sp-jf-platform via CI/CD) : l'UAMI `id-jf-dev-frc-caj` est possédée par sp-jf-platform, et RBAC Administrator conditionné est requis pour assigner des rôles — sp-jf-github ne dispose pas de ce droit.
- Cette PR (lz_dev apply) doit être appliquée avant le merge de `feature/m3-sb-mi-app` : le role assignment doit exister sur Azure avant que les Container App Jobs tentent de s'authentifier via l'identité managée.

---

### PR #74 — feat(module): add workload identity support for KEDA Service Bus trigger
**Date :** 2026-05-28

**Réalisé :**
- `modules/container_app_job/variables.tf` : ajout de la variable `uami_client_id` (string nullable, défaut `null`) après `servicebus_namespace`
- `modules/container_app_job/main.tf` : dans le bloc `rules{}` du trigger queue KEDA, remplacement du `metadata` statique par un `merge()` conditionnant l'ajout de `clientId`, et remplacement du bloc `authentication{}` fixe par un `dynamic "authentication"` conditionné sur `var.uami_client_id == null`

**Décisions techniques :**
- Le `merge()` sur `metadata` et le `dynamic "authentication"` permettent les deux modes d'authentification sans briser les callers existants : si `uami_client_id` est `null`, le comportement est identique à l'ancien module (connection string via secret). Si `uami_client_id` est fourni, KEDA utilise la workload identity Azure — `clientId` est injecté dans les metadata KEDA et le bloc `authentication` est absent, conformément au protocole KEDA workload identity.
- Rétrocompatibilité totale : tous les callers existants (`job_matching`, `job_offer_fetching`) n'ont pas à être modifiés tant qu'ils ne passent pas `uami_client_id`.

---

### PR #75 — feat(dev): migrate Service Bus auth to Managed Identity + add openai_capacity_tpm variable
**Date :** 2026-05-28

**Réalisé :**

*Terraform / envs/dev*
- `container_apps.tf` — `job_matching` : suppression du secret `servicebus-connection-string` et de la variable d'environnement `AZURE_SERVICEBUS_CONNECTION_STRING` ; ajout de `AZURE_SERVICEBUS_FULLY_QUALIFIED_NAMESPACE` et `AZURE_CLIENT_ID` en plain-text ; ajout de `uami_client_id` pour le scaler KEDA
- `container_apps.tf` — `job_offer_fetching` : même suppression ; ajout de `AZURE_SERVICEBUS_FULLY_QUALIFIED_NAMESPACE` et `AZURE_CLIENT_ID` en plain-text (pas de `uami_client_id` — job timer, pas de KEDA queue auth)
- `container_apps.tf` — locals : suppression de `servicebus_connection_string`
- `servicebus.tf` : suppression du `module "secret_servicebus"` (connection string KV) ; commentaire explicatif ajouté
- `variables.tf` : ajout de `openai_capacity_tpm` (number, défaut 1000, validation > 0)
- `openai.tf` : les deux `capacity_tpm = 1000` remplacés par `var.openai_capacity_tpm`

*Python*
- `shared/bus.py` : migration de `ServiceBusClient.from_connection_string(AZURE_SERVICEBUS_CONNECTION_STRING)` vers `ServiceBusClient(fully_qualified_namespace=_namespace, credential=_credential)` avec `DefaultAzureCredential()`
- `requirements.txt` : ajout de `azure-identity`

**Décisions techniques :**
- `DefaultAzureCredential` lit `AZURE_CLIENT_ID` automatiquement pour sélectionner la bonne UAMI parmi celles attachées au Container App Job — aucun changement de code Python nécessaire pour passer le client ID.
- Le `module "secret_servicebus"` est retiré : la connection string n'a plus de consommateur. La stocker en KV sans l'utiliser crée un artefact trompeur.
- `openai_capacity_tpm` avec `default = 1000` : un apply Terraform sans `terraform.tfvars` ne peut plus remettre accidentellement la valeur à `10` (la valeur initiale du PR #23, corrigée manuellement ensuite).
- **Breaking change fonctionnel** : les agents ne démarreront plus si `AZURE_SERVICEBUS_FULLY_QUALIFIED_NAMESPACE` n'est pas injecté — la `ValueError` au démarrage du module remplace silencieusement l'ancienne connexion par string.

---

### PR #76 — chore: add westeurope to allowed locations policy
**Date :** 2026-05-28

**Réalisé :**
- `lz_dev/policies.tf` : ajout de `"westeurope"` dans la liste `allowed_locations` du module `policy_allowed_locations`

**Décisions techniques :**
- Microsoft Entra External ID (remplaçant d'Azure AD B2C) déploie son infrastructure interne en `westeurope`, indépendamment de la région de résidence des données sélectionnée à la création du tenant. La policy `Allowed locations` (mode `All`, scope subscription) bloquait la création avec un `RequestDisallowedByPolicy` sur la région `westeurope`.
- `westeurope` est ajouté aux côtés de `francecentral` et `northeurope` — les deux régions EU déjà autorisées pour les ressources Azure standard du projet.

---

### PR #TBD — chore: replace westeurope with europe in allowed locations for Entra External ID
**Date :** 2026-06-01

**Réalisé :**
- `lz_dev/policies.tf` : remplacement de `"westeurope"` par `"europe"` dans la liste `allowed_locations` du module `policy_allowed_locations`

**Décisions techniques :**
- L'Activity Log Azure révèle que la `resourceLocation` tentée lors de la création du tenant Entra External ID (`Microsoft.AzureActiveDirectory/ciamDirectories`) est `"europe"` — une valeur spéciale Azure pour les ressources d'identité multi-régions, distincte de `"westeurope"`.
- PR #76 avait ajouté `"westeurope"` comme hypothèse ; cette PR corrige le tir en remplaçant `"westeurope"` par la valeur exacte retournée par Azure, sans exemption inutile de toute la région standard westeurope.
