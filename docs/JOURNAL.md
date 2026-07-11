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

### PR #77 — chore: replace westeurope with europe in allowed locations for Entra External ID
**Date :** 2026-06-01

**Réalisé :**
- `lz_dev/policies.tf` : remplacement de `"westeurope"` par `"europe"` dans la liste `allowed_locations` du module `policy_allowed_locations`

**Décisions techniques :**
- L'Activity Log Azure révèle que la `resourceLocation` tentée lors de la création du tenant Entra External ID (`Microsoft.AzureActiveDirectory/ciamDirectories`) est `"europe"` — une valeur spéciale Azure pour les ressources d'identité multi-régions, distincte de `"westeurope"`.
- PR #76 avait ajouté `"westeurope"` comme hypothèse ; cette PR corrige le tir en remplaçant `"westeurope"` par la valeur exacte retournée par Azure, sans exemption inutile de toute la région standard westeurope.

---

### PR #78 — chore(m3): prepare repo for public visibility
**Date :** 2026-06-01

**Réalisé :**
- `docs/` : remplacement de toutes les références "Azure AD B2C" par "Microsoft Entra External ID" — alignement avec le renommage officiel Microsoft
- `.gitignore` : `docs/MANUAL_OPERATIONS.md` et `job-finder-private/` (repo git imbriqué pour les opérations sensibles) ajoutés à la liste d'exclusion ; `docs/MANUAL_OPERATIONS.md` désindexé via `git rm --cached`
- `JobFinder/powershell/setup-sp-jf-platform.ps1` et `setup-sp-jf-github.ps1` : `$subscriptionId` et `$tenantId` hardcodés remplacés par un bloc `param([Parameter(Mandatory)])` — les valeurs ne sont plus stockées dans le code source

**Décisions techniques :**
- Les scripts PowerShell contenaient des IDs Azure (subscription, tenant) en clair — un repo public les aurait exposés. Le bloc `param(Mandatory)` force l'appelant à les fournir explicitement à l'exécution.
- `MANUAL_OPERATIONS.md` contient des procédures opérationnelles sensibles (SPs, OIDC, rôles) : déplacé dans `job-finder-private/` et exclu du repo public.
- `job-finder-private/` est un repo git indépendant imbriqué dans `job-finder/` — le gitignore du repo parent l'exclut entièrement pour éviter tout commit accidentel de son contenu.

---

### PR #79 — feat: complete Entra External ID setup script
**Date :** 2026-06-01

**Réalisé :**
- `JobFinder/powershell/setup-entra-external-tenant.ps1` : script étendu pour couvrir toutes les opérations faites manuellement sur le portail — 9 sections au total :
  1. Tenant CIAM via ARM (`Microsoft.AzureActiveDirectory/ciamDirectories`)
  2. App Registration `fastapi-jobfinder` via `az ad app`
  3. Scopes built-in OpenID Connect (openid, profile, email)
  4. Client secret (`--append`, 2 ans)
  5. Scope custom `access_as_user` via Graph PATCH sur l'application
  6. User flow `susi` via Graph POST (`externalUsersSelfServiceSignUpEventsFlow`)
  7. Association `fastapi-jobfinder` ↔ user flow `susi`
  8. Google Identity Provider + ajout au user flow `susi`
  9. Résumé des 5 valeurs à stocker dans Key Vault
- Deux nouveaux paramètres obligatoires : `$googleClientId`, `$googleClientSecret`

**Décisions techniques :**
- Le tenant a été créé manuellement le 2026-06-01 via le portail Azure avant que ce script existait — le script documente et automatise la procédure pour une reconstruction depuis zéro
- La création de tenant CIAM est asynchrone côté Azure — `Start-Sleep -Seconds 10` suivi d'un GET de vérification pour lire le `tenantId` une fois la propagation terminée
- La section 2 (app registration) nécessite `az login --tenant $externalTenantId` : les commandes `az ad app` et tous les appels Graph suivants ciblent le tenant CIAM — un re-login interactif est requis pour basculer du tenant principal vers le tenant External ID
- `--resource https://graph.microsoft.com` sur tous les appels `az rest` Graph : explicite l'audience OAuth2 du token, nécessaire dans un tenant CIAM où l'audience par défaut pourrait différer
- `--append` sur `az ad app credential reset` : ajoute un secret sans invalider les secrets existants — une ré-exécution ne casse pas les déploiements en cours
- Mise à jour du user flow pour ajouter Google : GET du flow pour lire la liste courante des IdPs, puis PATCH avec la liste augmentée — évite d'écraser la config existante

---

### PR #80 — feat: FastAPI webapp — JWT auth, CV upload, matches, profile
**Date :** 2026-06-02

**Réalisé :**
- `agents/webapp/auth.py` : validation JWT Entra External ID avec python-jose — fetch JWKS avec TTL 24h + retry sur rotation de clé (`JWTError` → vider cache → re-fetch → réessayer une fois), décodage RS256, audience + issuer validés, retourne le claim `sub` ; `HTTPException 401` si token absent/invalide/expiré ; `load_dotenv()` appelé après tous les imports (convention CLAUDE.md)
- `agents/webapp/schemas.py` : modèles Pydantic — `ProfileUpdate` (sans `rome_codes` — readonly), `OfferOut` (avec `skills: list[str] = []` pour NULL ORM), `MatchOut`, `MatchesOut` (wrapper `{ rome_codes, matches }`), `ProfileOut` (`rome_codes` readonly), `CVUploadOut` (avec `blob_url`) ; `from_attributes=True` pour sérialisation ORM
- `agents/webapp/dependencies.py` : dépendance `get_db` — generateur FastAPI wrappant `get_session`
- `agents/webapp/routers/cv.py` : `POST /cv/upload` — validation `content_type` (422 si non-PDF) + taille max 10 MB (413) avant lecture ; upload PDF dans Azure Blob Storage (`cvs/{user_id}/{uuid}.pdf`, `overwrite=False`, client singleton module-level) → `blob_url` ; extraction texte pdfplumber ; embedding `shared/embedder.embed()` ; upsert CV avec `blob_url` (select-then-update-or-insert — absence de contrainte unique sur `user_id` intentionnelle, supporte plusieurs CVs par utilisateur) ; upsert UserProfile `ON CONFLICT DO NOTHING` ; déclenchement matching `offer-ready` (après commit, `ServiceBusError` logué sans faire échouer la requête) ; `AzureError` → 503
- `agents/webapp/routers/matches.py` : `GET /matches` → `MatchesOut { rome_codes, matches }` triés par score décroissant
- `agents/webapp/routers/profile.py` : `GET /profile` (404 si absent) + `PUT /profile` — upsert sur `job_categories`, `location`, `contract_types` uniquement ; `rome_codes` jamais touché
- `agents/webapp/main.py` : lifespan `run_migrations()` (fail-fast intentionnel) ; `AsyncGenerator[None, None]` comme type de retour ; 3 routers inclus
- `agents/webapp/requirements.txt` : fastapi, uvicorn, python-jose, pdfplumber, sqlalchemy, psycopg2-binary, pgvector, azure-servicebus, azure-identity, azure-storage-blob, openai, structlog, pydantic, requests
- `agents/webapp/Dockerfile` : build context `JobFinder/python/`, `uvicorn main:app --host 0.0.0.0 --port 8000`
- `migrations/versions/003_add_cvs_blob_url.py` : `ADD COLUMN blob_url VARCHAR NULL` sur `cvs`
- `shared/models.py` : `blob_url: Mapped[str | None]` ajouté sur `CV`

**Décisions techniques :**
- `rome_codes` géré exclusivement par l'agent GPT-4o-mini — absent de `ProfileUpdate` et du `set_{}` de `PUT /profile` ; exposé en lecture dans `ProfileOut` et `MatchesOut`. Un endpoint utilisateur ne doit jamais écraser une donnée produite par un agent IA.
- `MatchesOut { rome_codes, matches }` : rome_codes retournés une seule fois au niveau racine — évite la redondance et épargne un second appel `GET /profile` au frontend.
- JWKS TTL 24h + retry sur rotation : les clés Entra External ID changent rarement, mais une rotation dans la fenêtre TTL est couverte sans redémarrage du container.
- Blob upload après validation PDF et avant embedding : évite de stocker un fichier invalide et de gaspiller des tokens si le storage est hors service.
- `_blob_service_client` singleton module-level : évite de créer un nouveau `BlobServiceClient` (et une nouvelle credential) par requête.
- Absence de contrainte unique sur `cvs.user_id` intentionnelle : supporte plusieurs CVs par utilisateur (rôles différents). Race condition select-then-insert acceptée — le webapp tourne sur un seul replica pendant cette phase.
- `send_message` après `session.commit()` : le message n'est dispatché que si l'écriture DB a réussi. `ServiceBusError` logué sans faire échouer la requête — le cron de matching prendra le relai au prochain run.
- `agents/webapp/main.py` : commentaire inline sur `except Exception` dans `lifespan` pour documenter l'intention fail-fast ; `run_migrations()` enveloppé dans un `try/except Exception` avec `logger.error("migrations_failed", exc_info=True)` — même pattern appliqué aux trois agents (`offer_fetching`, `matching`, `cleanup`).
- `except Exception` intentionnel dans les 4 entrypoints : Alembic et SQLAlchemy peuvent lever des exceptions de types variés (`CommandError`, `OperationalError`, `ProgrammingError`…) — catcher la base garantit qu'aucune ne passe silencieusement.
- Terraform et CI/CD (Container App permanent, build Docker, secrets) feront l'objet de PRs séparées.

---

### PR #81 — feat: provision FastAPI webapp as Container App
**Date :** 2026-06-02

**Réalisé :**
- `modules/container_app/` : nouveau module Terraform réutilisable — `azurerm_container_app` avec ingress HTTP port 8000, `revision_mode = "Single"`, scale-to-zero (`min_replicas` configurable), `prevent_destroy = true`, tag `protect = "true"` ; blocs `dynamic` pour `env`, `secret`, `identity`, `registry`
- `envs/dev/webapp.tf` : déploiement de la webapp FastAPI dans le CAE existant — image ACR `agents/webapp:latest`, UAMI `id-jf-dev-frc-caj`, 9 variables d'environnement câblées (DATABASE_URL, AZURE_OPENAI_*, AZURE_SERVICEBUS_*, AZURE_CLIENT_ID, AZURE_STORAGE_ACCOUNT_URL, ENTRA_EXTERNAL_*) ; secrets Entra External ID lus depuis Key Vault via data sources
- `envs/dev/outputs.tf` : output `webapp_url` exposant le FQDN public du Container App
- `envs/dev/main.tf` : provider azurerm déjà déclaré — aucune modification

**Décisions techniques :**
- Module `container_app` distinct de `container_app_job` : un Container App est un service HTTP permanent (ingress, scaling horizontal) ; un Container App Job est une tâche ponctuelle (timer ou queue) — les deux ressources azurerm n'ont pas les mêmes attributs et ne partagent pas la même sémantique
- `module.storage.primary_blob_endpoint` utilisé directement pour `AZURE_STORAGE_ACCOUNT_URL` : l'output du module expose déjà l'URL blob complète — plus cohérent que créer un data source redondant sur une ressource déjà en state
- `data.azurerm_user_assigned_identity.caj` réutilisé depuis `container_apps.tf` : l'identité managée est partagée entre les Container App Jobs et la webapp — un seul objet IAM à gérer, une seule assignation AcrPull

---

### PR #82 — feat: add webapp to build and deploy pipeline
**Date :** 2026-06-02

**Réalisé :**
- `.github/workflows/buildAgents.yml` : ajout du step "Build and push webapp image" après offer-fetching, avec build context `JobFinder/python`, layer cache ACR `agents/webapp:cache` ; ajout de la ligne webapp dans le Build summary ; ajout de `az containerapp update` (pas `job update`) pour mettre à jour le Container App permanent après le push

**Décisions techniques :**
- `az containerapp update` vs `az containerapp job update` : la webapp est un Container App permanent (service HTTP), pas un Container App Job (tâche ponctuelle) — les deux commandes CLI sont distinctes et non interchangeables
- Même pattern tags `:latest` + `:<sha>` que les agents : `:latest` pour le déploiement Terraform initial, `:<sha>` pour la traçabilité et le rollback précis via la commande de mise à jour

---

### PR #83 — docs: update ADRs to Accepté and document AKS abandonment
**Date :** 2026-06-02

**Réalisé :**
- `docs/adr/ADR-*.md` : statut de tous les ADRs passé de "Proposé" à "Accepté" — les décisions sont implémentées et en production
- `docs/adr/ADR-002-compute-platform.md` : révision complète — décision mise à jour de AKS vers Container Apps définitif ; section "Pourquoi la migration AKS a été abandonnée en Milestone 3" ajoutée ; conséquences et actions réalisées mises à jour

**Décisions techniques :**
- Migration AKS abandonnée : Container Apps couvre l'ensemble des besoins (Container App Jobs pour les agents batch, Container App pour la webapp HTTP) sans la complexité et le coût d'AKS. La valeur portfolio est couverte par l'architecture multi-agents, KEDA, les identités managées et les modules Terraform.

---

### PR #84
```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   🔀  MERGE dev → main — 2026-06-02                                         ║
║   🏷️  v0.5.0 — Milestone 3 : webapp FastAPI + Entra External ID             ║
║         (PRs #73 à #83)                                                      ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║   Identité managée & Service Bus                                             ║
║   ─────────────────────────────────────────────────────────────────────      ║
║   • PR #73  Service Bus Data Owner → UAMI (lz_dev, sp-jf-platform)          ║
║   • PR #74  Module container_app_job — workload identity KEDA                ║
║   • PR #75  Migration auth Service Bus → Managed Identity (Python + TF)     ║
║                                                                              ║
║   Infrastructure réseau & gouvernance                                        ║
║   ─────────────────────────────────────────────────────────────────────      ║
║   • PR #76  westeurope ajouté à allowed locations (Entra External ID)       ║
║   • PR #77  westeurope → europe (resourceLocation réelle Azure)             ║
║                                                                              ║
║   Entra External ID                                                          ║
║   ─────────────────────────────────────────────────────────────────────      ║
║   • PR #78  Repo préparé pour visibilité publique (secrets retirés)         ║
║   • PR #79  Script PowerShell setup Entra External ID complet               ║
║             (tenant, app registration, scopes, user flow, Google IdP)       ║
║                                                                              ║
║   FastAPI Webapp — Python                                                    ║
║   ─────────────────────────────────────────────────────────────────────      ║
║   • PR #80  Webapp FastAPI — JWT Entra, POST /cv/upload (PDF + blob),       ║
║             GET /matches, GET+PUT /profile ; migration 003 blob_url          ║
║                                                                              ║
║   FastAPI Webapp — Infrastructure & CI/CD                                   ║
║   ─────────────────────────────────────────────────────────────────────      ║
║   • PR #81  Module container_app + déploiement Terraform dev                ║
║   • PR #82  buildAgents.yml — build webapp + az containerapp update         ║
║                                                                              ║
║   Documentation                                                              ║
║   ─────────────────────────────────────────────────────────────────────      ║
║   • PR #83  ADRs → Accepté ; ADR-002 révisé (AKS abandonné)                ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## PR #85 — docs: update backlog with M4 planning and PR roadmap

**Date :** 2026-06-02
**Branche :** `docs/m4-backlog-and-planning` → `dev`

### Ce qui a été fait

Préparation du Milestone 4 (frontend Next.js) et du Milestone 5 (monitoring + tests) via trois nouveaux ADRs et un backlog détaillé par PR.

**Nouveaux ADRs :**
- **ADR-015** — Framework frontend : Next.js 14 (App Router, TypeScript, Tailwind CSS, Framer Motion, MSAL). Choix justifié par la valeur portfolio et la cohérence avec l'infrastructure Container Apps existante.
- **ADR-016** — Stratégie de test : tests unitaires Python ciblés (pytest) sur la logique critique (cleanup, auth JWT, validation CV). Tests e2e différés à v1.1.0 pour tenir le délai v1.0.0.
- **ADR-017** — Monitoring et alerting : Application Insights + KQL + Azure Monitor Alerts. 6 alertes critiques définies (5xx, dead-letter, CPU PostgreSQL, quota OpenAI, agent fetch absent, disponibilité webapp).

**Backlog M4 — 9 PRs planifiées :**
1. Agent cv-analysis — extraction codes ROME depuis texte CV (GPT-4o-mini)
2. Infrastructure frontend — Container App Next.js + CI/CD
3. Frontend setup — projet Next.js + auth Entra External ID (MSAL)
4. Frontend — page upload CV avec animation Three.js
5. Frontend — bibliothèque de CV
6. Frontend — vue détail CV (placeholders cv-review)
7. Frontend — page profil utilisateur
8. Agent cv-review — analyse CV vs offres (forces/faiblesses/suggestions)
9. Frontend — brancher cv-review sur la vue détail CV

**Backlog M5 — 3 PRs planifiées :**
1. ADR-017 : Terraform — action group + 6 alertes + injection `APPLICATIONINSIGHTS_CONNECTION_STRING`
2. ADR-017 : Python — instrumentation azure-monitor-opentelemetry + `duration_seconds`
3. Tests unitaires Python (ADR-016)

---

## PR #86 — feat: add cv-analysis agent for ROME code extraction

**Date :** 2026-06-02
**Branche :** `feature/cv-analysis-agent` → `dev`

### Ce qui a été fait

Introduction de l'agent `cv-analysis` qui complète le pipeline d'upload CV : les codes ROME sont désormais extraits automatiquement depuis le texte brut du CV avant de déclencher le matching.

**Problème résolu :** `user_profiles.rome_codes` restait vide pour les nouveaux utilisateurs. Le job `offer-fetching` utilisait des codes ROME fallback hardcodés au lieu des vrais besoins du candidat.

**Nouveau flow :**
```
POST /cv/upload
  → extraction PDF + embedding + upsert cvs + profil par défaut
  → send_message("cv-analysis", {cv_id})          ← remplace offer-ready

job-jf-dev-frc-cv-analysis (queue: cv-analysis)   ← NOUVEAU
  → SELECT raw_text, user_id FROM cvs WHERE id = cv_id
  → GPT-4o-mini : extrait 3–5 codes ROME (JSON strict)
  → UPDATE user_profiles SET rome_codes = [...] WHERE user_id = ?
  → send_message("offer-ready", {rome_codes, trigger: "cv_analysis"})
```

**Décisions techniques :**
- Le message Service Bus ne transporte que `cv_id` (pas `user_id`, pas `raw_text`). L'agent lit `raw_text` et `user_id` depuis la table `cvs` en une seule requête — évite la limite 256 KB de Service Bus Standard et un round-trip blob inutile.
- `_get_cv_text` retourne `tuple[str, str]` (raw_text, user_id) depuis la même requête, pas deux SELECT.
- Validation des codes ROME par regex `^[A-Z]\d{4}$` — les codes invalides sont filtrés avec un warning plutôt qu'une erreur fatale.
- Le CV est tronqué à 8 000 caractères pour le prompt GPT-4o-mini (limite tokens raisonnable).
- Pas de `requirements.txt` par agent — l'image utilise le `requirements.txt` racine `JobFinder/python/` (build context partagé).

**Fichiers modifiés :**
- `agents/webapp/routers/cv.py` — `MATCHING_TRIGGER_QUEUE` → `CV_ANALYSIS_QUEUE`, message simplifié à `{cv_id}`, log renommé en `cv_upload_analysis_triggered`
- `agents/cv_analysis/main.py` — nouvel agent (consume cv-analysis → extrait ROME → update user_profiles → envoie offer-ready)
- `agents/cv_analysis/Dockerfile` — même pattern que les agents batch existants
- `envs/dev/servicebus.tf` — queue `cv-analysis` ajoutée
- `envs/dev/container_apps.tf` — module `job_cv_analysis` ajouté (queue trigger, image `agents/cv-analysis:latest`)
- `.github/workflows/buildAgents.yml` — step build/push `agents/cv-analysis` + `az containerapp job update`

---

## PR #87 — feat: add configurable CORS middleware to webapp API

**Date :** 2026-06-23
**Branche :** `feature/m4-webapp-cors` → `dev`

### Ce qui a été fait

Première étape du Milestone 4 (frontend Next.js) : autoriser le futur frontend à appeler l'API FastAPI depuis le navigateur. Jusqu'ici `agents/webapp/main.py` n'avait aucun middleware CORS — tout appel cross-origin était bloqué par le navigateur.

Ajout du middleware `CORSMiddleware` sur l'objet `app`, configuré de façon non-bloquante pour la webapp déjà déployée :
- Origines autorisées lues depuis la variable d'environnement `CORS_ALLOWED_ORIGINS` (chaîne séparée par des virgules), parsée au niveau module en `list[str]` (trim des espaces, entrées vides ignorées).
- Méthodes : `GET, POST, PUT, DELETE, OPTIONS`. En-têtes : `Authorization, Content-Type`.

### Décisions techniques

- **Deny-by-default non-bloquant :** si `CORS_ALLOWED_ORIGINS` est absente ou vide, la liste d'origines est vide (aucune origine autorisée → comportement actuel inchangé) et un `logger.warning("cors_no_allowed_origins_configured")` est émis. Aucune exception levée : la webapp démarre normalement. Pas de `["*"]` par défaut pour ne pas ouvrir l'API par accident.
- **`allow_credentials=False` :** l'authentification se fait par jeton Bearer dans l'en-tête `Authorization`, jamais par cookie. Inutile (et risqué) d'autoriser les credentials cross-origin.

### Vérification

App importée localement avec la stack webapp complète et un preflight `OPTIONS` via `TestClient` :
- Avec `CORS_ALLOWED_ORIGINS=http://localhost:3000` : preflight `200`, en-tête `Access-Control-Allow-Origin: http://localhost:3000` présent, méthodes et en-têtes corrects, pas d'`Access-Control-Allow-Credentials`.
- Sans la variable : warning loggé, app démarre, preflight rejeté (`400`, pas d'`Allow-Origin`), `/docs` reste accessible.

### Fichiers modifiés

- `agents/webapp/main.py` — constante `CORS_ALLOWED_ORIGINS` (parsing env), ajout du `CORSMiddleware` + warning si aucune origine configurée

---

## PR #88 — feat(frontend): scaffold Next.js project + fix(webapp): add alembic

**Date :** 2026-06-23
**Branche :** `feature/m4-frontend-scaffold` → `dev`

Premier pas du Milestone 4 (proposition A — *walking skeleton*) : initialisation du projet frontend Next.js, plus un correctif de dépendance backend repéré pendant la PR CORS. Deux commits atomiques distincts dans une seule PR.

### Commit 1 — `fix(webapp): add alembic to webapp requirements`

`shared/db.py` importe `alembic` au chargement du module, mais le Dockerfile de la webapp n'installe que `agents/webapp/requirements.txt` (qui ne le listait pas) → la webapp plantait au démarrage. Ajout de `alembic` (même spécification non-épinglée que le `requirements.txt` racine).

**Vérification :** dans un venv où seul `agents/webapp/requirements.txt` est installé, `python -c "import shared.db"` réussit (avec `DATABASE_URL` factice pour passer la validation au chargement).

### Commit 2 — `feat(frontend): scaffold Next.js project with MSAL auth`

Nouveau répertoire `JobFinder/frontend/` : Next.js 14 (App Router) + TypeScript + Tailwind CSS (cf. ADR-015), authentification Microsoft Entra External ID (CIAM) via `@azure/msal-browser` + `@azure/msal-react`, client HTTP `axios`.

**Périmètre — squelette d'auth uniquement.** Aucune UI métier (pas d'upload, pas de bibliothèque) : juste une page d'accueil avec un bouton de connexion/déconnexion qui distingue l'état connecté / non connecté.

**Décisions techniques :**
- Configuration MSAL entièrement lue depuis des variables d'environnement `NEXT_PUBLIC_*` — rien codé en dur. Une variable manquante lève une erreur explicite au chargement de `msalConfig.ts`. Toutes documentées dans `.env.local.example`.
- Instance MSAL partagée (`lib/auth/msalInstance.ts`) entre le `MsalProvider` (`AuthProvider`) et l'intercepteur axios, pour un cache de compte cohérent. `AuthProvider` attend `instance.initialize()` (requis par MSAL v3) avant de rendre ses enfants.
- L'intercepteur axios (`lib/api/client.ts`) acquiert le jeton via `acquireTokenSilent` (scope `NEXT_PUBLIC_ENTRA_API_SCOPE`) et l'injecte en `Authorization: Bearer …` ; repli sur `acquireTokenRedirect` si une interaction est requise.
- Dockerfile `node:20-alpine` (`npm ci` + `npm run build` + `npm start`, port 3000) ; `.dockerignore` exclut `node_modules`, `.next`, `.env*`.

**Limite connue :** le login n'est **pas** testable de bout en bout tant que l'app registration SPA (Entra External ID) et son redirect URI n'existent pas — c'est l'étape manuelle suivante. Le build, le lint et le serveur de dev ont été validés avec des valeurs `NEXT_PUBLIC_*` factices.

### Documentation

- `docs/adr/ADR-015-frontend-framework.md` — emplacement corrigé `frontend/` → `JobFinder/frontend/`.
- `docs/BACKLOG.md` (tests M5) — ajout de `tests/test_cors.py` (scénarios preflight origine présente/absente), follow-up identifié par le reviewer de la PR #87.

### Correctif post-scaffold — `fix(frontend): reference NEXT_PUBLIC_* env vars statically`

La page plantait au chargement navigateur (« Missing required environment variable: NEXT_PUBLIC_ENTRA_CLIENT_ID ») alors que `.env.local` était correct et chargé côté serveur. Cause : `msalConfig.ts` lisait les variables via un accès dynamique (`process.env[name]`). Next.js n'inline les `NEXT_PUBLIC_*` dans le bundle **client** que si elles sont référencées **statiquement** (`process.env.NEXT_PUBLIC_FOO`) → en accès dynamique, valeurs `undefined` côté navigateur (OK côté serveur).

Correctif : `requireEnv(name, value)` reçoit désormais la valeur lue statiquement ; la validation est conservée. Vérifié dans un vrai navigateur (Edge headless) : la page affiche le titre + le bouton « Se connecter », sans erreur de page dans la console.

### Correctif — `fix(frontend): surface MSAL initialization failures instead of blank screen`

`AuthProvider` appelait `msalInstance.initialize().then(...)` sans `.catch()` : en cas d'échec d'initialisation (ex. autorité malformée), la promesse était avalée, `isReady` restait `false` et la page restait blanche, sans aucun message. Ajout d'un `.catch()` qui logge l'erreur, stocke un état `initError` et affiche un message visible (`role="alert"`) à la place de `null`. Objectif : ne plus jamais avoir d'écran blanc silencieux en cas de mauvaise configuration MSAL.

### Investigation — resync `next` / `@next/swc` (aucun changement)

Un resync de version `next` était envisagé car le lockfile montrait `next`/`@next/env` en `14.2.35` et les binaires `@next/swc-*` en `14.2.33`. Vérification faite : ce n'est **pas** une incohérence. `next@14.2.35` épingle lui-même ses `optionalDependencies` `@next/swc-*` à `14.2.33`, et `@next/swc-*@14.2.35` n'existe pas sur le registre npm (les binaires SWC n'ont pas été rebâtis pour les patchs 14.2.34/35). La résolution actuelle est donc correcte et la seule possible — aucun changement de dépendance n'a été apporté.

---

## PR #89 — feat: add SPA app registration to Entra External ID setup script

**Date :** 2026-06-23
**Branche :** `feature/m4-spa-app-registration` → `dev`

### Ce qui a été fait

Le scaffold frontend (PR #88) est en place mais le login MSAL ne fonctionnait pas : il manquait l'app registration SPA dans le tenant Entra External ID `jobfinderapp`. Ajout de cette carte applicative au script manuel `JobFinder/powershell/setup-entra-external-tenant.ps1`, dans le même style idempotent que les sections existantes.

**Décision actée :** carte SPA dédiée (`spa-jobfinder`), distincte de l'API `fastapi-jobfinder` — séparation client public (navigateur) / API protégée.

**Nouvelles sections du script (9 à 12, résumé renuméroté en 13) :**
- **9.** App registration SPA `spa-jobfinder` — client public, **sans client secret** (`AzureADMyOrg`).
- **10.** Plateforme SPA — redirect URIs enregistrées dans la propriété `spa` (et non `web`) : c'est ce qui active le flux **Authorization Code + PKCE** attendu par MSAL. Paramétrables via le nouveau paramètre `$spaRedirectUris` (défaut `@("http://localhost:3000")`), ajout additif pour pouvoir ajouter l'URL du Container App plus tard sans modifier le script.
- **11.** Permission API déléguée — référence à `fastapi-jobfinder` (son `appId`) + l'id du scope `access_as_user` (réutilisé depuis la section 5, **non recréé**, type `Scope`).
- **12.** Association `spa-jobfinder` ↔ user flow `susi` (même pattern que la section 7) → la SPA hérite d'Email + Google.

**Résumé (section 13) :** ajout du bloc de valeurs exactes à coller dans `JobFinder/frontend/.env.local` (`NEXT_PUBLIC_ENTRA_CLIENT_ID`, `NEXT_PUBLIC_ENTRA_AUTHORITY`, `NEXT_PUBLIC_ENTRA_KNOWN_AUTHORITY`, `NEXT_PUBLIC_ENTRA_API_SCOPE`, `NEXT_PUBLIC_REDIRECT_URI`), plus la commande d'exécution et le rappel qu'un `az login` interactif sur le tenant CIAM est requis.

**Décisions techniques :**
- Aucun client secret pour la SPA (client public PKCE).
- Redirect URIs dans `spa.redirectUris` via PATCH Graph, pas dans `web`.
- JSON des tableaux (`redirectUris`, `requiredResourceAccess`) construit manuellement : `ConvertTo-Json` désérialise un tableau mono-élément en scalaire sous PowerShell 5.1, ce que Graph rejette.
- Idempotence : re-run détecte tout l'existant (app, redirect URIs, permission, association) et ne crée que la SPA si absente. Vérifié par parsing PowerShell (aucune erreur de syntaxe). Application manuelle par l'utilisateur, hors CI/CD.

### Raffinements post-revue (non bloquants)

Suite à la revue du reviewer, sur la même PR :
- **Section 11 — `requiredResourceAccess` additif.** Le PATCH écrasait tout le tableau (il ne posait que l'entrée `fastapi-jobfinder`). Remplacé par un patron lire-fusionner-écrire (même logique additive que les redirect URIs en section 10) : GET de la SPA, fusion du scope `access_as_user` dans l'entrée `fastapi-jobfinder` existante (ou ajout d'une nouvelle entrée), sans supprimer d'autres permissions ni dupliquer. Motivation : ne pas effacer une future 2e permission (ex. microservice de facturation).
- **Nettoyage `$tmpFile`.** Les blocs de fichier temporaire des sections 10/11/12 sont désormais en `try { … } finally { Remove-Item }` — suppression garantie même si `az rest` échoue.
- **Commentaires.** Section 12 : explication de l'usage volontaire de `ConvertTo-Json` (objet simple, pas un tableau, contrairement aux sections 10/11). Section 13 : précision que seule la 1re redirect URI (localhost dev) est reprise dans le hint, les autres restant enregistrées.
- **`$externalTenantId` :** vérifié défini dans tous les chemins de la section 1 avant le résumé (section 13) — aucun correctif nécessaire.
### Correctif — incident tenant Entra en double (détection + polling)

Lors d'une exécution réelle, le script a **créé un second tenant Entra External ID en double**, alors que le tenant correct (`jobfinderapp.onmicrosoft.com`, dans `rg-jf-dev-frc-core`) existait déjà. Deux bugs cumulés en section 1 :

1. **Détection erronée du tenant.** Le nom de ressource ARM était construit depuis `$domainName = "jobfinderapp"` (`GET .../ciamDirectories/jobfinderapp`), alors que le vrai nom est `jobfinderapp.onmicrosoft.com` (Azure ajoute le suffixe du domaine initial) → 404 → le script concluait « le tenant n'existe pas » et entrait dans la branche création, dupliquant le tenant.
2. **Polling acceptant le GUID vide.** La boucle de polling acceptait `properties.tenantId` même quand il valait `00000000-0000-0000-0000-000000000000` (valeur renvoyée pendant le provisioning), enregistrant un tenantId invalide.

**Corrections :**
1. **Détection robuste par listing.** On LISTE les `ciamDirectories` du resource group et on retrouve l'existant en matchant sur `properties.domainName == "$domainName.onmicrosoft.com"`. La branche création n'est atteinte que si aucune ressource ne correspond — fini la dépendance à un nom de ressource supposé. `$domainName` reste `"jobfinderapp"` pour l'autorité ciamlogin ; seule la résolution ARM utilise le suffixe `.onmicrosoft.com` (variable `$ciamDomain`).
2. **Polling rejetant le GUID tout-à-zéro.** Le GUID tout-à-zéro est traité comme « pas prêt » ; le polling (re-list + match) continue jusqu'à un vrai GUID, avec échec explicite (`exit 1`) si `maxAttempts` est atteint. Un tenant déjà prêt est résolu dès la 1re itération.

**Backlog :** item de durcissement ajouté (`docs/BACKLOG.md`, section Sécurité) : écrire les secrets sensibles (client secret Entra, secret Google) directement dans Key Vault via `az keyvault secret set` plutôt que de les afficher en console.

**Vérification :** logique vérifiée statiquement (pas d'accès Azure depuis l'environnement) — parsing PowerShell sans erreur ; une ré-exécution détecte le tenant `jobfinderapp.onmicrosoft.com` existant via le listing et **n'entre pas** dans la branche création.

### Correctifs reproductibilité — défauts constatés sur run réel (Défauts 1, 2a, 2b, 3)

Lors du premier run complet après les corrections du tenant, trois catégories de défauts ont empêché le script de terminer proprement :

**Défaut 1 — Faux succès sur les appels Graph (`az rest` ne lève pas d'exception sur erreur)**

`az rest` retourne `$LASTEXITCODE = 0` (ou absorbe les erreurs) même quand un appel Graph échoue avec un 4xx, rendant le diagnostic impossible et masquant les échecs réels sous des messages de succès. Correctif : introduction de la fonction `Invoke-GraphRequest` dans `setup-entra-external-tenant.ps1`. La fonction capture stderr dans un fichier temporaire, contrôle `$LASTEXITCODE`, vérifie la présence de `.error` ou `.@odata.error` dans la réponse JSON, et lève une exception PowerShell avec le message d'erreur complet. Tous les appels Graph des sections 5 à 12 passent désormais par cette fonction ; les appels ARM de la section 1 (management.azure.com) sont inchangés.

**Défaut 2a — Association app ↔ user flow rejetée (`"application id is invalid"`)**

Les POST sur `includeApplications` (sections 7 et 12) échouaient silencieusement. L'API Graph exige `@odata.type = "#microsoft.graph.authenticationConditionApplication"` dans le body — sans ce champ, même avec un `appId` correct, la requête est rejetée. Correctif : ajout du champ dans les sections 7 et 12 ; commentaire explicatif ajouté.

**Défaut 2b — Absence de service principal pour les apps créées**

`az ad app create` (CLI 2.x) ne crée **pas** automatiquement le service principal correspondant. L'association d'une app au user flow nécessite l'existence du SP. Correctif : ajout d'un bloc idempotent `az ad sp list / az ad sp create` après chaque `az ad app create`, dans les sections 2 et 9. Le bloc est **séparé** de la création de l'app (pas dans le `else`) pour garantir l'existence du SP même si l'app existait déjà sans SP lors d'un re-run.

**Défaut 3 — Token Azure CLI sans les permissions Graph nécessaires**

`az login --tenant $externalTenantId` ne procure pas les permissions `IdentityProvider.ReadWrite.All` et `EventListener.ReadWrite.All` dans le token, qui sont absentes du jeu de scopes par défaut du CLI sur un tenant CIAM. Correctif en deux parties :

1. **Nouveau script `JobFinder/powershell/setup-sp-jf-ciam-setup.ps1`** (bootstrap, idempotent) : crée le SP `sp-jf-ciam-setup` dans le tenant CIAM, lui assigne les 3 permissions Graph applicatives (`Application.ReadWrite.All`, `IdentityProvider.ReadWrite.All`, `EventListener.ReadWrite.All`) via `POST /servicePrincipals/{id}/appRoleAssignments` (admin consent programmatique, ou fail-fast avec instructions portail si le token ne dispose pas de `AppRoleAssignment.ReadWrite.All`), génère un client secret et l'écrit dans `kv-jf-dev-frc` (`ciam-setup-sp-client-id` et `ciam-setup-sp-secret`) — jamais affiché en console. Idempotent : re-run détecte l'app, le SP, les assignations existantes et le secret KV, et ne recrée que ce qui manque.

2. **Section 1-bis dans `setup-entra-external-tenant.ps1`** : lit les credentials de `sp-jf-ciam-setup` depuis `kv-jf-dev-frc` (fail-fast si absents avec instructions de bootstrap) et effectue `az login --service-principal` avant les sections 2–12. Le login interactif `az login --tenant` est supprimé.

**Décision architecturale :** le secret du SP de setup n'est jamais affiché en console — il rejoint `kv-jf-dev-frc` dès sa génération, cohérent avec le backlog item "écrire les secrets dans Key Vault" déjà tracé.

**Vérification :** parsing PowerShell sans erreur ; seul un run réel par l'utilisateur (sans aucun faux succès) validera ces corrections.

### Finalisation auth frontend — affichage identité

Après investigation du `server_error` AADSTS40015 (erreur Entra ↔ Google IDP, cause externe au frontend), dernière itération sur `LoginButton.tsx` :

- **Priorité d'affichage :** `preferred_username` (email, claim le plus fiable dans un tenant CIAM) → `name` si présent et différent de `"unknown"` → `"Connecté"`.
- **Lecture des claims :** `accounts[0]?.idTokenClaims` casté en `Record<string, unknown>`, lecture explicite de `preferred_username` et `name`.
- **Instrumentation de diagnostic retirée :** `console.log("[MSAL] claims")` (LoginButton), `console.error("[MSAL] auth failure")` (AuthProvider event callback), `LogLevel.Verbose` + `loggerCallback` (msalConfig → remis en `LogLevel.Warning` + no-op).
- `npm run build` passe (TypeScript + lint) après nettoyage du cache `.next`.

### Retours reviewer non bloquants (suite)

- **Polling break** : boucle de détection du tenant restructurée avec `break` explicite sur ID valide — `Start-Sleep` devient le chemin de fall-through (jamais atteint si le tenant existe déjà), éliminant l'attente inutile de 10s sur tenant existant.
- **Null guard `$spaAppObjId`** : garde ajouté après `az ad app create` en section 9 — fail-fast explicite si la création ne retourne pas d'ID (même style que le garde `$flowId` en section 6).
- **Commentaire `NEXT_PUBLIC_ENTRA_KNOWN_AUTHORITY`** : précise que `knownAuthorities` dans MSAL attend un nom d'hôte brut (sans `https://`).
- **Backlog** : item ajouté — extraire `Invoke-GraphRequest` dans `graph-utils.ps1` (dot-sourcing) à partir d'un 3ᵉ script Graph.

---

## PR #90 — fix(webapp): add python-multipart to webapp requirements

**Date :** 2026-06-24
**Branche :** `fix/webapp-python-multipart` → `dev`

### Ce qui s'est passé

Crash-loop confirmé sur `app-jf-dev-frc` après le merge de PR #89 :

```
RuntimeError: Form data requires "python-multipart" to be installed.
```

FastAPI exige `python-multipart` pour parser les corps `multipart/form-data` (`UploadFile` dans `POST /cv/upload`). La dépendance manquait dans `agents/webapp/requirements.txt` → crash à l'import, uvicorn ne démarre pas (exit code 1).

### Correctif

Ajout de `python-multipart` dans `agents/webapp/requirements.txt`. Le rebuild de l'image via `buildAgents.yml` et le redéploiement via `az containerapp update` restaurent le démarrage normal d'uvicorn.

### Audit

`alembic` (PR #88) puis `python-multipart` (PR #90) ont manqué successivement, causant deux crash-loops consécutifs. Pattern identifié : sans lockfile, les dépendances implicites de FastAPI ne sont pas visibles et doivent être découvertes par un crash en prod. Item backlog « pip-compile / lock des dépendances webapp » renforcé en `[urgent]` avec description complète de la solution (`requirements.in` + `pip-compile`).

---

## PR #91 — fix(webapp): copy migrations/ into webapp Docker image

**Date :** 2026-06-24
**Branche :** `fix/webapp-dockerfile-copy-migrations` → `dev`

### Ce qui s'est passé

3e crash-loop consécutif sur `app-jf-dev-frc` après le merge de PR #90 :

```
alembic.util.exc.CommandError: No 'script_location' key found in configuration.
```

`shared/db.py` charge `/app/migrations/alembic.ini` au démarrage pour exécuter `alembic upgrade head`. Le fichier était absent de l'image webapp : `agents/webapp/Dockerfile` ne copiait que `agents/webapp/` et `shared/` — pas `migrations/`. Les Dockerfiles des agents batch utilisent `COPY . .` depuis le build context `JobFinder/python/`, ce qui inclut `migrations/` automatiquement ; le Dockerfile webapp était plus sélectif et avait oublié ce répertoire.

### Correctif

Ajout dans `agents/webapp/Dockerfile` :

```dockerfile
COPY migrations/ ./migrations/
```

### Audit — 3 manques successifs

`alembic` (requirements.txt, PR #88) → `python-multipart` (requirements.txt, PR #90) → `migrations/` (Dockerfile, PR #91) : le build webapp n'avait jamais été validé par un vrai démarrage. Item backlog renforcé avec deux solutions complémentaires : `pip-compile` pour les dépendances, smoke-test d'import dans `buildAgents.yml` pour détecter les erreurs avant le push vers ACR.

---

## PR #92 — feat(infra): set CORS_ALLOWED_ORIGINS on webapp Container App

**Date :** 2026-06-24
**Branche :** `feature/m4-webapp-cors-origins` → `dev`

### Ce qui a été fait

Ajout de la variable d'environnement `CORS_ALLOWED_ORIGINS=http://localhost:3000` sur la webapp Container App dans `envs/dev/webapp.tf`. Le middleware `CORSMiddleware` ajouté en PR #87 lit cette variable pour autoriser les requêtes cross-origin — sans elle, tout appel depuis le frontend local vers l'API déployée était bloqué par le navigateur.

### Décisions techniques

- Valeur plain-text (pas un secret) : les origines CORS sont semi-publiques, visibles dans les headers de réponse HTTP.
- `http://localhost:3000` uniquement pour l'instant — l'URL du Container App frontend s'ajoutera ici (séparée par une virgule) lors du déploiement du frontend (M4 PR #2).
- Commentaire en place dans `webapp.tf` pour rappeler l'action à faire lors du déploiement frontend.

---

## PR #93 — fix(webapp): fix JWT issuer — use tenant GUID subdomain

**Date :** 2026-06-24
**Branche :** `fix/webapp-jwt-issuer` → `dev`

### Ce qui s'est passé

Tous les endpoints authentifiés retournaient 401 "Invalid token claims". Diagnostic via le header `Authorization` de la première requête réelle (`GET /profile`) : le token était bien envoyé, l'audience (`aud`) était correcte, mais l'issuer ne correspondait pas.

- **Token `iss` (réel) :** `https://067e6a3a-2b6f-41ad-96fb-0785f1ba73bc.ciamlogin.com/067e6a3a-2b6f-41ad-96fb-0785f1ba73bc/v2.0`
- **`ISSUER` attendu par le backend :** `https://jobfinderapp.ciamlogin.com/067e6a3a-2b6f-41ad-96fb-0785f1ba73bc/v2.0`

Entra External ID (CIAM) émet les tokens avec le GUID du tenant comme sous-domaine (`{tenant_id}.ciamlogin.com`) quel que soit le domaine custom utilisé pour l'authentification (`jobfinderapp.ciamlogin.com`). La constante `ISSUER` dans `auth.py` était hardcodée sur le domaine custom → `JWTClaimsError` sur chaque requête authentifiée.

### Correctif

```python
# auth.py — avant
ISSUER = f"https://jobfinderapp.ciamlogin.com/{ENTRA_EXTERNAL_TENANT_ID}/v2.0"
# après
ISSUER = f"https://{ENTRA_EXTERNAL_TENANT_ID}.ciamlogin.com/{ENTRA_EXTERNAL_TENANT_ID}/v2.0"
```

---

## PR #94 — feat(frontend): profile page — GET/PUT /profile, auth guard, ROME chips

**Date :** 2026-06-24
**Branche :** `feature/m4-profile-page` → `dev`

### Ce qui a été fait

Implémentation de la page profil (`app/profile/page.tsx`) et mise à jour de la page d'accueil (`app/page.tsx`).

**Page profil (`/profile`) :**
- Garde d'auth : si non authentifié, message + bouton de connexion (`loginRedirect`).
- Chargement : `GET /profile` via `apiClient` (Bearer token injecté par l'intercepteur axios). Cas 404 → formulaire vide (le `PUT /profile` est un upsert).
- Formulaire : `location` (texte libre), `contract_types` (cases à cocher : CDI, CDD, Freelance, Stage, Alternance), `job_categories` (tag input, Entrée ou virgule pour ajouter).
- `rome_codes` : chips en lecture seule, affichés uniquement si non vides (gérés par l'agent CV).
- Sauvegarde : `PUT /profile` avec `{ location, contract_types, job_categories }` — `rome_codes` absent intentionnellement.
- Feedback inline succès / erreur après sauvegarde.

**Page d'accueil :**
- Lien « Mon profil → » vers `/profile` affiché uniquement quand authentifié.

### Décisions techniques

- `rome_codes` masqué si vide — pas de section vide avant le premier upload de CV.
- 404 silencieux : formulaire vide est l'état initial attendu pour un nouvel utilisateur.
- `location.trim() || null` : chaîne vide normalisée en `null` (correspond au type `str | None` du schéma Pydantic).
- Ce PR a nécessité le fix préalable PR #93 (issuer JWT CIAM).

---

## PR #95 — chore: conventions Next.js + lockfile pip-compile webapp

**Date :** 2026-06-25
**Branche :** `chore/frontend-conventions-and-pip-compile` → `dev`

### Ce qui a été fait

**Frontend — application des conventions Next.js (CLAUDE.md) :**
- `lib/utils.ts` : utilitaire `cn()` (clsx + tailwind-merge) pour les classes Tailwind conditionnelles.
- `lib/api/types.ts` : source unique des types API — `ProfileData` extrait de `profile/page.tsx`.
- `app/layout.tsx` : police Inter via `next/font/google` (supprime tout chargement externe de font).
- `next.config.mjs` : `output: "standalone"` (requis pour le déploiement Container App) + `images.remotePatterns: []` (à compléter au déploiement).
- `app/profile/page.tsx` : import `ProfileData` depuis `lib/api/types`, usage de `cn()` sur la classe feedback, `focus-visible` sur les 4 boutons interactifs.
- `components/LoginButton.tsx` : `focus-visible` sur les boutons login/logout.
- `package.json` : ajout des dépendances `clsx` et `tailwind-merge`.

**Python webapp — lockfile pip-compile :**
- `agents/webapp/requirements.in` : fichier source (dépendances directes, non épinglées).
- `agents/webapp/requirements.txt` : lockfile généré par `pip-compile`, toutes les dépendances transitives épinglées — inclut `alembic==1.18.4` et `python-multipart==0.0.32`, causes des 3 crashs prod antérieurs.

**CI — smoke-test avant push ACR :**
- `buildAgents.yml` : le step "Build and push webapp image" est découpé en 3 : build local (load), smoke-test d'import (`python -c "import main"`), puis push ACR. Interrompt le workflow avant tout push si une dépendance manque ou lève une exception à l'import.

### Décisions techniques

- `output: "standalone"` dans `next.config.mjs` : requis pour l'image Docker Next.js multi-stage (backlog infra frontend).
- Focus sur `focus-visible:` (non `focus:`) : styles focus uniquement au clavier, pas au clic souris — meilleure UX + conformité WCAG.
- Les inputs existants (`focus:ring-2 focus:ring-blue-400`) sont exemptés de la migration `focus-visible` — ils ont déjà des styles focus explicites, les changer serait du churn non requis.
- Smoke-test avec des valeurs fictives (`postgresql://x:x@localhost/x`) : suffisant pour valider que tous les modules s'importent sans `ValueError`. La connexion réelle n'est pas testée — ce n'est pas le but du smoke-test.
- `annotated-doc==0.0.4` dans le lockfile : dépendance directe de `fastapi==0.138.0` (vérifiée dans les métadonnées du wheel).

---

## PR #96 — feat(frontend): upload page with 2D canvas orbit animation

**Date :** 2026-06-25
**Branche :** `feature/m4-upload-page` → `dev`

### Ce qui a été fait

Remplacement du walking skeleton (`app/page.tsx`) par la page d'upload CV finale.

**Composants créés :**
- `app/_components/OrbitAnimation.tsx` : canvas 2D plein écran. 220 particules ambiantes (mouvement brownien), 60 particules orbitales (ellipses indépendantes avec simulation de profondeur). Machine à états `idle | uploaded | done` : convergence des orbites vers le centre sur `uploaded`, glissement du document avec bump-up + chute accélérée sur `done`. Thumbnail PDF rendu via pdfjs-dist v3 (`OffscreenCanvas` → data URL) à la sélection du fichier. Particules avec `birthDelay` aléatoire (1–2 s, ease-out quadratique). Hover/click interactif (glow, scale, ripple) via refs partagées — aucun re-render.
- `app/_components/UploadSection.tsx` : drag-and-drop + clic restreint à la zone icône. Upload HTTP fire-and-forget ; animation découplée du réseau (déclenchée par `onThumbnailReady`). `onDoneComplete` auto-reset vers `idle` après l'animation. AuthButton en haut à droite.
- `app/_components/HomeClient.tsx` : wrapper client partagé UploadSection + bibliothèque. Scroll-snap mandatory `h-dvh` entre les deux sections.
- `app/_components/AuthButton.tsx` : bouton "Se connecter" (non authentifié) ou pill prénom + initiales avec dropdown profil / déconnexion (lucide-react, fermeture au clic extérieur).
- `app/page.tsx` : Server Component, `dynamic(ssr:false)` sur `HomeClient`.
- `public/logos/france-travail.svg` + `public/pdf.worker.min.js` : texture FT et worker pdfjs.

### Décisions techniques

- **Canvas 2D** (pas Three.js) : plus léger, SSR-safe sans `ssr: false` sur le canvas, meilleur contrôle fin des animations 2D type "particules orbitales".
- **State machine `idle | uploaded | done`** : `uploaded` apparaît immédiatement à la sélection du fichier (thumbnail visible) ; `done` déclenché par la fin du rendu PDF.js (pas par le réseau) — zéro indicateur de chargement sur la page d'accueil.
- **pdfjs-dist v3** : v4/v6 échouent silencieusement dans Next.js (worker ESM). v3 utilise un worker `.js` classique servi depuis `/public`.
- **Click restreint à ±28×34px autour du centre** : le div overlay couvre tout l'écran pour le drag-and-drop, mais le click ne s'active qu'au-dessus de l'icône (vérification des coordonnées dans le handler).
- **Scroll-snap mandatory** : `<main>` avec `h-dvh snap-y snap-mandatory` — une section = un "snap point", transition instantanée entre accueil et bibliothèque.
- **Bibliothèque** : miniature PDF grisée visible immédiatement après l'animation (data URL issu de pdfjs + `grayscale` CSS), spinner superposé pendant l'analyse backend.
- **`/library` route** : non encore implémentée (backlog M4-PR5) — la bibliothèque est une section dans la même page via scroll-snap.

---

## PR #97 — fix(lz_dev): add Storage Blob Data Contributor role for UAMI caj

**Date :** 2026-06-25
**Branche :** `fix/blob-rbac-caj-uami` → `dev`

### Ce qui a été fait

Ajout du role assignment `Storage Blob Data Contributor` sur `rg_data` pour la UAMI `id-jf-dev-frc-caj` dans `lz_dev/rbac.tf`.

### Contexte

`POST /cv/upload` retournait systématiquement 503. Les logs Container App révèlent :
`ErrorCode: AuthorizationPermissionMismatch` — la webapp utilise `DefaultAzureCredential` (UAMI via `AZURE_CLIENT_ID`) pour écrire dans le blob container `cvs`, mais la UAMI n'avait aucun rôle data-plane sur le Storage Account. L'upload échouait à chaque tentative.

### Décision technique

Scope à `rg_data` (resource group) plutôt qu'au storage account ou container : cohérent avec le pattern existant (`sp-jf-github` a déjà `Storage Blob Data Contributor` sur `rg_data`). Un seul storage account existe dans ce RG en dev.

---

## PR #98 — feat: library section with CV status tracking

**Date :** 2026-06-25
**Branche :** `feature/library` → `dev`

### Ce qui a été fait

Suivi du statut d'analyse de bout en bout (backend → agent → frontend) et page bibliothèque réelle.

**Backend — modèle et migration :**
- `shared/models.py` : deux nouveaux champs sur `CV` — `name` (String, nullable) et `status` (String, non-null, default `"pending"`).
- Migration `005` : `ADD COLUMN name`, `ADD COLUMN status` avec `server_default='pending'` pour les lignes existantes.

**Backend — endpoints :**
- `POST /cv/upload` : stocke `file.filename` dans `CV.name` et réinitialise `status='pending'` à chaque upload.
- `GET /cv/` : nouveau endpoint — liste tous les CVs de l'utilisateur authentifié avec le nombre de matches (LEFT JOIN subquery), ordonnés par `uploaded_at` desc.
- `schemas.py` : ajout de `CVListItemOut`.

**Agent cv-analysis :**
- Nouvelle fonction `_set_cv_status(cv_id, status)` (update SQL, catch `SQLAlchemyError`).
- `main()` : `"processing"` à la réception, `"error"` en cas d'exception, `"done"` avant l'envoi du message `offer-ready`.

**Frontend :**
- `lib/api/types.ts` : `CVStatus` (union type) + `CVData` interface.
- `CVCard.tsx` : carte CV avec trois états visuels (pending/processing → spinner, done → match count, error → badge rouge).
- `LibrarySection.tsx` : fetche `GET /cv/` au mount, poll toutes les 3 s si des CVs sont en cours. `fetchCvs` stabilisé avec `useCallback`, `clearInterval` dans le return du `useEffect`.
- `HomeClient.tsx` : simplifié — remplace le placeholder inline par `<LibrarySection />` qui gère ses propres données.

### Décisions techniques

- Polling côté frontend (3 s) plutôt que WebSocket : cohérent avec l'architecture Container App Jobs existante, implémentation simple, charge minimale.
- `LibrarySection` owns its data — `onReadyForLibrary` prop supprimée de `HomeClient`, pas de prop drilling.
- `h-dvh snap-start` sur `LibrarySection` : maintient le scroll-snap avec la section upload.

---

## PR #99 — fix: gate onThumbnailReady behind !cancelled to prevent double animation

**Date :** 2026-06-25
**Branche :** `fix/double-animation-strict-mode` → `dev`

### Ce qui a été fait

Correction dans `OrbitAnimation.tsx` : le callback `onThumbnailReadyRef.current?.()` est désormais conditionnel à `!cancelled`, aussi bien dans le chemin succès que dans le chemin `catch`.

### Contexte

React StrictMode monte, démonte et remonte les composants en développement. L'`useEffect` pdfjs s'exécutait donc deux fois :
- Premier passage : le cleanup posait `cancelled = true` → `onThumbnailReady(null)` → `setAnimState('done')` → animation slide.
- Second passage : pdfjs rendait le PDF avec succès → `onThumbnailReady(dataUrl)` → `setAnimState('done')` → animation se rejouait.

### Décision technique

Déplacer `onThumbnailReadyRef.current?.()` à l'intérieur du bloc `if (!cancelled)`. Solution minimale — aucun autre changement.

---

## PR #100 — fix(webapp): always INSERT on CV upload — support multiple CVs per user

**Date :** 2026-06-25
**Branche :** `fix/cv-upload-always-insert` → `dev`

### Ce qui a été fait

**Backend (`routers/cv.py`) :**
- Remplacement de la logique select-then-upsert par un simple `INSERT`. Chaque upload crée une nouvelle ligne CV distincte, visible comme une carte séparée dans la bibliothèque.

### Décisions techniques

- Abandon du select-then-upsert : le commentaire dans le code indiquait explicitement que le modèle supporte plusieurs CVs par utilisateur — le comportement upsert contredisait ce design.

---

## PR #101 — fix: use receive_message as context manager in cv-analysis

**Date :** 2026-06-25
**Branche :** `fix/cv-analysis-receive-message` → `dev`

### Ce qui a été fait

Correction dans `JobFinder/python/agents/cv_analysis/main.py` : `receive_message` est désormais appelé comme context manager (`with receive_message(...) as payload:`). Le cas file d'attente vide est traité par `except RuntimeError`.

### Contexte

`receive_message` est un `@contextmanager` qui yield le payload décodé et appelle `complete_message` / `abandon_message` à la sortie. L'agent l'appelait comme une fonction ordinaire — `msg` recevait un objet `_GeneratorContextManager`, et `msg.body` levait `AttributeError`, crashant toutes les exécutions.

### Décision technique

`with receive_message(...) as payload:` — le generator ne yield pas quand la file est vide, ce qui lève `RuntimeError` : attrapée explicitement pour logger `cv_analysis_no_message` et sortir proprement.

---

## PR #102 — feat: add management subnet to lz_dev for jumpbox VM

**Date :** 2026-06-25
**Branche :** `feature/lz-mgmt-subnet` → `dev`

### Ce qui a été fait

Ajout d'un subnet de management (`snet-jf-lz-dev-frc-mgmt`, `10.0.2.0/27`) dans le VNet de la landing zone dev, et exposition de son ID en output `subnet_mgmt_id`.

### Contexte

Prérequis au déploiement d'une VM jumpbox pour accéder à PostgreSQL en VNet privé. Le subnet de management est séparé des autres subnets (app, cae, postgresql) pour isoler les ressources d'administration.

### Décisions techniques

- `/27` (32 IPs) : largement suffisant pour une seule VM de management, avec de la marge pour d'éventuels futurs outils d'administration.
- Aucune délégation sur ce subnet : contrairement à CAE et PostgreSQL, les VMs Azure standard n'en nécessitent pas.
- PR séparée de la VM elle-même (PR B) : le subnet est une ressource `lz_*` (plateforme) — mélanger `lz_dev` et `dev` dans un même PR viole les règles Git du projet.

---

## PR #103 — feat: deploy jumpbox VM in dev

**Date :** 2026-06-25
**Branche :** `feature/jumpbox-vm` → `dev`

### Ce qui a été fait

**Module `modules/jumpbox/` :**
- `variables.tf` : variables avec descriptions et validation sur `auto_shutdown_time` (format HHMM).
- `main.tf` : NIC (IP privée uniquement), VM Linux Ubuntu 22.04 LTS Gen2 (`Standard_B1ms`) avec authentification par mot de passe, cloud-init pour installer `postgresql-client`, schedule d'arrêt quotidien à 20h UTC.
- `outputs.tf` : `vm_id`, `private_ip`.

**env dev (`envs/dev/`) :**
- `network.tf` : ajout du data source `azurerm_subnet.lz_vnet_mgmt`.
- `jumpbox.tf` : génération du mot de passe admin (`random_password`, 32 chars), stockage dans Key Vault (`jumpbox-admin-password`), instanciation du module jumpbox.
- `outputs.tf` : ajout de `jumpbox_private_ip`.

### Décisions techniques

- **Bastion Developer SKU** : accès via le portail Azure — gratuit, aucune ressource Bastion à déployer. Pas d'IP publique, pas de NSG, surface d'attaque nulle.
- **Mot de passe généré par Terraform** : `random_password` (32 chars, caractères spéciaux) stocké en Key Vault. Aucune variable à injecter en CI, aucun GitHub Secret. Pour se connecter : portail → VM → Bastion → `azureuser` + mot de passe récupéré dans le KV.
- **Auto-shutdown à 20h UTC** : seul mécanisme d'arrêt nécessaire avec Bastion (pas d'auto-désallocation IMDS).
- **Data source plutôt que `terraform_remote_state`** : cohérent avec le pattern existant (`lz_vnet_app`, `lz_vnet_cae`).
- **`data.azurerm_resource_group.rg_app`** : les resource groups de dev sont des data sources (ownership transféré à lz_dev).

---

## PR #104 — feat(cv): store thumbnails in blob storage, expose thumbnail_url via API

**Date :** 2026-06-25
**Branche :** `fix/cv-upload-always-insert` → `dev`

### Ce qui a été fait

Stockage des miniatures PDF côté serveur (Azure Blob Storage) et exposition via l'API, en remplacement de l'approche client-side fragile (objectURL pdfjs passé comme prop).

**Backend :**
- `shared/models.py` : colonne `thumbnail_url` (String, nullable) ajoutée sur le modèle `CV`.
- Migration Alembic `006_add_cv_thumbnail_url.py` : `ADD COLUMN thumbnail_url VARCHAR NULL` sur la table `cvs`.
- `schemas.py` : `thumbnail_url: str | None` ajouté dans `CVListItemOut`.
- `cv.py` : génération de miniature via `pypdfium2` (THUMBNAIL_SCALE=0.4) et upload blob non-bloquant ; `thumbnail_url` persisté dans la ligne `cvs` et retourné dans `GET /cv/`.
- `scripts/backfill_thumbnails.py` : script standalone pour les CVs existants sans miniature.

**Frontend :**
- `types.ts` : `thumbnail_url: string | null` dans `CVData`.
- `CVCard.tsx` : lit `cv.thumbnail_url` depuis l'API — grisé + spinner si pending, pleine couleur si done.
- `LibrarySection.tsx`, `UploadSection.tsx`, `HomeClient.tsx` : suppression de la machinerie `pendingThumbnail` / `onClearThumbnail` / `seenPendingRef`.

### Décisions techniques

- **pypdfium2** : dépendance transitive de pdfplumber déjà présente — pas de nouvelle dépendance externe.
- **Non-critique** : un échec de génération de miniature ne remonte pas en 500 — le CV est visible avec un fallback "PDF".

---

## PR #105 — fix: Network Contributor on subnet_mgmt for jumpbox NIC

**Date :** 2026-06-25
**Branche :** `fix/jumpbox-subnet-rbac` → `dev`

### Ce qui a été fait

Ajout de `subnet_mgmt_network_contributor` dans la map `sp_role_assignments` de `lz_dev/rbac.tf` : `Network Contributor` sur `module.subnet_mgmt.id` pour le SP `sp-jf-github`.

### Contexte

L'apply dev échouait avec `LinkedAuthorizationFailed` : le SP `dev` pouvait écrire la NIC dans `rg-jf-dev-frc-app` mais n'avait pas `Microsoft.Network/virtualNetworks/subnets/join/action` sur `snet-jf-lz-dev-frc-mgmt` (dans `rg-jf-lz-dev-frc`). Ce pattern est identique à `subnet_cae_network_contributor`, ajouté pour la même raison lors du déploiement de la Container App Environment.

### Décision technique

Même scope et même rôle que `subnet_cae_network_contributor` — cohérence avec le pattern existant. Séparé en PR dédiée car c'est un changement `lz_*` (plateforme) qui ne peut pas être mélangé avec la PR jumpbox (`dev`).

---

## PR #106 — fix(jumpbox): replace Standard_B1ms with Standard_B2s

**Date :** 2026-06-25
**Branche :** `fix/jumpbox-vm-size` → `dev`

### Ce qui s'est passé

L'apply dev échouait avec `SkuNotAvailable` :

```
The requested VM size Standard_B1ms is currently not available in location FranceCentral.
Capacity Restrictions.
```

### Correctif

Remplacement du default `vm_size` dans `modules/jumpbox/variables.tf` : `Standard_B1ms` → `Standard_B2s` (2 vCPU, 4 GB RAM). `Standard_B2s` est disponible en France Central et reste dans la gamme économique pour un jumpbox de dev.

---

## PR #107 — fix(jumpbox): use Standard_D2s_v3 in availability zone 2

**Date :** 2026-06-25
**Branche :** `fix/jumpbox-vm-size` → `dev`

### Ce qui s'est passé

`Standard_B2s` (PR #106) se heurtait à la même `SkuNotAvailable` que `Standard_B1ms`, cette fois pour la zone de disponibilité par défaut.

### Correctif

- `modules/jumpbox/variables.tf` : default `vm_size` relevé à `Standard_D2s_v3` (2 vCPU, 8 GB RAM).
- `modules/jumpbox/main.tf` : zone de disponibilité épinglée explicitement (`zone = "2"`) plutôt que laissée au choix d'Azure.

### Décision technique

Même branche que PR #106 plutôt qu'une nouvelle : l'apply avait échoué une seconde fois dans la foulée sur la même feature en cours de stabilisation, pas une régression distincte méritant son propre ticket.

---

## PR #108 — feat(cv): proxy endpoints for CV thumbnail and PDF

**Date :** 2026-06-26
**Branche :** `feature/cv-thumbnail-proxy` → `dev`

### Ce qui a été fait

Les blobs Azure sont dans un conteneur privé — le navigateur ne peut pas les atteindre directement (erreur 409). `next/image` ne résout pas le problème car le serveur Next.js n'a pas non plus les credentials.

**Backend :**
- `schemas.py` : remplacement de `thumbnail_url: str | None` par `has_thumbnail: bool` dans `CVListItemOut` — les URLs brutes Azure ne sont plus exposées au frontend.
- `cv.py` : ajout du helper `_download_blob`, deux nouveaux endpoints proxy (`GET /cv/{cv_id}/thumbnail` → JPEG, `GET /cv/{cv_id}/pdf` → PDF), tous deux protégés par JWT et requêtant le blob via `BlobServiceClient` (DefaultAzureCredential / managed identity). Mise à jour de `list_cvs` pour calculer `has_thumbnail=cv.thumbnail_url is not None`.

**Frontend :**
- `lib/api/types.ts` : `thumbnail_url: string | null` → `has_thumbnail: boolean` dans `CVData`.
- `CVCard.tsx` : réécriture complète — `useEffect` fetche `GET /cv/{id}/thumbnail` via `apiClient` (responseType blob), crée un object URL local, révoque au démontage. `<img>` brut à la place de `next/image` (incompatible avec les `blob:` URLs).

### Décisions techniques

- **`has_thumbnail` au lieu d'une URL** : ne jamais exposer au frontend une URL Azure privée qu'il ne peut pas utiliser — le booléen suffit pour piloter le fetch conditionnel.
- **Object URL** : `URL.createObjectURL` sur la réponse blob est la seule façon d'afficher un blob protégé dans un `<img>` — révocation au démontage pour éviter les fuites mémoire.
- **`<img>` brut avec `eslint-disable`** : `next/image` ne supporte pas le schéma `blob:` — l'exception est documentée et intentionnelle.

---

## PR #111 — feat(cv): delete CV with scale animation

**Date :** 2026-06-26
**Branche :** `feature/cv-delete` → `dev`

### Ce qui a été fait

Permet à l'utilisateur de supprimer un CV depuis la bibliothèque.

**Backend — `cv.py` :**
- Ajout de `_delete_blob` (helper utilisant `PurePosixPath`, cohérent avec `_download_blob`). No-op si le blob est absent (`ResourceNotFoundError`).
- Endpoint `DELETE /cv/{id}` (HTTP 204) : vérifie la propriété, supprime les blobs PDF et thumbnail, supprime les matches en cascade (FK sans `ON DELETE CASCADE`), puis supprime la ligne CV.

**Agent cv-analysis — `main.py` :**
- Si le CV est supprimé pendant que son message est en queue, `_get_cv_text` lève `ValueError`. Ce cas est maintenant intercepté séparément avant le `except Exception` général : le message est complété proprement, sans retry ni dead-letter.

**Frontend — `CVCard.tsx` / `LibrarySection.tsx` :**
- `CVCard` gère un état `DeleteState = "idle" | "confirm" | "absorbing"` et un état `isHovered`.
- Survol : fil vertical + bouton poubelle apparaissent (opacity 150ms). La poubelle a le même fond et contour que la carte au repos, et devient rouge au hover.
- Clic poubelle → `"confirm"` : sous-icônes croix (gauche) et check (vert, droite) apparaissent sur les côtés, reliées par des fils horizontaux `h-px`.
- Clic croix → retour `"idle"`. Clic en dehors de la rangée poubelle → `"idle"`.
- Clic check → `"absorbing"` : `scale(0)` + fade en 400ms via `useRef`, puis API call, puis `onDeleted`.
- `LibrarySection` : `handleCvDeleted` filtre le CV de la liste locale sans refetch.

### Décisions techniques

- **`_delete_blob` utilise `PurePosixPath`** : même parsing robuste que `_download_blob`, cohérence interne.
- **Animation impérative via `useRef`** : `scale(0)` + `opacity 0` directement sur le style DOM — évite la complexité des classes Tailwind conditionnelles pour une animation one-shot.
- **Sous-icônes sur les côtés** : optimise l'espace vertical ; la rangée `[✕] ─ [🗑️] ─ [✓]` reste dans l'empreinte horizontale de la carte.
- **`onDeleted` appelé même si l'API échoue** : la carte est retirée côté client dans tous les cas, l'erreur est loggée en console.

---

## PR #109 — fix(frontend): correct apiClient default import in CVCard

**Date :** 2026-06-26
**Branche :** `feature/cv-thumbnail-proxy` → `dev`

### Ce qui s'est passé

`CVCard.tsx` (PR #108) importait `apiClient` en named export (`import { apiClient } from "@/lib/api/client"`) alors que le module l'exporte en `export default` — erreur de build.

### Correctif

Import corrigé en `import apiClient from "@/lib/api/client"`.

---

## PR #110 — feat(frontend): library unauthenticated state and skeleton loading

**Date :** 2026-06-26
**Branche :** `feature/library-unauthenticated-state` → `dev`

### Ce qui a été fait

Deux corrections dans `LibrarySection.tsx` :

1. **État non connecté** : quand l'utilisateur n'est pas authentifié, la section bibliothèque affichait "Aucun CV importé" (bug : `loading` passait à `false` et `cvs=[]` déclenchait la condition vide sans guard `isAuthenticated`). Désormais, un message centré avec un bouton "Se connecter" est affiché à la place.

2. **Skeleton de chargement** : le texte "Chargement…" est remplacé par 3 skeleton cards animées (`animate-pulse`) qui imitent la forme d'un `CVCard`, rendant la transition visuelle immédiate lors de la connexion.

### Changements

- `LibrarySection.tsx` : import de `useMsal` et `loginRequest` ; ajout du guard `isAuthenticated` sur la condition "Aucun CV" ; remplacement du texte de chargement par 3 skeleton cards ; ajout du bloc état non connecté avec bouton `loginRedirect`.

### Décisions techniques

- La condition `{!loading && cvs.length === 0 && !error}` manquait un guard `isAuthenticated` — quand non connecté, `loading` passe à `false` immédiatement dans le `useEffect` et `cvs` reste vide, ce qui déclenchait faussement "Aucun CV importé".
- Le skeleton est conditionné à `loading && isAuthenticated` pour ne s'afficher que pendant le vrai chargement post-connexion, pas lors de la navigation en état déconnecté.
- Le bouton "Se connecter" dans la bibliothèque appelle `instance.loginRedirect(loginRequest)` — même flow MSAL que le bouton du header, cohérence UX.

---

## PR #112 — feat: Application Insights telemetry + monitoring alerts

**Date :** 2026-06-26
**Branche :** `feature/monitoring-alerts` → `dev`

### Contexte

Suite à l'incident du 25 juin (KEDA arrêté 24h sans détection), deux lacunes identifiées : les agents n'envoient aucune trace à Application Insights, et aucune alerte Azure Monitor n'existe pour détecter les jobs en échec ou les messages stagnants.

### Ce qui a été fait

**Commit 1 — Injection Application Insights dans les agents**

- `shared/telemetry.py` (nouveau) : module bootstrap OpenTelemetry — appelle `configure_azure_monitor` si `APPLICATIONINSIGHTS_CONNECTION_STRING` est présent ; no-op silencieux en dev local.
- `requirements.txt` : ajout de `azure-monitor-opentelemetry`, `pdfplumber`, `pypdfium2`.
- `webapp/requirements.txt` : ajout de `azure-monitor-opentelemetry`.
- `agents/*/main.py` (5 fichiers) : `configure_telemetry("<nom-agent>")` appelé en tête de `main()` / `lifespan()` dans chacun des agents (`cv-analysis`, `matching`, `offer-fetching`, `cleanup`, `webapp`).
- `envs/dev/container_apps.tf` : secret `appinsights-connection-string` et env var `APPLICATIONINSIGHTS_CONNECTION_STRING` ajoutés aux 4 Container App Jobs (`job_matching`, `job_cleanup`, `job_offer_fetching`, `job_cv_analysis`).

**Commit 2 — Alertes Azure Monitor**

- `envs/dev/monitoring.tf` : 3 alertes ajoutées :
  - `job_execution_failed` — sévérité 1, fenêtre 15 min, déclenche dès qu'une exécution de job passe en `Failed` (détecte les crashs agents)
  - `servicebus_deadletter` — sévérité 1, fenêtre 5 min, déclenche si `DeadletteredMessages > 0` (détecte les messages épuisés)
  - `servicebus_active_messages_stale` — sévérité 2, fenêtre 30 min, déclenche si `ActiveMessages > 0` en minimum sur 30 min (détecte KEDA mort — l'incident du 25 juin aurait déclenché cette alerte)
  - `azurerm_monitor_action_group` : action group email (`jf-owner`) branché sur `var.alert_email`
- `envs/dev/variables.tf` : variable `alert_email` avec validation regex email.
- `envs/dev/outputs.tf` : output `action_group_id`.

### Décisions techniques

- `configure_telemetry` est un import différé (`from shared.telemetry import ...` dans `main()`) — évite d'initialiser OpenTelemetry au chargement du module, ce qui pourrait interférer avec les tests unitaires.
- L'alerte `stale-messages` utilise `Minimum` comme agrégation : si le minimum sur 30 min est > 0, des messages sont restés en queue tout au long de la fenêtre — distingue les pics normaux (message consommé en < 30 min) des blocages réels (KEDA mort).
- `alert_email` sans `default` : force une valeur explicite dans `terraform.tfvars` (gitignored) — pas de risque d'envoyer des alertes à une adresse placeholder.

---

## PR #113 — fix: correct metric name for Container App Job failure alert

**Date :** 2026-06-26

### Contexte

L'apply de la PR #112 a échoué avec une erreur 400 : `Couldn't find a metric named JobExecutionRunningCount`. La métrique `JobExecutionRunningCount` n'existe pas sur `Microsoft.App/managedEnvironments`.

### Ce qui a été fait

- `envs/dev/monitoring.tf` : correction de l'alerte `job_execution_failed`.
  - Scope : `module.container_app_environment.id` → les 4 IDs des jobs (`module.job_matching.id`, `module.job_cleanup.id`, `module.job_offer_fetching.id`, `module.job_cv_analysis.id`).
  - `metric_namespace` : `Microsoft.App/managedEnvironments` → `Microsoft.App/jobs`.
  - `metric_name` : `JobExecutionRunningCount` → `Executions`.
  - `aggregation` : `Count` → `Total`.
  - `dimension.name` : `ExecutionStatus` → `state` ; `dimension.values` : `["Failed"]` → `["failed"]`.

### Décision technique

Les métriques d'exécution des Container App Jobs ne sont pas exposées sur la ressource `managedEnvironments` — elles sont publiées sur chaque ressource `Microsoft.App/jobs` individuellement. L'alerte doit donc lister les 4 jobs comme scopes et cibler le namespace `Microsoft.App/jobs`. La dimension `state` avec la valeur `"failed"` est confirmée via l'API Azure (`az monitor metrics list-definitions`).

---

## PR #114 — fix: add tenantId to KEDA azure-servicebus scaler metadata

**Date :** 2026-06-26

### Contexte

Suite à l'apply de la PR #112 (ajout du secret Application Insights), les Container App Jobs ont été recréés, ce qui a forcé KEDA à recréer les ScaledJobs. Depuis cet apply, KEDA 2.18.1 échoue en boucle avec l'erreur :

```
error parsing azure service bus metadata: no connection setting given
Failed to ensure ScaledJob is correctly created
```

Les messages `cv-analysis` et `offer-ready` s'accumulent sans être consommés.

### Cause racine

KEDA 2.18.1 a introduit un changement de comportement : pour le scaler `azure-servicebus` en mode workload identity (`clientId` dans les métadonnées), le champ `tenantId` est désormais **obligatoire**. Sans lui, KEDA ne peut pas résoudre l'identité et signale l'absence de connection string.

### Ce qui a été fait

- `modules/container_app_job/variables.tf` : ajout de la variable `uami_tenant_id` (nullable, validation UUID identique à `uami_client_id`).
- `modules/container_app_job/main.tf` : `tenantId = var.uami_tenant_id` ajouté dans le merge de métadonnées KEDA, au même niveau que `clientId`, conditionné à `uami_client_id != null`.
- `envs/dev/container_apps.tf` : `uami_tenant_id = data.azurerm_user_assigned_identity.caj.tenant_id` ajouté sur les deux jobs queue-triggered (`job_matching`, `job_cv_analysis`).

### Décision technique

Seuls les jobs queue-triggered reçoivent `uami_tenant_id` — les jobs timer-triggered (`job_cleanup`, `job_offer_fetching`) n'utilisent pas de scaler KEDA Service Bus et n'ont pas besoin de cette valeur.

### Correction post-review (non bloquant)

Ajout d'une validation croisée dans `modules/container_app_job/variables.tf` pour interdire le passage de `uami_client_id` sans `uami_tenant_id` (ou inversement) :

```hcl
validation {
  condition     = (var.uami_client_id == null) == (var.uami_tenant_id == null)
  error_message = "uami_client_id and uami_tenant_id must both be set or both be null."
}
```

Sans ce garde, un caller pouvait passer `uami_client_id` sans `uami_tenant_id`, ce qui aurait injecté silencieusement `tenantId = null` dans les métadonnées KEDA. La validation exploite la cross-variable validation introduite en Terraform 1.9 (supportée par `hashicorp/setup-terraform@v4` sans version épinglée, qui installe le latest stable ≥ 1.9).

---

## PR #115 — fix(infra): one metric alert per Container App Job

**Date :** 2026-06-28

### Contexte

L'apply de PR #114 a échoué avec :

```
Error: creating or updating Monitor Metric Alert "alert-jf-dev-job-execution-failed":
unexpected status 400 — "Alerts are currently not supported with multi resource level
for microsoft.app/jobs."
```

L'alerte `job_execution_failed` passait `scopes = local.all_job_ids` (liste des 4 IDs de jobs), mais Azure ne supporte pas les metric alerts multi-ressources pour `Microsoft.App/jobs`.

### Ce qui a été fait

- `envs/dev/monitoring.tf` : `locals.all_job_ids` converti de `list(string)` en `map(string)` (clé = nom logique du job, valeur = resource ID).
- `azurerm_monitor_metric_alert.job_execution_failed` : ajout de `for_each = local.all_job_ids` — une alerte distincte par job (`scopes = [each.value]`), nommée `alert-jf-dev-{each.key}-failed`.

### Décision technique

Azure n'expose pas les métriques d'exécution des Container App Jobs au niveau du CAE (`managedEnvironments`) ni en mode multi-ressources — chaque ressource `Microsoft.App/jobs` est scopée individuellement. Le `for_each` sur la map garantit qu'un nouveau job ajouté dans `locals.all_job_ids` reçoit automatiquement sa propre alerte sans modification supplémentaire.

---

## PR #116 — fix(infra): force KEDA reset on job-cv-analysis via tag

**Date :** 2026-06-28

### Contexte

Tentative de fix isolée pour le scaler `azure-servicebus` du job `cv-analysis` qui ne se déclenchait plus depuis le 25 juin. L'hypothèse était qu'une recréation propre via Terraform (plutôt que depuis le portail) permettrait au contrôleur KEDA de ré-enregistrer le scaler.

### Ce qui a été fait

- `modules/container_app_job/variables.tf` : ajout de la variable `additional_tags` (map, default `{}`).
- `modules/container_app_job/main.tf` : tags statiques convertis en `merge()` pour intégrer `additional_tags`.
- `envs/dev/container_apps.tf` : `additional_tags = { keda_reset = "2026-06-28" }` ajouté sur `module.job_cv_analysis`, forçant une mise à jour Terraform du job.

### Résultat

La recréation du job n'a pas suffi — le problème est systémique au niveau du contrôleur KEDA dans le CAE (les deux scalers `azure-servicebus` sont morts : `cv-analysis` et `matching`). Fix complet dans PR #117.

---

## PR #117 — fix(infra): force KEDA controller reset via CAE tag

**Date :** 2026-06-28

### Contexte

Investigation KEDA complète : les deux jobs queue-triggered (`cv-analysis` et `matching`) ont une Execution History vide depuis le 25 juin. Le scaler cron (`fetch`) fonctionne normalement. Tous les éléments vérifiés sont corrects : config KEDA (`clientId`, `tenantId`), rôle IAM `Azure Service Bus Data Owner` sur l'UAMI, réseau (pas de NSG, Service Bus `defaultAction: Allow`), état du CAE (`Succeeded`, KEDA 2.18.1).

La cause probable est un token Azure AD expiré ou invalidé dans le contrôleur KEDA, suite aux modifications de role assignments UAMI du 25 juin (commit `8b2af55`). KEDA n'a pas su renouveler ce token automatiquement. Le scaler cron n'a pas besoin de token Service Bus — il n'est pas affecté.

### Ce qui a été fait

- `modules/container_app_environment/variables.tf` : ajout de la variable `additional_tags` (`map(string)`, default `{}`).
- `modules/container_app_environment/main.tf` : tags statiques convertis en `merge()` pour intégrer `additional_tags`.
- `envs/dev/container_apps.tf` : `additional_tags = { keda_controller_reset = "2026-06-28" }` sur `module.container_app_environment`, forçant une mise à jour du CAE et un redémarrage du contrôleur KEDA.

### Décision technique

Une mise à jour in-place du CAE (tag seul, pas de recréation) provoque un redémarrage du contrôleur KEDA managé par Azure. Cela force la réacquisition d'un token Azure AD frais pour le scaler `azure-servicebus`, sans interruption du scaler cron ni des jobs en cours.

---

## PR #118 — feat(infra): add Diagnostic Settings on CAE for KEDA logs

**Date :** 2026-06-28

### Contexte

L'investigation KEDA (PR #117) a révélé que les tables `ContainerAppConsoleLogs` et `ContainerAppSystemLogs` dans Log Analytics étaient vides faute de Diagnostic Settings configurés sur le CAE. Sans ces logs, les échecs du contrôleur KEDA sont invisibles — les pannes futures seront impossibles à diagnostiquer.

### Ce qui a été fait

- `envs/dev/monitoring.tf` : ajout d'une ressource `azurerm_monitor_diagnostic_setting` ciblant le CAE (`module.container_app_environment.id`), envoyant vers le Log Analytics Workspace existant (`module.application_insights.workspace_id`).
  - Catégorie `ContainerAppConsoleLogs` : stdout/stderr des containers agents.
  - Catégorie `ContainerAppSystemLogs` : événements du contrôleur KEDA, provisioning, erreurs de scaler.

### Décision technique

Les Diagnostic Settings sont ajoutés directement dans `monitoring.tf` (pas dans le module `container_app_environment`) car ils sont une préoccupation d'observabilité de l'environnement applicatif, pas une propriété intrinsèque du CAE. Le workspace cible est le même que celui d'Application Insights — un seul workspace Log Analytics par environnement, cohérent avec l'architecture existante.

---

## PR #119 — fix(infra): force-recreate CAE, webapp and jobs after KEDA hard reset

**Date :** 2026-06-28

### Contexte

Après l'échec de toutes les tentatives de redémarrage du contrôleur KEDA (tag CAE, tag jobs, peer-to-peer encryption toggle), le CAE, le webapp (`app-jf-dev-frc`) et les 4 Container App Jobs ont été supprimés manuellement via CLI pour forcer une recréation propre du contrôleur KEDA.

Toutes les ressources supprimées sont gérées par Terraform. Aucune donnée persistante n'est stockée dans ces ressources (données dans PostgreSQL, Service Bus, Storage — intacts).

### Ce qui a été fait

Ajout d'un commentaire dans `envs/dev/container_apps.tf` pour déclencher le `terraform apply` via CI/CD. Terraform détecte les ressources absentes lors du state refresh et les recrée depuis cette configuration.

### Décision technique

La suppression manuelle est hors Terraform (`prevent_destroy = true` ne bloque que les destroy Terraform, pas la recréation après suppression externe). Un seul apply CI/CD suffit à tout remettre en place — CAE, KEDA, webapp, 4 jobs — avec un contrôleur KEDA vierge.

---

## PR #120 — fix(infra): switch KEDA Service Bus auth from workload identity to SAS connection string

**Date :** 2026-06-28

### Contexte

Après recréation complète du CAE (PR #119), le scaler `azure-servicebus` KEDA ne déclenche toujours pas les jobs `cv-analysis` et `matching`. La workload identity (UAMI `id-jf-dev-frc-caj`) est correctement configurée mais le contrôleur KEDA dans le CAE managé ne parvient pas à acquérir de token valide — comportement identifié comme un bug connu de la plateforme Azure Container Apps (issue #1344 microsoft/azure-container-apps, issue #5977 kedacore/keda).

Décision : basculer sur l'authentification par SAS connection string pour KEDA uniquement. Les agents Python continuent d'utiliser `DefaultAzureCredential` (UAMI) pour leurs propres appels Service Bus.

### Ce qui a été fait

- `envs/dev/servicebus.tf` : ajout d'un secret Key Vault `servicebus-connection-string` via `module.secret_servicebus_connection_string`, pointant vers `module.servicebus.primary_connection_string`.
- `envs/dev/container_apps.tf` : suppression de `uami_client_id` et `uami_tenant_id` sur `job_matching` et `job_cv_analysis`. Ajout du secret `servicebus-connection-string` dans la liste `secrets` des deux jobs. Le module bascule automatiquement sur le bloc `authentication { secret_name = "servicebus-connection-string" }` quand `uami_client_id = null`.

### Décision technique

La connexion SAS n'affecte que le scaler KEDA (lecture du message count pour trigger). Les agents Python (`bus.py`) utilisent toujours `DefaultAzureCredential` → UAMI → `Azure Service Bus Data Owner` pour lire/compléter les messages. Les deux mécanismes d'auth sont indépendants.

---

## PR #121 — feat(matching): switch from top-K to score threshold matching

**Date :** 2026-06-28

### Contexte

Le job matching gardait les 20 meilleures offres par CV (`MATCHING_TOP_K = 20`), indépendamment de leur pertinence réelle. Un CV spécialisé pouvait se retrouver avec 20 matches dont la plupart sont sémantiquement éloignés.

### Ce qui a été fait

- `shared/config.py` : remplacement de `MATCHING_TOP_K` par `MATCHING_SCORE_THRESHOLD` (float, défaut `0.8`, configurable via `MATCHING_SCORE_THRESHOLD` env var).
- `agents/matching/main.py` : réécriture de `_get_all_matches` — suppression de la window function `row_number()`, ajout d'un filtre `WHERE score >= threshold`. La requête retourne tous les matches dont la similarité cosinus est supérieure au seuil, sans limite de nombre.
- `envs/dev/container_apps.tf` : remplacement de la variable d'env `MATCHING_TOP_K = "20"` par `MATCHING_SCORE_THRESHOLD = "0.8"`.

### Décision technique

Un seuil de similarité cosinus à 0.8 signifie que le CV et l'offre partagent un champ sémantique très proche (80% de similarité). En pratique avec `text-embedding-3-small`, les bons matches métier se situent entre 0.75 et 0.90 — 0.8 est sélectif sans être trop restrictif. La valeur est configurable via env var pour ajuster sans redéploiement.

---

## PR #122 — feat(matching): lower score threshold from 0.8 to 0.6

**Date :** 2026-06-28

### Contexte

Le seuil `0.8` introduit en PR #121 s'est révélé trop sélectif en usage réel : trop peu de matches remontaient pour la plupart des CVs testés.

### Ce qui a été fait

- `shared/config.py` : valeur par défaut de `MATCHING_SCORE_THRESHOLD` abaissée de `0.8` à `0.6`.
- `envs/dev/container_apps.tf` : variable d'env `MATCHING_SCORE_THRESHOLD` alignée sur `0.6`.

### Décision technique

`0.6` reste au-dessus du bruit sémantique pur tout en laissant remonter des matches pertinents mais moins évidents lexicalement — ajusté à l'usage plutôt que recalculé analytiquement, cohérent avec le choix de PR #121 de garder ce seuil configurable par env var justement pour ce genre d'itération sans redéploiement de code.

---

## PR #123 — fix(frontend): show skeleton while CV library loads after login

**Date :** 2026-06-30

### Contexte

Après connexion, la bibliothèque de CV restait vide sans aucun feedback pendant une dizaine de secondes — le temps que le fetch `/cv/` se complète. Le squelette de chargement existait déjà (`CVCardSkeleton`) mais n'était jamais affiché dans ce scénario.

### Root cause

MSAL résout l'état d'authentification de manière asynchrone après le premier rendu. Au premier rendu, `isAuthenticated = false`, ce qui déclenchait `setLoading(false)` dans le `useEffect`. Quand MSAL confirmait l'authentification (`isAuthenticated = true`), `loading` était déjà à `false` — la condition `loading && isAuthenticated` du skeleton était donc fausse pendant tout le fetch initial.

### Ce qui a été fait

Deux changements dans `LibrarySection.tsx` :
- Ajout de `setLoading(true)` avant `fetchCvs()` dans le `useEffect` principal — garantit que le skeleton s'affiche dès que MSAL confirme l'auth, quelle que soit la valeur précédente de `loading`.
- Ajout de `cvs.length === 0` à la condition du skeleton — évite d'afficher les skeletons par-dessus des CV déjà chargés lors d'un `refreshTrigger` (upload).

### Décision technique

Le polling par intervalle (`setInterval`) appelle `fetchCvs()` directement, sans passer par le `useEffect` — il ne remet pas `loading` à `true`. Les mises à jour de statut en arrière-plan restent donc silencieuses, sans flash de skeleton.

---

## PR #124 — docs: extract conventions to separate files and slim down CLAUDE.md

**Date :** 2026-06-30

### Contexte

`CLAUDE.md` concentrait à la fois le contexte projet (stack, CI/CD, git flow) et les conventions détaillées de chaque technologie (Terraform, Python, SQL, Frontend). Cette densité alourdissait chaque session sans que toutes les conventions soient pertinentes en permanence.

### Ce qui a été fait

- `docs/conventions-python.md` — conventions Python extraites de `CLAUDE.md` (typage, logging, structlog, variables d'environnement, gestion des erreurs, style)
- `docs/conventions-sql.md` — conventions SQLAlchemy / Alembic extraites (modèles, nommage des contraintes, migrations)
- `docs/conventions-frontend.md` — conventions Next.js / React / TypeScript extraites (Server Components, `cn()`, dynamic import, Three.js, types API, `next/image`, API client, env vars, `loading.tsx`, route groups, nommage, découpe, `useEffect`, accessibilité)
- `docs/conventions-terraform.md` — conventions Terraform extraites (nommage, séparateurs, règles de module, commandes CLI, architecture, modules, state backend)
- `CLAUDE.md` — chaque section de conventions remplacée par une ligne de renvoi vers le fichier correspondant

### Décision technique

Les conventions restent dans des fichiers dédiés consultés à la demande (avant d'écrire du code dans la technologie concernée). `CLAUDE.md` conserve uniquement le contexte projet stable : workflow collaboratif, stack, structure repo, CI/CD, git flow, code review standards.

---

## PR #125 — feat(frontend): badge nouveaux matchs non vus sur les cartes CV

**Date :** 2026-06-30

### Contexte

Le nombre de matches s'affichait sur chaque carte CV, mais sans distinction entre les offres déjà consultées et les nouvelles depuis le dernier lancement. L'utilisateur n'avait aucun moyen de savoir si de nouvelles offres pertinentes étaient apparues.

### Ce qui a été fait

**Backend :**
- Migration `007_add_seen_at_to_matches.py` : ajout de la colonne `seen_at TIMESTAMPTZ NULL` à la table `matches`. `NULL` = non vu, timestamp = vu à cet instant.
- `shared/models.py` : champ `seen_at` ajouté au modèle `Match`.
- `schemas.py` : champ `unseen_count: int` ajouté à `CVListItemOut`.
- `routers/cv.py` — deux changements :
  - `list_cvs` : la subquery agrège maintenant `match_count` et `unseen_count` (via `COUNT(...) FILTER (WHERE seen_at IS NULL)`) en un seul scan, sans jointure supplémentaire.
  - Nouvel endpoint `PATCH /cv/{cv_id}/mark-all-seen` : vérifie l'ownership du CV, met à jour en masse tous les matches non vus (`seen_at IS NULL → now()`).

**Frontend :**
- `lib/api/types.ts` : `unseen_count: number` ajouté à `CVData`.
- `CVCard.tsx` : état local `unseenCount` (synchronisé sur `cv.unseen_count` via `useEffect`). Quand `unseenCount > 0`, un texte vert `+N nouveaux` apparaît au-dessus du compteur de matches. Un clic déclenche l'appel `PATCH /cv/{cv_id}/mark-all-seen` et remet le badge à 0 en optimiste (revert si l'API échoue).

### Décisions techniques

- `seen_at` nullable plutôt qu'un booléen `is_seen` : le timestamp permet de tracer quand la consultation a eu lieu, et préserve la possibilité de filtrer par période plus tard.
- `COUNT FILTER (WHERE seen_at IS NULL)` dans la subquery existante : un seul GROUP BY pour `match_count` et `unseen_count` — même scan, même jointure que l'existant.
- Le décrément individuel (une offre vue → `unseen_count -= 1`) est volontairement absent : il n'existe pas encore de vue liste-des-offres dans le frontend. L'infra est en place (`seen_at` en base, le champ exposé dans l'API), le câblage UI se fera quand la page matches sera construite.
- Si des offres expirent et sont supprimées par le cleanup agent, leurs matches disparaissent → l'`unseen_count` baisse automatiquement sur le prochain fetch, sans logique spéciale.

---

## PR #126 — fix(frontend): positionnement du badge +N au-dessus du compteur de matches

**Date :** 2026-06-30

### Contexte

Suite à PR #125, le badge vert `+N` était positionné au-dessus du bloc matches mais son alignement horizontal n'était pas satisfaisant. L'objectif : que le `+` démarre exactement à l'espace entre le chiffre et le mot "matchs", sans perturber le rendu de la ligne.

### Ce qui a été fait

- `CVCard.tsx` : refactoring du bloc match. Le `<p>` affiche "106 matchs" normalement avec un espace simple. Le bouton badge est sorti du flux (`absolute bottom-full left-0`) et positionné au-dessus via un span fantôme invisible (`<span className="invisible text-[10px]">{cv.match_count}</span>`) qui reproduit la largeur du nombre — le `+N` se positionne ainsi naturellement à l'espace entre le chiffre et "matchs", quelle que soit la largeur du nombre.

### Décision technique

Le span fantôme (invisible, même police que le paragraphe) est la seule approche CSS pure permettant d'aligner dynamiquement un élément `absolute` sur une position intra-texte sans JavaScript et sans perturber le flux. Les alternatives testées (inline avec `relative -top-2`, `flex items-baseline gap-1`, `ml-6 block`) modifiaient toutes soit le flux, soit l'espacement entre chiffre et "matchs".

---

## PR #127 — feat(frontend): refonte de la bibliothèque CV en grille 5 colonnes

**Date :** 2026-06-30

### Contexte

La bibliothèque affichait les cartes CV en défilement horizontal (`flex overflow-x-auto`). Ce mode ne passait pas bien visuellement sur la section snap-scroll pleine hauteur : les contrôles de suppression (fil + corbeille) débordaient hors du conteneur scrollable, et la section n'était pas centrée.

### Ce qui a été fait

- `LibrarySection.tsx` : passage de `flex overflow-x-auto` à `grid grid-cols-5 gap-x-5 gap-y-2` ; section centrée avec `flex flex-col items-center justify-center` + `relative` ; label `BIBLIOTHÈQUE` sorti du flux (`absolute top-8`) pour ne pas perturber l'alignement vertical du contenu ; skeleton étendu à 10 items (2 rangées × 5 colonnes) ; liste plafonnée à `MAX_CVS = 10`.
- `CVCard.tsx` : largeur du wrapper réduite de `w-44` à `w-36` pour s'adapter à la grille 5 colonnes.
- `CVCardSkeleton.tsx` : idem, `w-44` → `w-36`.

### Décision technique

Le `gap-y-2` (8 px) est volontairement serré : les contrôles de suppression (fil vertical + rangée de boutons) apparaissent en survol dans l'espace `gap-y`, ce qui les rend accessibles sans se superposer à la carte du dessous. Le label en `absolute` évite qu'il pousse le contenu centré vers le bas.

---

## PR #128 — error : cancelled

---

## PR #129 — feat(frontend): système de thème centralisé et toggle dark/light

**Date :** 2026-06-30

### Contexte

Toutes les couleurs de l'application étaient hardcodées dans les composants : classes Tailwind arbitraires (`bg-[#0a0a0f]`, `text-white/20`…), valeurs hex dans `OrbitAnimation.tsx` via le canvas 2D. Il n'existait aucun moyen de changer l'apparence globale sans modifier des dizaines de fichiers.

### Ce qui a été fait

**Infrastructure du thème :**
- `lib/theme/types.ts` : type `Theme` — 42 slots nommés par leur rôle CSS (`"--bg-page"`, `"--text-label"`, `"--canvas-ambient"`…). Les clés sont les noms des custom properties CSS, ce qui permet à `applyTheme()` de les écrire directement sur `:root` sans mapping intermédiaire.
- `lib/theme/themes/dark.ts` : thème sombre (palette existante — `#0a0a0f`, `rgba(255,255,255,X)`, emerald, blue-600…).
- `lib/theme/themes/light.ts` : thème clair — fonds blancs/gris, textes noirs avec opacité miroir, particules canvas sombres.
- `lib/theme/index.ts` : `applyTheme(theme: Theme)` — itère sur les entrées du thème et appelle `root.style.setProperty(key, value)`. Un seul appel pour basculer toutes les couleurs.
- `lib/theme/useTheme.ts` : hook client `useTheme()` — lit `localStorage` au mount pour persister le choix entre sessions, expose `{ themeId, toggle }`.

**Tailwind :**
- `tailwind.config.ts` : extensions `textColor`, `backgroundColor`, `borderColor`, `ringColor` avec les noms sémantiques (`text-label`, `bg-page`, `border-subtle`, `ring-default`…). Les valeurs pointent vers les CSS vars — Tailwind génère les classes, les vars fournissent les couleurs à runtime.
- `app/globals.css` : 42 custom properties dans `:root` avec les valeurs du thème sombre par défaut. Garantit que le rendu SSR est correct sans flash (le thème dark est dans le CSS statique ; `applyTheme` n'est appelé qu'au switch).

**Migration des composants :**
- `layout.tsx`, `page.tsx`, `error.tsx`, `UploadSection.tsx`, `AuthButton.tsx`, `LibrarySection.tsx`, `CVCard.tsx`, `CVCardSkeleton.tsx`, `profile/page.tsx` : toutes les couleurs hardcodées remplacées par les classes sémantiques. La page profile (palette gris/bleu) est migrée vers le thème unifié.

**Canvas (OrbitAnimation.tsx) :**
- La boucle `draw()` appelait `ctx.fillStyle = "#0a0a0f"` à chaque frame, rendant le canvas imperméable au thème CSS. Fix : `getComputedStyle(document.documentElement)` lit les vars `--bg-page`, `--canvas-ambient`, `--canvas-orbit`, `--canvas-icon` et `--canvas-icon-text` à chaque frame. Le canvas réagit instantanément au switch de thème.

**Toggle :**
- `AuthButton.tsx` : bouton ☀️/🌙 ajouté dans le dropdown du menu utilisateur. Appelle `toggle()` du hook `useTheme`.

### Décisions techniques

- **CSS vars avec valeurs rgba complètes** (pas de canaux RGB + `<alpha-value>` Tailwind) : les couleurs de l'app utilisent des opacités très variées (`/15`, `/20`, `/25`…). Stocker des valeurs complètes dans les vars simplifie les thèmes (`"rgba(255,255,255,0.20)"`) sans nécessiter de config Tailwind complexe.
- **`getComputedStyle` à chaque frame dans le canvas** : les browsers cachent la valeur, l'overhead est négligeable à 60 fps. Alternative (ref mise à jour via MutationObserver) : plus complexe pour un gain imperceptible.
- **Thème dark baked dans `globals.css`** : évite le FOUC au premier rendu SSR. Le hook lit `localStorage` après le mount client — un léger flash peut apparaître si l'utilisateur avait choisi le thème clair et recharge la page, cas rare et acceptable pour un portfolio.
- **`applyTheme` sans ThemeProvider React** : les CSS vars sont globales et réactives nativement. Un contexte React forcerait tous les composants consommateurs à être `"use client"`, ce qui va à l'encontre de la convention de minimiser les client components.

---

## PR #130 — feat(frontend): grille 10 emplacements, accès bibliothèque conditionnel

**Date :** 2026-06-30

### Contexte

Suite à la mise en place de la grille 5 colonnes (PR #127), deux problèmes restaient ouverts :
1. La grille n'affichait que les CVs présents — les emplacements vides n'étaient pas matérialisés, rendant la capacité maximale (10 CVs) invisible.
2. La section bibliothèque était toujours accessible via le scroll, même sans CV enregistré et sans être connecté, ce qui donnait accès à un état vide sans utilité.

### Ce qui a été fait

**Dimensionnement des cartes :**
- `CVCard.tsx` : largeur élargie de `w-36` à `w-44`.
- `CVCardSkeleton.tsx` : restructuré pour correspondre exactement à `CVCard` — même largeur `w-44`, même wrapper externe `flex flex-col`, 3 barres animées (au lieu de 2) calquées sur les 3 lignes de texte de la carte réelle, spacer `h-[42px]` reproduisant l'espace des contrôles de suppression toujours présents dans le DOM.

**Emplacements libres :**
- Nouveau composant `CVCardPlaceholder.tsx` : même structure que `CVCard` (même wrapper, même padding, même `aspect-[3/4]`) mais contenu invisible — simple encadré en pointillés signalant un emplacement libre.
- `LibrarySection.tsx` : la grille affiche toujours `MAX_CVS = 10` cellules : les CVs réels suivis des placeholders pour les emplacements libres (`MAX_CVS - cvs.length`).

**Accès conditionnel à la bibliothèque :**
- `LibrarySection.tsx` : calcule `accessible = isAuthenticated && cvs.length > 0`. Quand non accessible, la section est rendue `hidden` (reste montée pour continuer à fetcher et notifier) ; quand accessible, elle devient un snap point (`snap-start`). Nouveau prop `onAccessibilityChange` pour remonter l'état au parent. Dead code supprimé : bloc "non connecté", message "Aucun CV importé", import `useMsal`.
- `HomeClient.tsx` : maintient l'état `libraryAccessible`, le passe à `UploadSection`, reçoit les changements depuis `LibrarySection`.
- `UploadSection.tsx` : le label `BIBLIOTHÈQUE` et la flèche animée ne s'affichent que lorsque `libraryAccessible` est `true`.

### Décisions techniques

- `accessible = isAuthenticated && cvs.length > 0` sans `!loading` : évite que la section disparaisse brièvement pendant les re-fetches déclenchés par un upload. La section reste visible tant qu'au moins un CV est connu, même si le chargement est en cours.
- `hidden` plutôt que retrait du DOM : la section reste montée pour continuer à fetcher en arrière-plan et appeler `onAccessibilityChange` dès que des CVs apparaissent — notamment lors du premier upload depuis `UploadSection`.
- Spacer `h-[42px]` dans `CVCardSkeleton` : les contrôles de suppression de `CVCard` (`h-3.5` fil + `h-7` bouton poubelle) sont toujours présents dans le DOM avec `opacity-0`, ajoutant 42 px à la hauteur du wrapper. Sans ce spacer, skeleton et carte chargée avaient des hauteurs différentes, provoquant un saut de layout au passage de l'un à l'autre.

**Apparition instantanée du CV après animation (carte optimiste) :**
- `UploadSection.tsx` : la révocation de l'objectURL est différée — au lieu d'être faite dans `handleThumbnailReady`, elle est transférée au parent via le nouveau prop `onAnimationComplete(thumbnailUrl)` appelé dans `handleDoneComplete`. L'ownership de l'URL passe à `HomeClient`.
- `HomeClient.tsx` : maintient `optimisticUpload { thumbnailUrl, cvId }`. Un `ref` (`uploadedCvIdRef`) capture le `cv_id` retourné par `POST /cv/upload` pour gérer les deux ordres possibles : animation terminée avant la réponse HTTP, ou réponse HTTP reçue avant la fin de l'animation.
- `LibrarySection.tsx` : quand `optimisticUpload` est défini, affiche immédiatement `CVCardOptimistic` en première position, rendant la bibliothèque accessible sans attendre le réseau. L'entrée optimiste est consommée (URL révoquée, état effacé) dès que le vrai CV apparaît dans la liste (matching par `cv_id`).
- Nouveau composant `CVCardOptimistic.tsx` : carte identique à `CVCard` (mêmes dimensions `w-44`, `aspect-[3/4]`, spacer `h-[42px]`) avec l'objectURL local comme miniature, overlay `bg-black/40`, spinner SVG, et texte "Analyse en cours…".

**Retry au rechargement de page (fix MSAL) :**
- `fetchCvs` dans `LibrarySection.tsx` : en cas d'échec du premier appel, une tentative est automatiquement effectuée après 1,5 s. Couvre les race conditions transitoires de `acquireTokenSilent` qui peuvent survenir au premier chargement quand MSAL hydrate son cache de tokens depuis le stockage navigateur — ce qui empêchait d'accéder à la bibliothèque lors d'un rechargement avec un CV en cours d'analyse.

---

## PR #131 — error : cancelled

---

## PR #132 — fix(frontend): replace hardcoded colors with theme tokens + enforce color convention

**Date :** 2026-06-30
**Branche :** `feature/light-theme-colors` → `dev`

### Contexte

Après l'introduction du système de thème centralisé (PR #129), plusieurs composants de la bibliothèque conservaient des couleurs hardcodées incompatibles avec le thème clair : `CVCardPlaceholder` avait une bordure `border-white/[0.07]` invisible sur fond blanc, `CVCardOptimistic` utilisait six valeurs `white/*` et `black/*` codées en dur, et `CVCard` utilisait `bg-black/40` directement.

### Ce qui a été fait

**Nouveau token `--bg-scrim` :**
- `lib/theme/types.ts`, `dark.ts`, `light.ts` : ajout du token `--bg-scrim` (`rgba(0,0,0,0.40)` dans les deux thèmes) — overlay sombre pour assombrir un thumbnail pendant le traitement, intentionnellement identique en dark et light.
- `tailwind.config.ts` : enregistrement de `scrim: "var(--bg-scrim)"` dans `backgroundColor`.
- `app/globals.css` : déclaration du défaut SSR.

**Migration des couleurs :**
- `CVCardPlaceholder.tsx` : `border-white/[0.07]` → `border-subtle`.
- `CVCardOptimistic.tsx` : 6 couleurs migrées — `border-white/10` → `border-subtle`, `bg-white/[0.04]` → `bg-card`, `bg-white/[0.05]` → `bg-overlay`, `bg-black/40` → `bg-scrim`, `text-white/35` → `text-muted`, `text-white/25` → `text-hint`.
- `CVCard.tsx` : `bg-black/40` → `bg-scrim`.

**Conventions :**
- `docs/conventions-frontend.md` : nouvelle section "Couleurs — système de thème obligatoire" — règle interdisant les couleurs hardcodées, protocole en 4 étapes pour ajouter un token, exception `OrbitAnimation.tsx`.

### Décisions techniques

- `--bg-scrim` à `rgba(0,0,0,0.40)` dans les deux thèmes : l'overlay sert à assombrir une photo de thumbnail pour que le spinner soit lisible — la couleur sombre est sémantiquement correcte dans les deux thèmes (on veut toujours assombrir la photo, pas éclaircir).
- Les tokens `text-muted` et `text-hint` correspondent exactement aux valeurs `white/35` et `white/25` du thème sombre — aucune perte de fidélité visuelle.

---

## PR #133 — feat: section détail CV avec liste de matchs

**Date :** 2026-06-30
**Branche :** `feature/cv-detail-section` → `dev`

### Contexte

La bibliothèque affichait les CVs sous forme de grille mais ne permettait pas d'accéder aux détails d'un CV ni à ses matchs. Il manquait un point d'entrée pour consulter les offres associées à chaque CV individuellement.

### Ce qui a été fait

**Backend :**
- `routers/matches.py` : nouvel endpoint `GET /matches/cv/{cv_id}` — vérifie l'ownership du CV (`CV.user_id == user_id`), charge les matchs triés par score décroissant via `selectinload(Match.offer)`, log structuré à l'entrée et à la sortie. Gestion explicite des `HTTPException` (404 si CV introuvable ou non possédé) et `SQLAlchemyError` avec `bare raise` après logging.

**Nouveaux tokens de thème :**
- `lib/theme/types.ts`, `dark.ts`, `light.ts`, `tailwind.config.ts`, `app/globals.css` : cinq tokens ajoutés — `border-faint` (séparateurs discrets), `border-active` (onglet actif), `bg-chip` (fond carte match), `bg-dot-active` (point pagination actif), `text-warning` (score moyen).

**Types frontend :**
- `lib/api/types.ts` : trois interfaces ajoutées — `OfferOut`, `MatchOut`, `CVMatchesOut` — en miroir des schémas Pydantic du backend.

**Sélection de CV :**
- `LibrarySection.tsx` : props `onCvSelect` et `onCvsChange` ajoutés ; chaque `CVCard` reçoit `onSelect`. `onCvsChange` notifie le parent dès que la liste des CVs est chargée.
- `HomeClient.tsx` : état `selectedCvId` + `cvList`, ref `detailRef` pour le scroll. `CVDetailSection` monté conditionnellement. Scroll dans `requestAnimationFrame` pour éviter la race condition snap-mandatory (le snap point doit être enregistré par le browser avant que `scrollIntoView` soit appelé).
- `CVCard.tsx` : `hover:border-white/20` → `hover:border-soft` (conformité conventions).

**Composants :**
- `CVDetailSection.tsx` : section pleine hauteur (`snap-start`) avec indicateur BIBLIOTHÈQUE (centré, flèche ⌃ animée, ferme la section), boutons de navigation latérale pleine hauteur (← / →, `disabled:opacity-0`), points de pagination, panneau gauche (miniature + nom du CV), panneau droit (onglets Matchs / Review). Erreur réseau surfacée dans l'UI plutôt que silencieusement avalée.
- `MatchList.tsx` : skeletons de chargement (5 × `animate-pulse`), état vide, liste de `MatchItem`.
- `MatchItem.tsx` : accordéon — score coloré (`text-success` ≥ 75 %, `text-warning` ≥ 50 %, `text-muted` sinon), intitulé + entreprise + lieu + type de contrat, section dépliable (salaire, code ROME, compétences en chips).

### Décisions techniques

- **`requestAnimationFrame` pour le scroll snap** : dans un conteneur `snap-mandatory`, un `scrollIntoView` synchrone appelé au montage d'un nouveau `snap-start` est ignoré car le browser n'a pas encore enregistré le snap point. Envelopper dans `rAF` laisse le browser un cycle pour enregistrer le point avant de scroller.
- **`matchesError` explicite** : le `.catch()` original avalait silencieusement les erreurs, laissant `matches = null` et affichant "Aucun match trouvé". La gestion explicite de l'erreur permet de distinguer "pas de matchs" de "échec réseau".
- **`forwardRef` sur `CVDetailSection`** : la ref est nécessaire pour que `HomeClient` puisse appeler `scrollIntoView` sur l'élément DOM. `displayName` défini pour les DevTools React.
- **Thumbnail à faible résolution** : la constante `THUMBNAIL_SCALE = 0.4` dans `shared/constants.py` génère des miniatures à ~29 DPI — résolution intentionnellement basse pour limiter la taille de stockage. Un endpoint `GET /cv/{cv_id}/pdf` existe pour le PDF haute qualité.

---

## PR #134 — feat: MatchItem — lien offre, label ROME, onglets, gestion expiration

**Date :** 2026-07-01
**Branche :** `feature/match-item-enhancements` → `dev`

### Contexte

La liste de matchs affichait les codes ROME bruts (ex. `M1805`), le titre des offres n'était pas cliquable, et la section dépliée n'avait pas de structure par onglet. Par ailleurs, le cleanup agent ignorait le champ `expires_at` des offres, laissant en base (et dans la liste des matchs) des offres dépubliées sur France Travail.

### Ce qui a été fait

**Backend :**
- `schemas.py` : `ft_id: str` et `expires_at: datetime | None` ajoutés à `OfferOut` — ces champs existaient dans le modèle SQLAlchemy mais n'étaient pas exposés par l'API.
- `agents/cleanup/main.py` : troisième critère ajouté au `or_()` — toute offre dont `expires_at` est non nul et dépassé est maintenant purgée lors du passage quotidien (02:00 UTC), indépendamment de son âge de collecte.

**Types frontend :**
- `lib/api/types.ts` : `ft_id: string` et `expires_at: string | null` ajoutés à `OfferOut`.

**Nouveau token de thème :**
- `lib/theme/types.ts`, `dark.ts`, `light.ts`, `tailwind.config.ts`, `app/globals.css` : token `border-accent` ajouté (`rgba(96, 165, 250, 0.35)` dark / `rgba(37, 99, 235, 0.35)` light) pour la bordure du chip ROME.

**Mapping ROME :**
- `lib/rome-codes.ts` : nouveau fichier — dictionnaire `ROME_LABELS` (domaines A à N, ~200 codes) + helper `getRomeLabel(code: string): string`. Retourne le code brut si inconnu — aucune valeur inventée.

**`MatchItem.tsx` — refonte :**
- Titre : balise `<a>` ouvrant l'offre sur `candidat.francetravail.fr/offres/recherche/detail/{ft_id}` dans un nouvel onglet. Hover : `text-accent` (bleu), actif : `text-strong`. Si `expires_at` est dépassé : titre affiché en texte simple (non cliquable) + badge "Expirée" (`bg-destructive-muted`).
- Accordéon : chevron dissocié du titre — la structure `<a>` imbriquée dans un `<button>` (HTML invalide) est évitée.
- Section dépliée avec deux onglets. **Offre** : chip ROME bleuté (`bg-accent-muted border-accent text-accent`) avec libellé complet, salaire, compétences. **Analyse** : placeholder "bientôt disponible".

### Décisions techniques

- **URL France Travail construite depuis `ft_id`** : le pattern `candidat.francetravail.fr/offres/recherche/detail/{id}` est le lien canonique public — `ft_id` correspond au champ `id` de l'API France Travail.
- **`active:text-strong` plutôt que `active:text-white`** : `text-white` codé en dur casse en thème clair. `text-strong` produit l'effet "flash au clic" dans les deux thèmes sans sortir du système de tokens.
- **Mapping ROME en frontend, pas en base** : stocker les libellés nécessiterait migration Alembic + modification du collecteur + re-collection. La map frontend couvre les codes effectivement utilisés sans impacter le schéma.
- **`expires_at` dans le cleanup** : la purge basée uniquement sur `ft_updated_at`/`collected_at` laissait des offres dépubliées en base pendant des semaines. Ajouter `expires_at < now` comme critère supplémentaire garantit la cohérence entre base et plateforme France Travail.

---

## PR #136 — fix: purger les offres clôturées via collected_at

**Date :** 2026-07-01
**Branche :** `feature/cleanup-closed-offers` → `dev`

### Contexte

Environ 50 % des liens de matchs ouvrerts depuis le site menaient sur "L'offre n'est plus en ligne (offre clôturée)". Une offre clôturée disparaît des résultats de l'API France Travail, mais restait en base jusqu'à ce que son `ft_updated_at` dépasse 60 jours — soit jusqu'à 60 jours de liens morts dans la liste des matchs.

### Ce qui a été fait

- `agents/cleanup/main.py` : le prédicat de suppression multi-critères (`ft_updated_at`, `expires_at`) est remplacé par un unique `collected_at < now - 2j`. L'agent offer-fetching met `collected_at` à jour à chaque fetch pour toutes les offres retournées ; une offre absente des résultats API (clôturée) voit son `collected_at` se figer et est purgée en 2 jours maximum.
- `shared/config.py` : nouvelle constante `CLEANUP_COLLECTED_AGE_DAYS` (défaut 2, configurable via env var `CLEANUP_COLLECTED_AGE_DAYS`).

### Décisions techniques

- **`collected_at` comme seul critère** : `ft_updated_at` reflète la date de dernière modification *côté France Travail*, pas la dernière confirmation d'activité côté applicatif. `collected_at` est l'unique signal fiable — rafraîchi à chaque fetch, figé dès que l'offre disparaît de l'API.
- **Fenêtre de 2 jours** : l'agent fetch tourne 2×/jour (12:00 et 20:00 UTC), soit 4 cycles de grâce avant suppression. C'est suffisant pour absorber un incident passager sur l'agent de collecte.
- **Suppression du critère `expires_at`** : `expires_at` n'est jamais renseigné par le collecteur (placeholder non alimenté) — le critère n'avait aucun effet en pratique.

---

## PR #137 — feat: unit test suite — backend agents and frontend components

**Date :** 2026-07-01
**Branche :** `feature/unit-tests` → `dev`

### Contexte

Le projet n'avait aucun test automatisé — chaque changement backend ou frontend ne pouvait être vérifié que manuellement.

### Ce qui a été fait

- **Frontend (`__tests__/`)** : suite Jest + Testing Library — `CVCard.test.tsx`, `MatchItem.test.tsx`, `MatchList.test.tsx`, `useTheme.test.tsx`, `utils.test.ts`. `jest.config.js`/`jest.setup.ts` ajoutés, dépendances de test ajoutées à `package.json`.
- **Backend (`python/tests/`)** : suite pytest — `test_cv_analysis.py`, `test_ft_client.py`, `test_matching.py`, `test_webapp_cv.py`, `test_webapp_matches.py`, `test_webapp_profile.py`, `conftest.py` (fixtures partagées), `pytest.ini`, `requirements-dev.txt`.
- `agents/cleanup/tests/test_cleanup.py` : suite existante ajustée pour rester cohérente avec le nouveau `conftest.py`.
- `MatchList.tsx` : léger ajustement pour rendre le composant testable (pas de changement de comportement visible).
- `__tests__/README.md` et `python/tests/README.md` : conventions de test documentées par couche.

### Décisions techniques

- **Une suite par couche plutôt qu'un runner unique** : Jest pour le frontend (déjà l'écosystème Next.js), pytest pour le backend — pas d'outillage cross-stack qui aurait ajouté de la complexité pour peu de bénéfice sur un mono-repo à deux stacks distinctes.
- **`conftest.py` centralisé** : fixtures DB/mocks partagées entre les modules de test backend plutôt que dupliquées par fichier.

---

## PR #139 — feat(frontend): progression matching sur les cartes CV

**Date :** 2026-07-01
**Branche :** `feature/cv-card-match-status-ux` → `dev`

### Contexte

Après l'upload d'un CV, la carte affichait immédiatement `0 matchs` alors que l'agent de matching n'avait pas encore tourné. L'utilisateur n'avait aucun retour visuel sur l'état réel de la recherche. Par ailleurs, la transition de la carte optimiste vers la vraie `CVCard` provoquait un bref flash du texte `"PDF"` pendant le chargement de la miniature depuis le blob storage.

### Ce qui a été fait

**`agents/matching/main.py`** : après chaque run, les CVs en statut `"done"` (analyse terminée, matching non encore passé) sont avancés à `"matched"`. Le frontend dispose ainsi d'un signal non ambigu distinguant « matching en cours » (0 résultats connus) de « matching terminé avec 0 correspondances réelles ».

**`lib/api/types.ts`** : `"matched"` ajouté à `CVStatus`.

**`CVCard.tsx`** :
- Statut `"done"` → spinner + `"Recherche en cours..."` avec ellipse animée (cycles `.` → `..` → `...` toutes les 500 ms via `AnimatedEllipsis`).
- Statut `"matched"` → affichage du compte de matchs.
- `has_thumbnail && !thumbnailSrc` (fetch blob en cours) → spinner au lieu du texte `"PDF"`, éliminant le flash.

**`LibrarySection.tsx`** : le polling est étendu au statut `"done"` afin que la carte se mette à jour automatiquement à la fin du matching.

**`migrations/010_add_matched_to_cv_status.py`** : drop/recreate du CHECK constraint `ck_cvs_status` pour inclure `'matched'`.

### Décisions techniques

- **`status === "done"` comme signal de searching** : `"done"` signifie « analyse terminée, matching pas encore passé ». `"matched"` est le statut terminal après matching. Cette lecture du statut seul (sans heuristique sur `match_count`) est plus robuste et lisible.
- **Migration CHECK constraint nécessaire** : la colonne `status` avait un CHECK constraint en base (`ck_cvs_status`), contrairement à l'hypothèse initiale. La migration `010` drop et recrée le constraint avec `'matched'` inclus.
- **Ellipse animée en React plutôt que CSS keyframes** : le cycle `.` → `..` → `...` est contrôlé par un `setInterval` dans `AnimatedEllipsis`, colocalisé dans `CVCard.tsx`. Évite d'étendre `tailwind.config.ts` pour une animation ponctuelle.

---

## PR #140 — feat(ci): add unit tests workflow

**Date :** 2026-07-01
**Branche :** `feature/ci-unit-tests` → `dev`

### Contexte

La suite de tests ajoutée en PR #137 ne tournait qu'en local — rien n'empêchait une régression non testée d'être mergée.

### Ce qui a été fait

`.github/workflows/unitTests.yml` : nouveau workflow déclenché sur chaque PR (`pull_request`).
- `detect-changes` : diff des fichiers modifiés entre la base et la tête de la PR pour déterminer si les couches Python et/ou frontend sont concernées.
- `test-python` / `test-frontend` : jobs conditionnés (`if: needs.detect-changes.outputs.<layer> == 'true'`), exécutant pytest et `jest` respectivement.
- `unit-tests-gate` : unique check requis en branch protection, quel que soit le sous-ensemble de jobs réellement exécuté.

### Décisions techniques

- **Change detection plutôt que tout exécuter systématiquement** : évite de faire tourner pytest sur une PR purement frontend (et inversement) — plus rapide, sans perte de couverture puisque le layer non modifié n'a naturellement rien à régresser.
- **Un gate unique (`unit-tests-gate`)** : la branch protection référence un seul check requis, indépendant du nombre de jobs conditionnels réellement déclenchés — évite de devoir mettre à jour la config de protection à chaque ajout de job.

---

## PR #143 — fix(backend): add matched to CVStatus in webapp schemas

**Date :** 2026-07-01
**Branche :** `fix/cv-schemas-matched-status` → `dev`

### Contexte

PR #139 ajoutait le statut `"matched"` côté DB (migration 010) et côté frontend (`lib/api/types.ts`), mais pas dans le schéma Pydantic backend (`schemas.py`) — `CVStatus` y restait `Literal["pending", "processing", "done", "error"]`, sans `"matched"`.

### Ce qui a été fait

- `webapp/schemas.py` : `"matched"` ajouté à `CVStatus`.
- `python/tests/test_schemas.py` (nouveau) : test paramétré vérifiant que `CVListItemOut` accepte tous les statuts valides (y compris `"matched"`) et rejette un statut inconnu — garde-fou pour qu'un futur statut ajouté en DB/matching sans mise à jour du schéma soit détecté immédiatement.

---

## PR #135 — refactor: ROME codes — migration ARRAY vers JSONB, labels depuis le référentiel FT

**Date :** 2026-07-01
**Branche :** `feature/rome-codes-refactor` → `dev`

### Contexte

Les codes ROME étaient stockés en `text[]` dans `user_profiles.rome_codes`, sans libellés. Le frontend compensait avec un dictionnaire statique de ~200 entrées (`rome-codes.ts`). Cette approche ne permettait pas de savoir quels CVs avaient contribué à un code donné, ni de supprimer proprement un code lors de la suppression d'un CV.

### Ce qui a été fait

**Migration Alembic :**
- `migrations/versions/009_refactor_rome_codes_to_jsonb.py` : conversion de la colonne `rome_codes` de `text[]` vers `jsonb`, avec structure `{"M1805": {"cv_ids": [...], "label": "..."}}`.

**Modèle SQLAlchemy :**
- `shared/models.py` : `UserProfile.rome_codes` passe de `ARRAY(String)` à `JSONB`, valeur par défaut `{}`.

**Agent cv-analysis :**
- `shared/rome_referentiel.json` : 1 911 appellations officielles FT (codes `[A-Z]\d{4}`) générées via `scripts/fetch_rome_referentiel.py` depuis l'endpoint `/offresdemploi/v2/referentiel/metiers`. Fichier versionné dans le repo pour éviter toute dépendance réseau au démarrage du service.
- `_extract_rome_codes` : GPT-4o-mini identifie uniquement des codes — format simplifié `{"rome_codes": ["M1805", ...]}`. Chaque code est validé par regex puis vérifié dans `ROME_REFERENTIEL` (chargé au démarrage du module). Les codes absents du référentiel sont rejetés silencieusement. Le label est toujours résolu depuis le référentiel, jamais inféré par GPT.
- `_merge_rome_codes` : utilise `SELECT ... FOR UPDATE` pour éviter les écritures concurrentes. Chaque analyse ajoute `cv_id` à la liste `cv_ids` du code, sans doublon.

**Agent offer-fetching :**
- `_get_active_rome_codes` : `func.unnest()` (valide pour `text[]`) remplacé par `jsonb_object_keys()` via SQL brut — seule façon d'utiliser cette fonction set-returning dans SQLAlchemy.

**Webapp — schemas et routes :**
- `schemas.py` : `RomeCodeEntry` (Pydantic) ajouté ; `ProfileOut` et `MatchesOut` exposent `dict[str, RomeCodeEntry]` au lieu de `list[str]`.
- `routers/cv.py` : `_remove_cv_from_rome_codes` — lors de la suppression d'un CV, `cv_id` est retiré de chaque entrée du dict, et les entrées dont `cv_ids` devient vide sont supprimées. `SELECT ... FOR UPDATE` pour la cohérence.
- `routers/matches.py` : `rome_codes` casté en `dict` (au lieu de `list`) dans les deux endpoints.

**Frontend :**
- `lib/api/types.ts` : interface `RomeCodeEntry` ajoutée ; `ProfileData.rome_codes` et `CVMatchesOut.rome_codes` passent à `Record<string, RomeCodeEntry>`.
- `MatchItem.tsx` : `getRomeLabel()` remplacé par `romeCodesDict[code]?.label ?? code` — le label vient maintenant de l'API, pas du fichier statique.
- `MatchList.tsx` : prop `romeCodesDict` ajoutée et propagée à chaque `MatchItem`.
- `CVDetailSection.tsx` : `matches.rome_codes` passé à `MatchList`.
- `profile/page.tsx` : état `romeCodes` migré vers `Record<string, RomeCodeEntry>` — les chips affichent `entry.label` au lieu du code brut.
- `lib/rome-codes.ts` supprimé.

### Décisions techniques

- **Labels depuis le référentiel, pas depuis GPT** : GPT ne retourne que des codes. Le label est résolu depuis `rome_referentiel.json` chargé au démarrage — source autoritaire FT. Les codes absents du référentiel (hallucinations ou codes hors nomenclature) sont rejetés structurellement. Le risque d'hallucination sur le label disparaît.
- **`rome_referentiel.json` versionné dans le repo** : évite une dépendance réseau au boot. Le script `scripts/fetch_rome_referentiel.py` utilise le scope `api_offresdemploiv2` (déjà activé sur l'application FT) via l'endpoint `/referentiel/metiers`. À relancer si France Travail publie une nouvelle version du ROME.
- **`SELECT ... FOR UPDATE` dans `_merge_rome_codes` et `_remove_cv_from_rome_codes`** : JSONB est une valeur opaque pour PostgreSQL — un read-modify-write sans verrou en contexte concurrent (plusieurs CV analysés en parallèle) provoquerait des writes perdus.
- **`jsonb_object_keys` via `text()`** : SQLAlchemy `func.jsonb_object_keys()` ne se comporte pas comme une SRF dans `select()`. La requête SQL brute est plus lisible et garantit le bon comportement.
- **Labels en base plutôt qu'en frontend** : le libellé ROME est stocké en base avec le code et renvoyé par l'API — plus besoin du fichier statique `rome-codes.ts`. Le fallback `?? code` dans `MatchItem` couvre les offres dont le code ROME n'est pas dans le profil de l'utilisateur courant.

---

## PR #144 — feat(frontend): bouton connexion épinglé au viewport

**Date :** 2026-07-02
**Branche :** `feature/sticky-auth-button` → `dev`

### Contexte

`AuthButton` était positionné en `absolute` dans `UploadSection` (première section snap). Il disparaissait dès que l'utilisateur scrollait vers `LibrarySection` ou `CVDetailSection`.

### Ce qui a été fait

**`layout.tsx`** : `AuthButton` déplacé dans `RootLayout`, à l'intérieur de `AuthProvider`, avec `fixed right-3 top-2 z-50`. Il est désormais présent sur toutes les pages (accueil et profil) et reste ancré au viewport indépendamment du scroll.

**`UploadSection.tsx`** : import `AuthButton` et le `<div absolute>` local supprimés.

### Décisions techniques

- **Placement dans `layout.tsx` plutôt que `HomeClient.tsx`** : le bouton est utile sur toutes les pages. Le mettre dans le layout évite de le dupliquer et le rend cohérent globalement.
- **`AuthProvider` comme parent** : `AuthButton` consomme les hooks MSAL (`useIsAuthenticated`, `useMsal`). Il doit impérativement être rendu à l'intérieur de `MsalProvider`, fourni par `AuthProvider`.

---

## PR #145 — feat(ux): miniature haute résolution dans la vue détail CV

**Date :** 2026-07-02
**Branche :** `feature/ux-cv-thumbnail-lg` → `dev`

### Contexte

La miniature affichée dans `CVDetailSection` était floue : générée à `scale=0.4` (~238 × 337 px), elle était upscalée à ×2 dans un panneau de ~480 px. La cause est structurelle — une seule taille de miniature couvrait à la fois les cartes de bibliothèque (176 px) et la vue détail (jusqu'à 665 px CSS, ×2 sur écran Retina).

### Ce qui a été fait

**`shared/constants.py`** : ajout de `THUMBNAIL_SCALE_LG = 2.0` (~1 190 px de large, couvre un panneau de 665 px CSS sur écran Retina 1440 px).

**`shared/models.py`** : ajout de la colonne `thumbnail_url_lg: Mapped[str | None]` sur le modèle `CV`.

**`migrations/versions/011_add_cv_thumbnail_url_lg.py`** : migration Alembic ajoutant `thumbnail_url_lg VARCHAR(2048) NULL` à la table `cvs`.

**`agents/webapp/routers/cv.py`** :
- `_generate_cv_thumbnail(contents, scale)` — paramètre `scale` explicite au lieu de la constante globale.
- `_upload_thumbnail_blob(contents, user_id, cv_id, suffix="_thumb")` — paramètre `suffix` pour distinguer sm et lg.
- Endpoint `POST /cv/upload` : génère et stocke les deux tailles (`_thumb.jpg` et `_thumb_lg.jpg`) indépendamment — l'échec de l'une n'interrompt pas l'upload.
- Endpoint `GET /cv/{id}/thumbnail?size=sm|lg` : paramètre `size` (défaut `sm`). Si `size=lg` et `thumbnail_url_lg` est `NULL` (CV antérieur au backfill), retombe sur `thumbnail_url`.
- Endpoint `DELETE /cv/{id}` : supprime également `thumbnail_url_lg` si présent.

**`scripts/backfill_thumbnails.py`** : deux passages — passage 1 génère sm + lg pour les CVs sans miniature ; passage 2 génère lg seul pour les CVs qui n'ont que sm.

**`tests/test_webapp_cv.py`** : 4 nouveaux tests (happy path sm, happy path lg, fallback lg→sm, suppression des 3 blobs). Tests existants de suppression mis à jour (`thumbnail_url_lg = None` explicite). 20/20 au total.

**`CVDetailSection.tsx`** : fetch modifié de `/thumbnail` vers `/thumbnail?size=lg`.

### Décisions techniques

- **Deux tailles en blob, un seul endpoint** : évite de dupliquer la logique d'auth et de téléchargement. Le paramètre `?size` est transparent pour les CVCards (qui ne passent aucun paramètre et obtiennent `sm` par défaut).
- **`scale=2.0` choisi délibérément** : à `scale=0.4`, une page A4 (~595 pt) donne 238 px. À `scale=2.0`, on obtient ~1 190 px — suffisant pour couvrir 665 px CSS × 2 (Retina 1440 px). `scale=1.5` aurait été insuffisant sur grands écrans Retina.
- **Fallback sm transparent** : les CVs existants continuent de fonctionner sans backfill immédiat. Le backfill peut être lancé à la main après la migration.
- **Pas de `has_thumbnail_lg` dans le schéma** : le flag `has_thumbnail` existant reste suffisant. Le frontend ne distingue pas les tailles disponibles — le backend gère le fallback de façon transparente.

---

## PR #146 — feat(ux): redirection login au clic sur l'icône CV

**Date :** 2026-07-02
**Branche :** `feature/ux-auth-gate-on-upload-click` → `dev`

### Contexte

Un utilisateur non connecté pouvait cliquer sur l'icône CV, sélectionner un fichier via l'explorateur OS, et ce n'est qu'après la sélection que la redirection Azure AD se déclenchait (dans `handleFile`). L'ordre était contre-intuitif : la demande de connexion devait arriver avant d'ouvrir le sélecteur de fichier.

### Ce qui a été fait

**`UploadSection.tsx`** : le check `isAuthenticated` est déplacé de `handleFile` vers `handleClick`, juste avant l'appel à `fileInputRef.current?.click()`. Si l'utilisateur n'est pas connecté, `loginRedirect` est déclenché immédiatement et le sélecteur de fichier n'est jamais ouvert. Le check dans `handleFile` est conservé pour couvrir le chemin drag-and-drop.

### Décisions techniques

- **Check dans `handleClick` et non dans `handleFile`** : `handleFile` est le point d'entrée commun au clic et au drag-and-drop. Le retirer de `handleFile` aurait laissé le drag-and-drop non protégé. Les deux paths ont maintenant leur propre gate au plus tôt dans leur flux respectif.
- **`loginRedirect` et non `loginPopup`** : cohérent avec le reste de l'app — la popup est bloquée par défaut sur certains navigateurs et nécessite un geste utilisateur explicite dans le même tick.

---

## PR #147 — feat(frontend): section CV toujours disponible au scroll

**Date :** 2026-07-02
**Branche :** `feature/cv-auto-select` → `dev`

### Contexte

`CVDetailSection` n'était montée que lorsque `selectedCvId` était non-null, ce qui n'arrivait qu'après un clic explicite sur une carte. La section disparaissait également quand l'utilisateur cliquait sur "BIBLIOTHÈQUE" (`setSelectedCvId(null)`). Le résultat : la troisième section snap n'existait pas dans le DOM au chargement — le scroll vers la vue détail était impossible sans interaction préalable.

### Ce qui a été fait

**`HomeClient.tsx`** — seul fichier modifié :

- **Auto-sélection** : un `useEffect([cvList, selectedCvId])` sélectionne automatiquement `cvList[0]` (le CV le plus récent) dès que la bibliothèque contient au moins un CV et qu'aucune sélection valide n'est active. Si la liste se vide, `selectedCvId` repasse à `null`.
- **`handleCvSelect`** : remplace `setSelectedCvId` en tant que `onCvSelect` de `LibrarySection`. Sélectionne le CV ET scrolle explicitement vers `CVDetailSection` (via `requestAnimationFrame` pour laisser le snap container enregistrer la cible avant le scroll).
- **`handleCloseDetail`** : remplace `() => setSelectedCvId(null)` en tant que `onClose` de `CVDetailSection`. Scrolle vers `#library` via `scrollIntoView` sans démonter la section.

Grâce à l'auto-sélection, `selectedCvId` est toujours non-null dès que la bibliothèque est accessible — `CVDetailSection` reste donc montée en permanence comme troisième cible snap.

### Décisions techniques

- **Guard `selectedCvId && cvList.some(...)`** : le poll de 3 s dans `LibrarySection` produit un nouveau tableau à chaque cycle. Sans guard, l'effet remplacerait la sélection de l'utilisateur (navigation aux flèches) à chaque poll. Le guard préserve la sélection tant que le CV existe encore dans la liste.
- **Pas de scroll au montage** : l'ancien `useEffect([selectedCvId])` scrollait à chaque changement, y compris lors de l'auto-sélection initiale. Le nouveau design dissocie "sélection silencieuse" (auto-select) et "scroll explicite" (clic carte). L'utilisateur reste sur `UploadSection` au chargement.
- **`document.getElementById("library")`** : `LibrarySection` expose déjà `id="library"`. Évite d'ajouter un `forwardRef` au composant pour un simple scroll de retour.

---

## PR #148 — feat: affichage de la description complète dans le détail d'une offre

**Date :** 2026-07-03
**Branche :** `feature/offer-description-display` → `dev`

### Contexte

Le champ `description` (texte intégral de l'annonce France Travail) était déjà stocké en base depuis le fetch initial. Il n'était cependant jamais exposé au frontend : absent du schéma Pydantic `OfferOut`, de l'interface TypeScript correspondante, et du composant `MatchItem`. L'onglet "Offre" affichait uniquement le badge ROME, le salaire et les compétences — très peu de contenu visible au dépli d'une offre.

### Ce qui a été fait

**`python/agents/webapp/schemas.py`** : ajout de `description: str` dans `OfferOut`, positionné après `contract_type` (cohérent avec l'ordre de `models.py`). Aucune modification de router nécessaire — `model_validate` sérialise le champ automatiquement via `from_attributes=True`.

**`frontend/lib/api/types.ts`** : ajout de `description: string;` dans l'interface `OfferOut` à la même position relative.

**`frontend/app/_components/MatchItem.tsx`** : dans le bloc `activeTab === "offre"`, ajout d'un `<p>` avec `whitespace-pre-line` après les chips de compétences. La classe `whitespace-pre-line` est requise car le texte source contient des `\n` réels — sans elle, le contenu s'affiche en un seul bloc illisible.

**`python/tests/test_webapp_matches.py`** : `_make_offer()` reçoit `offer.description = "Description complète de l'offre de test."` pour éviter un `ValidationError` Pydantic sur le mock.

**`frontend/__tests__/MatchItem.test.tsx`** : `description` ajouté aux valeurs par défaut de `makeMatch()` ; nouveau test dans `describe("expand / collapse")` qui vérifie que le texte de description est rendu dans l'onglet "Offre" après dépli.

### Décisions techniques

- **Pas de troncature** : l'annonce complète est affichée telle quelle. Une troncature avec "voir plus" serait plus élégante mais hors périmètre — la donnée brute est déjà utile et lisible.
- **`whitespace-pre-line` plutôt que `whitespace-pre`** : préserve les sauts de ligne sans bloquer le retour à la ligne automatique sur petits écrans.
- **Position après les compétences** : la description est le contenu long — la placer en dernier évite de pousser les métadonnées courtes (ROME, salaire, compétences) hors du premier écran.

---

## PR #149 — feat(frontend): redesign CV detail — CorrespondancesPanel, new nav and is_new

**Date :** 2026-07-03
**Branche :** `rework-cv-page` → `dev`

### Contexte

La page CV detail existante affichait les offres via un composant `MatchItem` sans état contrôlé, avec une navigation par flèches latérales et un header lourd (logo, nom d'utilisateur). Le design handoff demandait un panneau "Vos correspondances" complet à droite et une navigation plus légère à gauche.

### Ce qui a été fait

**Tokens CSS** (`lib/theme/`, `globals.css`, `tailwind.config.ts`) — 6 nouveaux custom properties : `--bg-match-skill`, `--text-match-skill`, `--bg-new-offer`, `--text-new-offer`, `--border-match`, `--text-on-solid`. Enregistrés dans les deux thèmes et en tant qu'utilitaires Tailwind.

**Backend / API** (`schemas.py`, `lib/api/types.ts`) — `MatchOut` expose `is_new: bool` via `@computed_field` Pydantic calculé depuis `seen_at IS NULL` sur le modèle ORM `Match`. `seen_at` est exclu de la sérialisation JSON. Le type frontend `MatchOut` est mis à jour en conséquence.

**`CorrespondancesPanel.tsx`** (nouveau composant) — possède tout l'état de filtrage et d'interaction : tabs Matchs/Review, barre de filtres (recherche texte, tri pertinence/salaire/A→Z, contrat, score minimum, popover Filtre nouvelle/vue), liste avec skeleton de chargement, bannière d'offres rejetées avec restauration globale.

**`MatchItem.tsx`** — réécrit en composant entièrement contrôlé (`MatchItemData` interface). Colonne score 70px avec couleur HSL calculée et animation dorée au-delà de 90 %. Badge logo entreprise par hue déterministe depuis le nom. Accordéon avec descriptif de l'offre et colonne review agent (placeholder). `isNew` piloté par `MatchOut.is_new`.

**`CVDetailSection.tsx`** — header supprimé (logo, avatar, nom utilisateur). BIBLIOTHÈQUE + flèche ⌃ animée en haut de la section (style identique à `UploadSection`), intégrée dans le flux flex pour ne pas survoler le contenu. Pill de navigation de document dans le panneau gauche, au-dessus de la miniature. Miniature CV contrainte avec `min-h-0 / max-h-full` pour être entièrement visible sans scrollbar.

### Décisions techniques

- **`@computed_field` avec `seen_at` exclu** : `seen_at` est nécessaire pour calculer `is_new` côté Pydantic mais ne doit pas apparaître dans la réponse JSON (redondant et potentiellement sensible). `Field(exclude=True)` + `@computed_field` est le pattern Pydantic v2 idiomatique pour ce cas.
- **Composant contrôlé pour `MatchItem`** : tout l'état (expanded, saved, applied, rejected, isNew) remonte dans `CorrespondancesPanel`. Évite la duplication d'état et facilite les interactions croisées (ex : rejeter ferme l'accordéon).
- **`isNew` session-local supprimé** : l'ancien `Set<string> seen` marquait toutes les offres comme "Nouveau" au chargement. Branché sur `is_new` backend, le badge reflète correctement l'état persisté (`seen_at IS NULL`).
- **BIBLIOTHÈQUE dans le flux flex** : l'ancienne version `absolute` survolait le panneau des correspondances. En tant qu'enfant `flex-none`, elle pousse naturellement le body en dessous sans z-index.

---

## PR #151 — fix: description offre, badge Nouveau, marquage vu et filtre Nouvelles/Vues

**Date :** 2026-07-03
**Branche :** `feature/offer-seen-badge` → `dev`

### Contexte

Trois régressions ou lacunes constatées après la fusion des PRs #148 et #149 :

1. **Description absente** : PR #148 avait ajouté le rendu de `offer.description` dans l'ancien `MatchItem`. Le redesign complet du composant dans PR #149 a écrasé ce rendu — la description revenait de l'API mais n'était plus affichée.
2. **Badge "Nouveau" invisible en dark mode** : les tokens `--bg-new-offer` / `--text-new-offer` du thème sombre utilisaient `rgba(248,113,113,0.10)` (fond quasi transparent) et `rgb(248,113,113)` (texte seul, sans pastille visible). Le badge passait inaperçu.
3. **Marquage "vu" non persisté** : ouvrir une offre ne signalait pas la lecture en base. Au rechargement, toutes les offres avec `seen_at IS NULL` réapparaissaient avec le badge "Nouveau". Cause identifiée : le nouvel endpoint `PATCH /cv/{cv_id}/matches/{offer_id}/seen` n'était pas encore déployé sur l'Azure Container App (503), et les erreurs étaient silencieusement avalées.

### Ce qui a été fait

**`python/agents/webapp/routers/cv.py`** — nouvel endpoint `PATCH /cv/{cv_id}/matches/{offer_id}/seen` :
- Cherche le `Match` par `(cv_id, offer_id)` avec vérification d'ownership via join sur `CV.user_id`
- Idempotent : ne commit que si `seen_at` est `NULL`
- 404 si le match n'existe pas ou n'appartient pas à l'utilisateur
- Même pattern que `mark_all_seen` (logging structlog, guard `HTTPException`, guard `SQLAlchemyError`)

**`python/tests/test_webapp_cv.py`** — classe `TestMarkMatchSeen` avec 3 cas : happy path unseen (commit appelé, `seen_at` non-null), already-seen (commit non appelé), not-found (404).

**`frontend/app/globals.css`** + **`dark.ts`** + **`light.ts`** — tokens `--bg-new-offer` et `--text-new-offer` corrigés vers les valeurs exactes du design handoff : `rgb(253, 234, 234)` / `rgb(200, 16, 46)`. Les trois fichiers synchronisés en `rgb()` pour cohérence.

**`frontend/app/_components/MatchItem.tsx`** — `offer.description` rendu dans le panneau accordéon en `whitespace-pre-line` après les bullets de compétences. Badge `isNew` affiché dans l'en-tête de carte.

**`frontend/__tests__/MatchItem.test.tsx`** — test vérifiant que la description est rendue quand `isExpanded: true`.

**`frontend/app/_components/CorrespondancesPanel.tsx`** :
- Reçoit `cvId: string` ; état `seenIds: Set<string>` initialisé depuis `localStorage` (`jf_seen_<cvId>`)
- `toggleExpand` ajoute l'offre à `seenIds` (optimiste) + persiste en `localStorage` + appelle `PATCH .../seen` en fire-and-forget (erreur loggée en console, non bloquante)
- `isNew` passé aux items : `m.is_new && !seenIds.has(m.offer.id)` — badge disparaît dès le clic, sans attendre la réponse réseau
- **Filtre Nouvelles/Vues** : `seenIdsRef = useRef(seenIds)` mis à jour à chaque render (`ref.current = seenIds`). Le `useMemo` lit `seenIdsRef.current` sans l'avoir dans ses deps — la ref est exclue de `exhaustive-deps`, aucun `eslint-disable` nécessaire. Résultat : ouvrir une carte ne déclenche pas de recalcul du filtre ; modifier un vrai contrôle de filtre (query, tri, contrat, score, cases Nouvelles/Vues) recalcule avec les `seenIds` à jour
- Filtre renommé "Déjà vues" → "Vues"

**`frontend/app/_components/CVDetailSection.tsx`** — `cvId={selectedCvId}` propagé à `CorrespondancesPanel` ; `key={selectedCvId}` ajouté pour forcer un remontage lors du changement de CV (charge la bonne tranche `localStorage` et réinitialise tout l'état local).

### Décisions techniques

- **localStorage comme fallback au backend** : le PATCH retournait 503 (endpoint non déployé sur l'Azure Container App — feature branch pas encore mergée). Plutôt que d'attendre le déploiement, `seenIds` est persisté dans `localStorage` keyed par CV. Quand le backend sera disponible, les deux mécanismes coexistent : `is_new=false` (backend) OU `seenIds.has(id)` (localStorage) suppriment le badge.
- **Pattern "latest ref" plutôt que snapshot** : une première implémentation utilisait un état `seenIdsSnapshot` mis à jour via un helper `withSnapshot()` sur chaque handler de filtre — fonctionnel mais dupliquait la donnée et nécessitait de câbler chaque nouveau filtre. Remplacé par `useRef` inliné : la ref reflète `seenIds` sans condition à chaque render, le `useMemo` la lit sans la déclarer dans ses deps, ESLint accepte sans désactivation.
- **`key={selectedCvId}` sur `CorrespondancesPanel`** : garantit que chaque CV démarre avec un état propre (seenIds, filtre, carte ouverte). Sans la key, React réutilise l'instance et les états d'un CV précédent restent visibles le temps que les données se rechargent.
- **Endpoint sur le router `/cv/`** : cohérent avec `mark_all_seen` qui y est déjà défini. La route `/{cv_id}/matches/{offer_id}/seen` suit la hiérarchie ressource CV → Match.

---

## PR #152 — refactor: supprimer les champs profil inutilisés (contract_types, job_categories)

**Date :** 2026-07-04
**Branche :** `feature/profile-cleanup` → `dev`

### Contexte

`contract_types` et `job_categories` sur `UserProfile` étaient stockés, affichés sur `/profile` et persistés via `PUT /profile`, mais n'intervenaient **nulle part** dans la logique de matching (`routers/matches.py` ignorait complètement ces champs). Ces champs morts représentaient une surface à maintenir (schéma, route, frontend, tests) sans aucune valeur fonctionnelle.

`rome_codes` reste intact côté backend — il est central au matching. Seul son affichage redondant sur la page `/profile` est retiré (les chips sont déjà visibles dans la vue détail CV via `CVMatchesOut`).

### Ce qui a été fait

**Backend :**
- `shared/models.py` : colonnes `job_categories` et `contract_types` retirées de `UserProfile`.
- `migrations/versions/012_remove_unused_profile_fields.py` : `drop_column` des deux colonnes dans `upgrade()` ; `downgrade()` les recrée en `ARRAY(String) NOT NULL DEFAULT '{}'`.
- `agents/webapp/schemas.py` : `job_categories` et `contract_types` retirés de `ProfileUpdate` et `ProfileOut`. `ProfileUpdate` n'expose plus que `location: str | None`.
- `agents/webapp/routers/profile.py` : champs retirés du `values=` et du `set_={}` de l'upsert PostgreSQL.
- `agents/webapp/routers/cv.py` : `job_categories=[]` et `contract_types=[]` retirés de l'insert de profil par défaut à l'upload de CV.

**Frontend :**
- `frontend/lib/api/types.ts` : `job_categories` et `contract_types` retirés de `ProfileData`.
- `frontend/app/profile/page.tsx` : suppression de `CONTRACT_TYPES`, du bloc "Types de contrat" (état `contractTypes`, `toggleContractType`, JSX checkboxes), du bloc "Catégories de poste" (état `jobCategories`, `jobCategoryInput`, `addJobCategory`, `removeJobCategory`, JSX tag input), du bloc d'affichage des codes ROME (état `romeCodes`, chips). Import `RomeCodeEntry` supprimé. `handleSave` n'envoie plus que `{ location }`.

**Tests :**
- `python/tests/test_webapp_profile.py` : `_make_profile()` allégée (`job_categories`, `contract_types` retirés). `_PUT_BODY` réduit à `{ "location": "Lyon" }`. Test `test_returns_422_on_missing_required_field` supprimé — `ProfileUpdate` n'a plus de champ requis.

### Décisions techniques

- **`location` non touché** : le champ est hors périmètre — il sera remplacé par un système de zones communales dans `feature/profile-geo-search`. Modifier `location` ici créerait un conflit de colonne entre les deux branches.
- **Champs supprimés intégralement** (pas masqués) : ils n'étaient référencés nulle part dans le matching — les retirer de la DB évite toute ambiguïté sur leur utilité future.
- **Migration `downgrade()` fidèle** : recrée les colonnes avec le même type et `server_default` qu'à l'origine (`ARRAY(String)`, `NOT NULL`, `DEFAULT '{}'`) — rollback possible sans perte de contrainte.

---

## PR #153 — feat: recherche géographique par zone de communes peinte sur carte

**Date :** 2026-07-04
**Branche :** `feature/profile-geo-search` → `dev`

### Contexte

`offers.location` et `user_profiles.location` étaient de simples libellés texte, jamais utilisés comme filtre — la géolocalisation n'existait pas fonctionnellement. Or l'API France Travail renvoie pour chaque offre le code INSEE de la commune (`lieuTravail.commune`) plus ses coordonnées, champs jusqu'ici jetés à l'insertion. Puisque la précision réelle des données est la commune, la zone de recherche est définie en **peignant des communes entières** sur une carte (pas de polygone libre, pas de PostGIS) : le backend ne stocke qu'une liste de codes INSEE.

### Ce qui a été fait

**Backend :**
- `shared/models.py` : `Offer` gagne `commune` (String nullable, index `ix_offers_commune`), `latitude` et `longitude` (Float nullable, pour un futur affichage cartographique). `UserProfile.location` remplacé par `commune_codes` (`ARRAY(String) NOT NULL DEFAULT '{}'`).
- `agents/offer_fetching/main.py` : les trois champs de `lieuTravail` sont capturés dans le `values` et le `set_` de l'upsert. Pas de backfill — les offres existantes se rempliront à leur prochain passage dans le cycle de collecte.
- `migrations/versions/013_add_commune_search.py` : ajoute les colonnes offers + index, permute `location` → `commune_codes` sur `user_profiles`. Réversibilité validée en local (`upgrade head` → `downgrade -1` → `upgrade head` sur un Postgres pgvector jetable).
- `agents/webapp/` : `ProfileUpdate`/`ProfileOut` exposent `commune_codes: list[str]` ; `PUT /profile` upserte ce champ ; l'insert de profil par défaut (`cv.py`) initialise `commune_codes=[]`.
- `routers/matches.py` : **filtre géographique dur** — si `profile.commune_codes` est non vide, `GET /matches` et `GET /matches/cv/{id}` joignent `offers` et ne gardent que les matches dont `Offer.commune` est dans la zone. Zone vide = comportement inchangé (aucun filtre).

**Frontend :**
- Dépendances : `leaflet`, `react-leaflet@4` (React 18), `@turf/boolean-point-in-polygon`.
- `scripts/build-communes-geo.mjs` : télécharge les contours Etalab 2024 (simplification 1000m, licence ouverte) — le jeu inclut déjà les 45 arrondissements municipaux de Paris/Lyon/Marseille, seules les 3 communes parentes sont retirées (les offres France Travail portent des codes INSEE d'arrondissement, ex. `75101`, jamais `75056`) — découpe en un GeoJSON par département sous `public/geo/communes/` (8,2 Mo, 35 071 communes) avec un `index.json` des bounding boxes, plus `public/geo/departements.geojson` (329 Ko) pour le fond de carte stylisé.
- `app/profile/_components/CommuneZonePicker.tsx` : carte de France stylisée **sans tuiles** — contours départementaux et étiquettes de grandes villes posés directement sur le fond de la page (conteneur Leaflet transparent, aucun cadre), cadrée sur la métropole entière (`fitBounds` + zoom minimal verrouillé + `maxBounds`, aucun contrôle Leaflet). Barre d'outils : « Tout sélectionner », « Réinitialiser la zone », undo/redo par coup de pinceau (pile de 50 instantanés), compteur. Composant contrôlé (`value`/`onChange`), importé via `dynamic(..., { ssr: false })`.
- `app/profile/_components/CommunePaintLayer.tsx` : charge la géométrie des 35 071 communes dès le montage (~8 Mo de GeoJSON statique) — la peinture fonctionne partout et à tout niveau de zoom ; pinceau circulaire de taille écran fixe — clic gauche peint, clic droit efface, molette zoome vers le curseur, glisser-molette déplace la carte ; test cercle/commune préfiltré par bbox ; seule la **sélection** est dessinée (couche canvas dédiée, toujours visible) — les communes non sélectionnées n'ont aucun contour ; le fond départements vit dans un pane sous la sélection ; `onStrokeStart` notifie le parent au premier changement effectif de chaque coup de pinceau (instantané d'annulation).
- `app/profile/page.tsx` : le bloc « Localisation » (input texte) est remplacé par le picker ; `handleSave` envoie `commune_codes`.

**Tests :**
- `test_webapp_profile.py` : `location` → `commune_codes` dans `_make_profile()` et `_PUT_BODY`.
- `test_webapp_matches.py` : `_make_offer()` porte `commune="75101"`, `_make_profile()` accepte `commune_codes`. Cinq nouveaux tests valident le filtre en inspectant le statement SQL compilé passé à `session.execute` (présence/absence de `JOIN offers` et `offers.commune IN`) — pas de vraie base derrière les mocks.

### Décisions techniques

- **Pinceau circulaire plutôt que toggle de mode** : une première itération utilisait un toggle « Déplacer »/« Peindre » avec sélection point par point — jugé peu utilisable (retour utilisateur : impossible de peindre). Remplacé par un pinceau circulaire de rayon écran fixe (24 px) : plus on dézoome, plus le cercle couvre de communes. Le pan gauche de Leaflet est désactivé (`dragging={false}`) ; le déplacement passe par le glisser-molette (implémenté à la main via `map.panBy`), l'effacement par le clic droit (`contextmenu` intercepté).
- **Test cercle/commune approximé** : centre du cercle dans le polygone OU un sommet du polygone dans le rayon (distance équirectangulaire). Avec des contours simplifiés à 1000m (un sommet par km) et des rayons de plusieurs km, aucun cas réel n'échappe au test, et il reste assez léger pour tourner à chaque `mousemove` sur ~35 000 communes préfiltrées par bbox.
- **Restyle différentiel** : ne re-styler que les communes dont l'état de sélection a changé — un passage complet sur tous les polygones chargés à chaque `mousemove` gelait le renderer canvas.
- **Garde sur les contrôles Leaflet** : les `mousedown` provenant de `.leaflet-control-container` sont ignorés, sinon cliquer dessus peignait les communes situées dessous.
- **Carte stylisée plutôt que tuiles** (retour utilisateur : « une vraie carte de France intégrée dans la DA ») : les tuiles CARTO et le token `--map-tiles` d'une itération intermédiaire ont été retirés — le fond est le `--bg-page` de la page (conteneur Leaflet transparent, spécificité doublée pour battre la règle de `leaflet.css` injectée après `globals.css`), la silhouette de la France vient de `departements.geojson` (remplissage `--bg-card`, traits `--border-faint`) et ~90 villes servent de repères (marqueurs `divIcon` non interactifs, `cityLabels.ts`) affichées par paliers de zoom : 14 métropoles toujours visibles, ~30 villes régionales à partir du zoom 7, ~60 villes locales à partir du zoom 8,5 — synchronisées sur `zoomend`. La carte occupe une page élargie (`max-w-6xl`, 800 px de haut).
- **Données séparées du rendu** : une première itération ne chargeait les communes qu'au zoom ≥ 7 dans le viewport — sans pan au clic gauche, seul le centre de la France était atteignable (retour utilisateur). Les géométries sont désormais toutes chargées au montage (peinture partout, navigation entièrement à la molette puisque le zoom Leaflet est centré sur le curseur). Les contours des communes non sélectionnées, d'abord conditionnés au zoom, ont finalement été supprimés (retour utilisateur) — seule la sélection est dessinée, ce qui règle aussi la question du coût de rendu de 35 000 polygones.
- **Historique undo/redo dans le picker** : la couche de peinture appelle `onStrokeStart` une seule fois par coup de pinceau, juste avant son premier changement effectif — les coups « à vide » ne polluent pas l'historique, et « Tout sélectionner »/« Réinitialiser » créent chacun un instantané.
- **Doublons d'arrondissements corrigés** : les contours Etalab incluent déjà les arrondissements municipaux — la fusion initiale avec geo.api.gouv.fr dupliquait 45 features dans les fichiers 13/69/75 ; le script ne retire plus que les 3 communes parentes et déduplique par code INSEE.
- **Focus clavier restauré après `preventDefault()`** : le `preventDefault()` du `mousedown` de peinture supprime le focus implicite du conteneur, ce qui tuait la navigation clavier Leaflet (+/− et flèches) — `container.focus({ preventScroll: true })` est appelé explicitement à chaque coup de pinceau.
- **France métropolitaine uniquement** : la vue est verrouillée sur la métropole (Corse incluse) — les communes d'outre-mer sont présentes dans le dataset mais injoignables sur la carte ; à traiter si un besoin DOM apparaît.
- **Couleurs via variables CSS du thème** : les paths canvas Leaflet ne sont pas stylables par classes CSS — les tokens (`--bg-accent-muted`, `--border-accent`, `--border-subtle`) sont lus par `getComputedStyle` au moment du style, même exception que `OrbitAnimation`.
- **Arrondissements municipaux fusionnés au dataset** : peindre « Paris » entier sélectionnerait `75056`, code que France Travail n'émet jamais — le dataset contient donc les arrondissements à la place des trois communes parentes.

### Ce qui a été fait — itération 2 (même PR, retours utilisateur)

**Données (`scripts/build-communes-geo.mjs`) :**
- Population de chaque commune injectée dans les GeoJSON (`pop`, jointure geo.api.gouv.fr sur ~35 000 codes, arrondissements municipaux inclus) — pilote l'affichage progressif des noms.
- Second jeu de contours **simplifiés à 100m** sous `public/geo/communes-hd/` (96 départements métropolitains uniquement, ~29 Mo, coordonnées arrondies à 4 décimales) — ~5× plus de sommets que le 1000m.
- `index.json` passe de `dept → bbox` à `dept → { bbox, nom }` (noms de départements pour la liste récapitulative).

**Frontend :**
- **Détail au zoom** : dès le zoom 10, contours de toutes les communes du viewport (arrondissements de Paris/Lyon/Marseille inclus, libellés courts « 1er », « 12e ») ; les géométries HD 100m sont chargées paresseusement par département visible et substituées aux 1000m (remplissages de la sélection redessinés en HD). Zoom plafonné à 14.
- **Labels progressifs par population** : paliers (≥ 20 000 hab. dès le zoom 9, ≥ 5 000 dès 10, toutes les communes dès 11) combinés à un **placement par priorité** : tri population décroissante, rejet de tout label dont la boîte de texte estimée chevaucherait un label déjà posé (les villes statiques réservent leur place), espacement gonflé jusqu'à 2,5× en vue dézoomée, plafond de 200 labels par vue.
- **Liste récapitulative temps réel** sous la carte : groupée par département (ordre numérique, 2A/2B après le 20), compteur « x / total communes », sections repliables — seules les sections dépliées rendent leurs communes — tri alphabétique français avec collation numérique (Paris 2e avant Paris 18e).
- **Contour national bleu** quand la zone est vide (sémantique « toute la France, aucune restriction ») : dissolution côté client des frontières départementales partagées (les arêtes internes apparaissent deux fois et s'annulent) → 22 anneaux fermés en ~60 ms. Le bouton « Tout sélectionner » disparaît au profit de cette sémantique ; reste « Réinitialiser ».
- **Compression par département** : à l'écriture API, chaque département intégralement sélectionné devient un jeton `dept:xx` ; décompression à l'affichage, jetons non résolus préservés pendant le chargement du référentiel.
- **Thème clair** : les paths canvas Leaflet figent leurs couleurs au style — un `MutationObserver` sur l'attribut `style` de `<html>` (réécrit par `applyTheme()`) re-style sélection, fond départements, contours HD et liseré national au changement de thème.
- Indications d'usage sous la carte supprimées ; seule l'attribution Etalab/IGN (Licence Ouverte) subsiste.

**Backend :**
- `routers/matches.py` : condition géographique factorisée (`_commune_zone_condition`) — les jetons `dept:xx` se traduisent en préfixe SQL (`Offer.commune LIKE 'xx%'`, `autoescape`) OR-és avec le `IN` des codes isolés. Test ajouté sur le statement compilé (`IN` + `LIKE` + `OR`).

### Décisions techniques — itération 2

- **HD paresseux plutôt que 100m partout** : le chargement initial reste à 8,5 Mo (peinture immédiate sur toute la France) ; le détail 100m n'est payé que pour les départements effectivement zoomés.
- **Labels par collision plutôt que paliers seuls** (retour utilisateur : « mur de texte » en Île-de-France) : un palier de population déverse tous ses noms d'un coup en zone dense ; le placement priorisé garantit zéro chevauchement quelle que soit la densité, et les noms apparaissent au fil du zoom quand la place se libère.
- **Compression à la frontière API, côté client** : le backend n'a pas le référentiel des communes (il vit dans `public/geo/`) ; le frontend, qui l'a déjà en mémoire, compresse/décompresse — le backend ne connaît que la sémantique « préfixe INSEE ». Les zones énormes passent de milliers de codes à quelques jetons (stockage et paramètres SQL).
- **Dissolution topologique côté client** : Etalab ne publie pas de contour « métropole » ; les contours départementaux étant topologiquement cohérents, l'annulation des arêtes partagées donne le contour national sans dépendance (pas de turf/union) ni fichier supplémentaire.
- **Anciennes zones non compressées** : un profil enregistré avant la compression reste en codes bruts — lu normalement, compressé automatiquement au prochain enregistrement. Aucune migration nécessaire.
- **Offres sans code commune conservées malgré la zone** (retour utilisateur) : une offre France Travail sans `lieuTravail.commune` (télétravail, portée nationale) correspond potentiellement à tout — le filtre géographique inclut `offers.commune IS NULL` dans son OR plutôt que d'exclure ces offres.

---

## PR #154 — feat: intégration de la carte de zone à l'accueil, transition « focus caméra »

**Date :** 2026-07-06
**Branche :** `feature/home-map-transition` → `dev`

### Contexte

La carte de communes (PR #153) ne vivait que sur `/profile`. Vision produit : la carte n'est pas une section de scroll supplémentaire mais un **second calque de la section d'upload CV**, affiché en permanence en arrière-plan (centré, légèrement flouté, non interactif). Un scroll molette vers le haut — geste qui ne peut naturellement rien faire d'autre en haut de page — déclenche une transition complète façon « focus pull » d'appareil photo (flou + zoom + fade + vignette) qui rend la carte nette et peignable ; un scroll vers le bas joue la transition inverse. La route `/profile` est conservée telle quelle en parallèle (réserve pour de futurs réglages de profil).

### Ce qui a été fait

**Frontend :**
- `CommuneZonePicker` : variante opt-in `variant="embedded"` — remplit son parent, pas de résumé par département, attribution Etalab compacte superposée à la carte, pas d'outline de focus, compteur de sélection centré en haut, et insets négatifs gauche/bas qui surdimensionnent le conteneur au-delà de la section (débordement croppé par son `overflow-hidden`) pour asseoir la France sur l'icône CV. Rendu `/profile` inchangé quand les nouvelles props sont absentes.
- `CommunePaintLayer` : trois hooks pour un composant hôte — `onPaintingChange` (début/fin de trait de pinceau), `onAtMinZoomChange` (vue posée au zoom minimum : invalidé dès `zoomstart`, resynchronisé au `zoomend`), `viewResetToken` (incrément → retour instantané au cadrage national initial, `animate: false`). Le cercle de pinceau exige désormais que le curseur **atteigne** la carte (`elementFromPoint`), pas seulement son rectangle — il reste masqué quand la carte est un fond `pointer-events: none`.
- `UploadSection` : ne possède plus sa `<section>` (rendu en calque `absolute inset-0`), indication CARTE (chevron rebondissant vers le haut) symétrique de BIBLIOTHÈQUE, visible uniquement connecté.
- `MapSection` : wrapper léger du picker embedded, import `dynamic({ ssr: false })` avec placeholder pulsant.
- `HomeMapSection` : machine à états `cv / to-map / map / to-cv` (425 ms, constante unique partagée entre timers, transitions CSS et keyframe de vignette). Sortie du mode carte par molette bas : curseur hors de la carte, ou au-dessus d'elle une fois la vue posée au dézoom max depuis ≥ 200 ms (période de grâce contre l'élan de molette). Un trait de pinceau en cours absorbe tout scroll. Chaque sortie remet la carte sur son cadrage d'origine et flushe la sauvegarde. Zone auto-sauvegardée par debounce (800 ms) via `PUT /profile`. Accès au mode carte réservé aux utilisateurs connectés.
- `HomeClient` : monte `HomeMapSection` à la place d'`UploadSection`, callbacks inchangés via `uploadProps`.

**Backend :** aucun changement (`commune_codes` et l'API `/profile` existaient déjà).

### Décisions techniques

- **Molette : zoom carte vs sortie de page via la propagation DOM** — le handler `ScrollWheelZoom` de Leaflet stoppe la propagation de tout `wheel` reçu par son conteneur : un wheel sur la carte zoome, un wheel ailleurs bulle jusqu'à la section. Rien à calculer (pas de `getBoundingClientRect`).
- **Écouteur wheel natif non-passif, en phase capture** — React attache `onWheel` en passif (`preventDefault()` silencieusement ignoré), d'où un `addEventListener` natif ; la phase capture est nécessaire pour voir aussi les wheels au-dessus de la carte (sortie au dézoom max) puisque Leaflet les stoppe en phase bulle.
- **Jamais démonter ni `display:none` le calque carte** — transitions pilotées uniquement par `opacity`/`filter`/`transform` : la taille layout du conteneur ne change jamais, aucun `invalidateSize()` ni bug Leaflet de conteneur masqué.
- **Centrage par crop du conteneur plutôt que par transform** — un `translate` sur le calque glissait vers la position « vraie » en mode carte ; les insets négatifs déplacent le cadrage dans la géométrie même du conteneur, et le `scale` de la transition (origine centre) préserve la position : la carte est au même endroit dans tous les modes, toolbar et attribution comprises.
- **État « au dézoom max » invalidé dès `zoomstart`** — synchronisé seulement au `zoomend`, un enchaînement rapide zoom + scroll bas sortait vers l'accueil en plein zoom (l'animation n'avait pas encore émis son `zoomend`).
- **Reset de vue instantané (`animate: false`)** — il s'opère derrière le flou de sortie, et un saut instantané ne peut pas rester à moitié fait si une animation est interrompue (le zoom animé de Leaflet passe par `requestAnimationFrame`, gelé dans un onglet masqué).
- **Sauvegarde par debounce plutôt qu'au clic sur le bouton profil** — accrocher la sauvegarde à `AuthButton` (monté globalement dans `layout.tsx`) exigerait un état partagé global pour un bénéfice minime ; le debounce + flush à la sortie couvre tous les cas (bouton profil, changement d'onglet, fermeture).
- **Molette uniquement, pas de tactile** — la peinture est déjà souris uniquement (backlog « Support tactile du pinceau de communes ») ; la transition suit. Piste `Escape` signalée en commentaire, non bloquante.
- **Pinceau masqué par hit-test réel** — `elementFromPoint` contenu dans le conteneur : couvre le mode accueil et les transitions sans prop supplémentaire, `/profile` inchangé.

---

## PR #155 — fix: repli département pour les offres sans code commune dans le filtre de zone

**Date :** 2026-07-06
**Branche :** `feature/fix-commune-zone-department-fallback` → `dev`

### Contexte

Retour utilisateur après le merge de PR #153/#154 : peindre et enregistrer une zone communale sur `/profile` n'avait aucun effet visible sur `/matches`. Diagnostic confirmé par requêtes live en lecture seule sur la base dev (autorisation explicite de l'utilisateur, accès via `az containerapp exec` dans le webapp — Postgres est en VNet privé, aucun accès direct possible depuis l'extérieur) plutôt que par simple lecture de code : `_commune_zone_condition()` (`routers/matches.py`) OR-ait `Offer.commune.is_(None)` sans condition, pensé (PR #153) pour laisser passer les offres remote/nationales. En pratique, 3128 offres sur 5002 (62,5 %) ont `commune = NULL` au moment du diagnostic, et l'écrasante majorité de ces offres ne sont pas remote : leur `location` contient une ville ordinaire (`"75 - Paris"`, `"31 - Toulouse"`, `"69 - Lyon"`...) — France Travail laisse souvent le code INSEE structuré vide même quand le libellé texte donne une vraie ville (lacune de qualité de donnée côté source, pas un bug d'ingestion). Sur une zone de test (01/38/42/69), le filtre ne réduisait que 5002 → 3344 résultats au lieu des 216 offres réellement dans la zone — le bypass noyait le signal utile.

*Aparté sécurité relevé pendant l'investigation, hors périmètre de cette PR :* un seul rôle Postgres (superutilisateur) existe côté infra, partagé par le webapp public et tous les jobs batch (même chaîne de connexion admin injectée partout) — pas de séparation de privilèges par service. Signalé à l'utilisateur pour arbitrage avec Claude Cowork, non traité ici.

### Ce qui a été fait

**Backend :**
- `shared/geo.py` (nouveau) : `parse_department_from_location()` extrait un code département depuis le libellé texte France Travail (`"75 - Paris"` → `"75"`, gère Corse `2A`/`2B` et DOM/TOM `97x` ; retourne `None` pour `"France"`, `"Luxembourg"`, vide ou absent). `department_from_commune()` dérive le département depuis un code INSEE déjà connu. Deux fonctions pures, sans accès DB/réseau.
- `shared/models.py` : `Offer` gagne `department` (String nullable, index `ix_offers_department`).
- `agents/offer_fetching/main.py` : `department` dérivé de `lieuTravail.libelle` à chaque cycle de fetch/upsert, indépendamment de la présence de `commune`.
- `migrations/versions/014_add_offer_department.py` : ajoute la colonne + index, backfill des offres déjà en base où `commune IS NULL` (relit `location`, aucun rappel à l'API France Travail nécessaire). Réversibilité et idempotence vérifiées sur un conteneur `pgvector/pgvector:pg16` jetable (`upgrade head` → `downgrade -1` → `upgrade head` reproduit un backfill identique sur des lignes de test Paris/Corse/Guadeloupe/"France").
- `routers/matches.py` : `_commune_zone_condition()` retravaillée — le bypass inconditionnel devient un repli département, **gated derrière `commune IS NULL`** : une offre avec un `commune` connu hors zone n'est jamais repêchée par une correspondance de département (le commune précis prime), et seules les offres où ni `commune` ni `department` ne sont déterminables gardent le bypass total (ex. `"France"`, `"Luxembourg"`).

**Tests :**
- `test_geo.py` (nouveau) : cas Paris/Corse/DOM-TOM/valeurs non résolvables pour les deux helpers.
- `test_webapp_matches.py` : nouveaux tests directs sur `_commune_zone_condition` (inclusion via département, exclusion hors zone, bypass restreint, non-repêchage d'un commune précis hors zone via `and_`). L'assertion multi-départements compare l'ensemble des valeurs du `IN(...)` plutôt qu'un ordre littéral fixe — les sets Python n'ont pas d'ordre d'itération garanti pour des chaînes (hash randomisé), l'assertion à ordre fixe échouait sous certaines valeurs de `PYTHONHASHSEED` (reproduit empiriquement avant correction).

### Décisions techniques

- **Repli département plutôt que rappel à l'API France Travail** : le backfill ne relit que la colonne `location` déjà en base — aucune dépendance à la disponibilité de l'API France Travail pour une migration, cohérent avec la façon dont `commune`/`latitude`/`longitude` avaient été ajoutés en PR #153.
- **Repli gated derrière `commune IS NULL`** : `department` est renseigné pour **toutes** les offres à l'ingestion (pas seulement celles sans commune) — un simple OR sur `Offer.department.in_(departments)` aurait pu repêcher une offre au commune précis mais hors zone via une coïncidence de département. Le repli et le bypass total partagent donc le même garde-fou `and_(Offer.commune.is_(None), ...)`.
- **Diagnostic vérifié en conditions réelles avant l'implémentation** : requêtes de comptage live sur la base dev (`commune IS NULL`, échantillon de `location`, simulation de la zone 01/38/42/69) plutôt qu'une hypothèse basée sur la seule lecture du code — a permis d'écarter une piste concurrente (staleness du fetch côté frontend) et de confirmer que le bypass NULL était bien la cause dominante.
- **Nettoyage post-review en 6 commits atomiques** : rebase sur `dev` (PR #154 mergée entretemps, conflit résolu sur `docs/BACKLOG.md`) puis reconstruction de l'historique via `git reset --soft` + recommits ciblés par fichier plutôt qu'un rebase interactif (non supporté par l'outillage) — les correctifs de retour de review (test non déterministe, clarification de contrat) sont repliés dans leurs commits d'origine plutôt que de rester des commits « fixup » séparés.

---

## PR #156 — fix: repli région pour la zone de matching, refetch des correspondances au changement de zone

**Date :** 2026-07-06
**Branche :** `fix/matches-refresh-on-zone-change` → `dev`

### Contexte

Deux angles morts distincts découverts après le merge de PR #155, tous deux via retour utilisateur en usage réel plutôt que par relecture de code.

Le premier : requêtes live sur la base dev ont montré que le repli département de PR #155 laissait encore passer 17 offres portant un libellé **région** (« Île-de-France », « Bourgogne-Franche-Comté », « Centre-Val de Loire ») sans aucun code département — France Travail donne parfois un nom de région nu plutôt qu'un libellé « DD - Ville » — via le bypass inconditionnel, faisant apparaître ces offres même en peignant un unique département sans rapport (ex. Lyon seul). `DEPARTMENT_PREFIX_RE` manquait par ailleurs `98[6-9]` (Wallis-et-Futuna, Polynésie française, Nouvelle-Calédonie), faisant tomber des offres comme « 987 - Papeete » à `department = NULL`.

Le second : `HomeMapSection`, `LibrarySection` et `CVDetailSection` sont des sections sœurs montées en permanence sur la page d'accueil (scroll-snap, jamais démontées) — peindre une nouvelle zone puis revenir à la vue des offres affichait des correspondances périmées, le fetch de `CVDetailSection` ne dépendant que de `selectedCvId`, sans signal que la zone (et donc les résultats) avait changé.

### Ce qui a été fait

**Backend :**
- `shared/geo.py` : `DEPARTMENT_PREFIX_RE` reconnaît désormais `98[6-9]` ; `department_from_commune()` traite les codes commune `98x`. Ajout de `parse_region_from_location()` et `regions_intersecting()` — table `REGION_DEPARTMENTS` couvrant les 13 régions métropolitaines et les 5 DROM mono-départementaux, normalisation accents/apostrophes/casse (`_normalize_region`) car la donnée source est incohérente (« Île-de-France » et « Ile-de-France » coexistent).
- `shared/models.py` / `agents/offer_fetching/main.py` : `Offer.region` (indexée, nullable), peuplée depuis `lieuTravail.libelle` à chaque cycle fetch/upsert, même schéma que `commune`/`department`.
- `migrations/versions/015_add_offer_region.py` : ajoute la colonne + index ; re-parse le département des lignes que la migration 014 avait manquées (`98[6-9]` pas encore reconnu) ; backfille `region` pour les lignes où `commune` et `department` restent NULL. Réversibilité et idempotence vérifiées sur un conteneur `pgvector/pgvector:pg16` jetable (`upgrade head` → `downgrade -1` → `upgrade head` reproduit le même backfill), y compris une ligne Papeete passant de `department=NULL` à `department="987"`, des lignes Île-de-France/Bourgogne-Franche-Comté recevant leur région, et une ligne « France »/Luxembourg restant intégralement non résolue.
- `routers/matches.py` : `_commune_zone_condition()` passe de deux à trois niveaux de repli — commune → département → région, chacun gated derrière l'inconnu du niveau précédent. Une offre à département connu hors zone n'est jamais repêchée par une coïncidence de région (même règle de préséance que département sous commune). Seules les offres où ni commune, ni département, ni région ne sont déterminables (« France », « Luxembourg ») gardent le bypass total.

**Frontend :**
- `HomeMapSection` expose `onZoneSaved`, appelé après succès du `PUT /profile` (pas avant, pour ne pas courir en parallèle de la sauvegarde). `HomeClient` maintient un compteur `zoneVersion` incrémenté à chaque appel et le transmet à `CVDetailSection`, dont l'effet de fetch dépend désormais de `[selectedCvId, zoneVersion]`. Vérifié en conditions réelles : peindre une nouvelle zone puis revenir à la vue des offres déclenche un nouveau `GET /matches/cv/{id}` (81 résultats zone Lyon → 38 résultats zone Marseille/Aix-en-Provence après repeinture).

**Tests :**
- `test_geo.py` : normalisation accents/casse/apostrophe de `parse_region_from_location`, `regions_intersecting`, codes département COM 987/988.
- `test_webapp_matches.py` : nouvelle classe `TestCommuneZoneConditionRegionFallback` — inclusion via correspondance région, exclusion région hors zone, bypass final restreint, garde-fou département-connu-prioritaire contre un faux repêchage par région.

### Décisions techniques

- **Repli département avant région, jamais l'inverse** : la région est la granularité la plus grossière des trois — un repêchage par région ne doit jamais contredire un département déjà connu et hors zone, même règle de préséance qu'entre commune et département en PR #155.
- **Diagnostic vérifié sur données réelles avant implémentation** : comptage live sur la base dev (offres à région nue, simulation zone Lyon-only) plutôt qu'une hypothèse de code seul — a confirmé les 17 offres région comme cause du bypass excessif.
- **`zoneVersion` bumped après succès du `PUT /profile`, pas avant** : un bump optimiste aurait pu déclencher un refetch avant que la zone soit effectivement persistée, courant le risque de lire l'ancienne zone côté backend.
- **Compteur plutôt que ref de zone brute** : `CVDetailSection` n'a besoin de savoir *qu'*un changement a eu lieu, pas de connaître la zone elle-même — un entier incrémental évite de propager `commune_codes` à travers `HomeClient` jusqu'à un composant qui ne les utilise pas directement.

---

## PR #157 — fix: badge vert de la bibliothèque non rafraîchi à la consultation, non filtré par zone

**Date :** 2026-07-06
**Branche :** `fix/library-unseen-count-refresh` → `dev`

### Contexte

Retour utilisateur : le badge vert `+N` affiché sur chaque carte CV de la bibliothèque (nombre de nouveaux matchs) ne réagissait à rien après le chargement initial. Deux angles morts distincts :

1. Consulter (déplier) une offre dans `CorrespondancesPanel` appelle bien `PATCH /cv/{cv_id}/matches/{offer_id}/seen`, mais aucun signal ne remontait jusqu'à `LibrarySection` pour redemander `GET /cv/` — le badge restait figé sur la valeur du chargement initial jusqu'au prochain upload ou poll.
2. `list_cvs` (`GET /cv/`) calculait `unseen_count` (et `match_count`) par un simple `COUNT(...)` sur `Match`, sans jointure ni filtre géographique — contrairement à `GET /matches` et `GET /matches/cv/{cv_id}` qui appliquent `_commune_zone_condition()` (PR #155/#156). La bibliothèque pouvait donc annoncer des matchs (nouveaux ou non) hors de la zone peinte par l'utilisateur, qui n'apparaissent jamais dans la liste réellement affichée.

Retour de test supplémentaire une fois le premier correctif en place : le total gris (`X matchs`) devait lui aussi respecter la zone sélectionnée sur la carte, pas seulement le badge vert — élargi au cours de cette même PR plutôt que de rouvrir un ticket séparé.

**Découverte en testant manuellement les deux correctifs ci-dessus** (frontend local pointé sur le backend dev déployé) : la console navigateur montrait `Access to XMLHttpRequest ... has been blocked by CORS policy` sur chaque `PATCH .../seen`, avec `AxiosError: Network Error` côté client. `CORSMiddleware` (`main.py`) n'incluait pas `PATCH` dans `allow_methods` depuis son ajout en PR (commit `cc93c99`, « feat: add configurable CORS middleware to webapp API ») — le preflight `OPTIONS` du navigateur pour toute requête `PATCH` cross-origin échouait donc systématiquement, et la requête réelle n'atteignait jamais le backend. Bug préexistant, indépendant des deux points ci-dessus : consulter une offre ne persistait `seen_at` côté serveur **dans aucune version antérieure du frontend** — seul le marquage local (`localStorage`, introduit en PR #151) donnait l'illusion que ça fonctionnait (le badge « Nouveau » disparaît côté client indépendamment du serveur). Sans ce correctif, les deux points 1 et 2 restent invérifiables en conditions réelles : le badge de la bibliothèque ne peut jamais refléter une consultation, quel que soit l'état du reste du code.

**Angle mort supplémentaire signalé par l'utilisateur en revue** : le cache `seenIds` (`localStorage`) de PR #151 sert non seulement à masquer instantanément le badge « Nouveau » côté client, mais aussi de garde (`!seenIds.has(id)`) décidant si le `PATCH .../seen` est envoyé au backend — une fois un id dans ce cache, plus aucune tentative n'est refaite. Conséquence directe du bug CORS : toute offre consultée pendant la période où le `PATCH` échouait silencieusement reste marquée « traitée » côté client à vie, sans que le backend n'ait jamais reçu le signal — le badge vert de la bibliothèque resterait donc faux indéfiniment pour ces offres précises, même après le correctif CORS, sans readjustement automatique.

### Ce qui a été fait

**Backend :**
- `main.py` : `allow_methods` de `CORSMiddleware` gagne `"PATCH"` — sans ça, `PATCH /cv/{cv_id}/matches/{offer_id}/seen` et `PATCH /cv/{cv_id}/mark-all-seen` échouent silencieusement (bloqués par le navigateur avant même d'atteindre FastAPI, aucune trace côté serveur).
- `routers/matches.py` : `_commune_zone_condition()` renommée en `commune_zone_condition` (perd son underscore, désormais partagée entre routers, logique inchangée).
- `routers/cv.py` : `list_cvs` récupère le `UserProfile` de l'utilisateur et calcule un `zone_condition` unique (`commune_zone_condition(profile.commune_codes)` si `commune_codes` est non vide, sinon `true()`), appliqué aux deux `COUNT(...) FILTER` — `match_count` filtré par `zone_condition` seul, `unseen_count` par `and_(seen_at IS NULL, zone_condition)` — avec jointure `Match.offer_id == Offer.id`. La jointure vers `Offer` est une inner join sans risque : `offer_id` est une FK `NOT NULL`, donc aucune ligne n'est perdue quand la zone est vide (`true()` ne filtre rien).

**Frontend :**
- `HomeClient.tsx` : `uploadCount` renommé `libraryRefreshTrigger` (portée élargie, pas seulement les uploads) et incrémenté aussi dans `handleZoneSaved` et dans un nouveau `handleMatchSeen`, passé à `CVDetailSection` → `CorrespondancesPanel`.
- `CorrespondancesPanel.tsx` : `toggleExpand` chaîne `onMatchSeen?.()` après succès du `PATCH .../seen` (pas avant, pour ne pas rafraîchir avant que `seen_at` soit réellement committé côté backend). Nouvel effet de réconciliation : à chaque changement de `matches`, toute offre où le backend dit encore `is_new: true` alors que le cache local la considère déjà traitée déclenche un nouveau `PATCH .../seen` en tâche de fond — le backend reste la seule source de vérité, `localStorage` ne sert plus qu'à l'affichage instantané, jamais à décider définitivement qu'une tentative ne doit plus être refaite.

**Tests :**
- `test_webapp_main.py` (nouveau) : `allow_methods` de `CORSMiddleware` contient `PATCH` et les méthodes attendues — importe `main.py` avec `BlobServiceClient` patché (même technique que `test_webapp_cv.py`), sans déclencher le lifespan (donc sans tenter de connexion DB réelle).
- `test_webapp_matches.py` : import mis à jour (`commune_zone_condition`).
- `test_webapp_cv.py` : 3 nouveaux tests sur `list_cvs` — `match_count` et `unseen_count` tous deux filtrés quand `commune_codes` est renseigné (assertion sur le nombre d'occurrences de la condition de zone dans le SQL compilé, une par `FILTER`), non filtrés quand la zone est vide ou qu'il n'y a pas de profil.
- `CorrespondancesPanel.test.tsx` : 4 nouveaux tests — `onMatchSeen` appelé une fois le PATCH résolu, pas rappelé sur un cycle replier/redéplier de la même offre (déjà dans `seenIds`) ; retry automatique quand `is_new: true` + id déjà dans le cache local, pas de retry quand le backend confirme déjà vu.

Vérifié par tests unitaires (pytest + jest) et `tsc --noEmit`/`eslint` sans erreur, et par test manuel réel qui a révélé le bug CORS (console navigateur) ; le correctif CORS lui-même n'a pas encore pu être revérifié en conditions réelles puisqu'il nécessite un déploiement (backend non exécutable en local — DB en VNet privé).

### Décisions techniques

- **CORS traité comme faisant partie de cette PR plutôt qu'un ticket séparé** : découvert en testant les deux correctifs ci-dessus, et bloquant leur vérification même une fois mergés — sans lui, aucune consultation d'offre ne peut jamais faire bouger le badge, peu importe le reste.
- **Le backend arbitre, jamais le cache local** : `seenIds` gardait jusqu'ici le double rôle d'affichage instantané *et* de garde définitive contre un nouvel envoi — un échec silencieux (CORS ou autre) devenait donc permanent et invisible. L'effet de réconciliation retire ce second rôle : `localStorage` reste utile pour l'UX immédiate, mais seul `is_new` du backend décide si une tentative doit être refaite.
- **`match_count` et `unseen_count` partagent le même `zone_condition`** plutôt que deux conditions construites séparément : un seul appel à `commune_zone_condition()`, moins de risque de désynchronisation entre les deux compteurs si la logique de zone évolue.
- **`true()` comme condition neutre plutôt qu'un branchement de requête séparé** : évite de dupliquer la construction du `select(...)` selon que la zone soit vide ou non — un seul chemin de code, la même sous-requête dans tous les cas.
- **Renommage `_commune_zone_condition` → `commune_zone_condition` sans déplacer le fichier** : `cv.py` importe la fonction directement depuis `routers.matches` plutôt que de créer un nouveau module partagé — la fonction reste à un seul endroit, `routers/` est déjà un package important en absolu ailleurs dans les tests (`from routers.matches import ...`).
- **Rafraîchir après le succès du PATCH, pas de façon optimiste** : même raisonnement que `zoneVersion` en PR #156 — éviter de redemander `GET /cv/` avant que `seen_at` soit committé, ce qui redonnerait l'ancien `unseen_count`.

---

## PR #158 — feat: expérience/informations complémentaires sur /profile, blend du score par intention, suppression de compte

**Date :** 2026-07-07
**Branche :** `feature/profile-experience-search-fields` → `dev`

### Contexte

Trois chantiers distincts sur `/profile`, cadrés séparément avec Claude Cowork puis regroupés dans une seule branche/PR à la demande de l'utilisateur (fichiers frontend fortement partagés entre les trois — `page.tsx` en particulier — ce qui aurait produit des conflits de rebase inutiles entre plusieurs petites PR).

**Champs Expérience / Informations complémentaires.** `/profile` n'exposait jusqu'ici que la zone de communes peinte sur carte (`commune_codes`, PR #153). Décision actée avec l'utilisateur : le niveau d'expérience est un **signal souple**, pas un filtre dur — aucune colonne ajoutée sur `offers`, aucune capture du champ expérience de l'API France Travail. La recherche/description du candidat influence le score via un **embedding**, pas via un jugement LLM par offre — le blend reste dans le modèle batch actuel de `agents/matching/main.py` (pas de coût LLM par paire). Un champ « Formulez votre recherche » (`search_query`) a été ajouté puis entièrement retiré en cours de PR (voir Décisions techniques) ; seul `candidate_description` (rebaptisé « Informations complémentaires ») subsiste aux côtés d'`experience_level`.

**Piège corrigé avant qu'il ne devienne réel** : `PUT /profile` faisait un remplacement complet (`commune_codes` par défaut `[]`). Avec `/profile` qui envoie désormais `{experience_level, candidate_description}` sans `commune_codes`, et la page d'accueil qui peint des zones sans connaître ces nouveaux champs, les deux pages qui écrivent sur le même profil se seraient mutuellement écrasées. `PUT /profile` est passé en **update partiel réel** (`model_dump(exclude_unset=True)`) avant l'ajout des nouveaux champs, pas après.

**Nom du compte et suppression de compte.** Indépendant du chantier ci-dessus. Affichage du nom (`useMsal().accounts[0].name`, déjà utilisé par `AuthButton.tsx`) — aucune nouvelle donnée. Suppression de compte : droit à l'effacement RGPD (Art. 17), cohérent avec l'argument RGPD déjà documenté dans `ADR-011-user-authentication.md`. Scope v1 volontairement limité aux données applicatives (CVs, profil, matchs) — ne révoque pas l'identité Microsoft Entra External ID, pas d'appel Microsoft Graph API. `routers/cv.py:delete_cv` supprimait déjà correctement un CV (blobs Azure, matchs liés, purge `rome_codes`) ; cette PR en extrait la logique dans un helper réutilisable pour supprimer tous les CVs d'un compte dans une seule transaction.

**Refonte visuelle de `/profile`.** Design handoff fourni par l'utilisateur (`Profil candidat.dc.html`, prototype hi-fi couleurs crème + accent vert) — recréé en respectant les patterns existants du projet plutôt que copié tel quel : le système de thème dark/light du site (tokens CSS, toggle) devait continuer à fonctionner (contrairement au prototype, qui imposait un rendu clair fixe), et l'accent du site est bleu partout ailleurs (le vert du handoff est réservé aux badges de nouveaux matchs dans la bibliothèque) — le handoff a donc été traduit en nouveaux tokens de thème plutôt qu'en couleurs codées en dur, avec plusieurs itérations de rendu directement pilotées par retour visuel de l'utilisateur (carte → suppression du look carte → bande blanche + fond crème → couleur crème ajustée en `rgb(245,245,245)` → bouton Accueil en pilule fantôme).

### Ce qui a été fait

**Backend :**
- `shared/models.py` : `UserProfile` gagne `experience_level` (String, 3 valeurs : `"0-2"`/`"2-5"`/`"5+"`), `candidate_description` (Text, max 1000 caractères côté Pydantic), `intent_embedding` (`Vector(1536)`, jamais exposé dans `ProfileOut` — même traitement que `CV.embedding`/`Offer.embedding`).
- `migrations/versions/016_add_profile_experience_candidate_intent.py` : ajoute les 3 colonnes (nullable, pas de `server_default`). Migration unique et propre — un aller-retour intermédiaire ajoutant puis retirant `search_query` (voir Décisions techniques) a été consolidé avant merge, la branche n'ayant jamais été poussée ni déployée.
- `agents/webapp/schemas.py` : `ProfileUpdate` — tous les champs défaultent à `None` (jamais `[]`/`{}`) pour que `exclude_unset=True` distingue un champ absent d'un champ envoyé vide. `ProfileOut` gagne les mêmes champs (hors `intent_embedding`).
- `agents/webapp/routers/profile.py` : `put_profile` réécrit en update partiel réel ; `_build_intent_text` combine expérience (texte mêlant mot-clé métier « junior/confirmé/senior » et tranche d'années, pour matcher les deux formulations utilisées dans les offres) et description candidat, recalculé uniquement quand au moins un des deux champs est présent dans la requête ; `PUT {}` passe par `on_conflict_do_nothing` plutôt qu'un `set_` vide.
- `shared/config.py` / `agents/matching/main.py` : `INTENT_EMBEDDING_WEIGHT` (défaut 0.3) pondère `intent_embedding` face à `cvs.embedding` dans `_get_all_matches`, via une CTE (évite de dupliquer l'expression `CASE` entre `SELECT` et `WHERE`). Profils sans `intent_embedding` retombent sur le score CV-seul (`LEFT JOIN`).
- `agents/webapp/routers/cv.py` : logique de `delete_cv` extraite dans `_delete_cv(session, cv, user_id)`, sans `session.commit()` interne (le commit reste à la charge de l'appelant). `delete_cv` (route existante) devient fetch + 404 + `_delete_cv` + commit — refactor pur, comportement observable inchangé.
- `agents/webapp/routers/profile.py` : nouvelle route `DELETE /profile` — supprime tous les CVs du compte via `_delete_cv` puis la ligne `UserProfile`, dans une seule transaction. Idempotent (aucun CV, aucun profil → 204 quand même).

**Frontend :**
- `app/profile/page.tsx` : retrait de `CommuneZonePicker` (reste monté sur la page d'accueil, inchangé) ; nouveau bloc identité (avatar avec initiales, nom du compte, micro-label « Mon profil ») ; toggle Expérience à 3 boutons (label + sous-libellé année, désélectionnable — signal souple) ; textarea Informations complémentaires (1000 caractères, compteur) ; bouton Enregistrer avec état « Enregistré ✓ » qui se réinitialise à toute modification d'un champ ; section Zone de suppression montant `DeleteAccountSection`. Lien « ← Accueil » restylé en pilule fantôme (bordure, chevron net, hover, hauteur identique au badge compte `AuthButton`).
- `_components/ExperienceToggle.tsx`, `_components/InfoTooltip.tsx`, `_components/DeleteAccountSection.tsx` (nouveaux) : toggle à 2 lignes par bouton ; tooltip accessible au clavier (hover **et** focus, pas hover seul), positionné coin-à-coin avec l'icône « ? », fond opaque ; section de suppression autonome (état d'ouverture/confirmation, modale `role="dialog"`, `DELETE /profile` puis `logoutRedirect()` en cas de succès, message d'erreur sans fermer la modale en cas d'échec).
- Tokens de thème (`lib/theme/types.ts`, `themes/dark.ts`, `themes/light.ts`, `globals.css`, `tailwind.config.ts`) : `--bg-profile-page`, `--bg-profile-surface`, `--border-profile`, `--text-profile-muted`, `--bg-profile-destructive-hover` — valeurs claires ajustées itérativement avec l'utilisateur (fond page `rgb(245,245,245)`, surfaces blanches), valeurs sombres identiques aux tokens génériques existants (le handoff ne définit aucune variante sombre).
- `lib/api/types.ts` : `ProfileData` gagne `experience_level`/`candidate_description`.

**Tests :**
- `test_webapp_profile.py` : partial update (commune seul n'affecte pas l'intention et vice-versa), recalcul d'`intent_embedding` par bucket d'expérience, `PUT {}` idempotent, dépassement de 1000 caractères → 422, et une classe `TestDeleteAccount` (idempotent sans CV, appelle `_delete_cv` une fois par CV, 500 sur erreur DB).
- `test_webapp_cv.py` : suite existante inchangée (refactor `_delete_cv` transparent).

### Décisions techniques

- **`search_query` ajouté puis entièrement retiré du produit** : un champ « Formulez votre recherche » distinct d'« Informations complémentaires » a été implémenté (backend + frontend + tests), puis retiré à la demande de l'utilisateur — suppression complète plutôt qu'un simple retrait de l'UI (colonne, migration de suppression, schémas, route, tests), cohérent avec la règle du projet de ne jamais laisser de code mort. Les deux migrations (ajout puis suppression de la colonne) ont été consolidées en une seule avant le nettoyage final des commits, la branche n'ayant jamais quitté la machine locale.
- **`PUT /profile` en update partiel réel avant l'ajout des nouveaux champs, pas après** : ordonnancement délibéré des commits — le correctif anti-écrasement devait exister avant que deux pages (accueil et profil) ne se mettent effectivement à écrire des sous-ensembles disjoints du même profil.
- **Accent bleu, pas vert** : le handoff de design proposait un accent vert générique (couleur de marque par défaut du template), mais le vert est déjà un signal sémantique précis dans l'app (badge de nouveaux matchs) — réutiliser le bleu déjà établi (`bg-solid-primary`, `text-accent`, `border-accent`) évite un conflit de sens plutôt que d'introduire une seconde couleur d'accent.
- **Tokens de thème dédiés plutôt que couleurs codées en dur** : le handoff imposait un rendu clair fixe (fond crème indépendant du thème actif) — contraire à la convention du projet et au fonctionnement du reste du site. Les couleurs du handoff ont été portées dans de nouveaux tokens `--bg-profile-*`/`--border-profile`/`--text-profile-muted`, avec une valeur claire fidèle au handoff (ajustée ensuite par l'utilisateur) et une valeur sombre reprenant les tokens génériques existants — `/profile` respecte le toggle dark/light comme le reste de l'app.
- **`_delete_cv` sans commit interne** : laisse `delete_account` committer une seule fois pour l'ensemble du compte plutôt qu'une fois par CV — évite un état partiellement supprimé si une erreur survient au milieu d'une boucle sur plusieurs CVs.
- **Pas de saga / transaction compensatoire pour les blobs Azure**, à l'échelle du compte entier : même trade-off déjà assumé pour `delete_cv` (PR antérieure) — un blob supprimé avant un `commit()` qui échouerait ensuite reste supprimé, accepté tel quel plutôt que de complexifier avec une logique de compensation.
- **Nettoyage de branche en 6 commits atomiques** avant ouverture de la PR : `git reset --soft` sur `origin/dev` puis recommits ciblés par fichier/concern (champs profil, blend matching, refactor `_delete_cv`, route `DELETE /profile`, tokens de thème, page + composants frontend) — même technique que PR #155, l'historique linéaire de plus de 25 commits (itérations de copy, de couleurs, de layout) n'apportant aucune valeur de revue une fois le résultat final connu.

---

## PR #159 — feat(frontend): redesign de la bibliothèque — grille, en-tête, bouton de suppression, indicateurs de scroll

**Date :** 2026-07-07
**Branche :** `feature/library-redesign` → `dev`

### Contexte

La bibliothèque utilisait une grille figée (`grid-cols-5`, cartes compactes), sans mise en avant du CV actuellement affiché dans le détail et sans moyen d'ajouter un CV directement depuis la page. Le bouton de suppression sur chaque carte cumulait plusieurs défauts visuels remontés en revue : icône générique rognée par le bord de la carte au repos, fil de connexion carte→poubelle mal attaché, aucun lien visuel entre la poubelle et les boutons annuler/confirmer, et un bref chevauchement où le bouton apparaissait par-dessus la carte au clic avant d'avoir fini de se déplacer.

### Ce qui a été fait

**Grille et en-tête (`LibrarySection.tsx`) :**
- Grille remplacée par `grid-template-columns: repeat(auto-fill, minmax(180px,1fr))` à lignes de hauteur fixe (352px), au lieu du `grid-cols-5` figé.
- Nouveau slot « Ajouter un CV » dans la grille — bouton pointillé qui scrolle vers `#home` (nouvel `id` sur `HomeMapSection`) puis ouvre le sélecteur de fichier, upload direct sans quitter la bibliothèque.
- Carte du CV actuellement affiché en détail mise en évidence (`selectedCvId` remonté depuis `HomeClient`, bordure et halo accentués sur `CVCard`).
- En-tête (titre, description, compteur « CV IMPORTÉS x/10 ») sorti du flux normal (`absolute`) : son espacement vertical n'affecte plus la position de la grille en dessous, qui reste centrée dans toute la section quelle que soit la hauteur de l'en-tête.
- Compteur « x / 10 » recoloré pour matcher le libellé « CV IMPORTÉS » (même gris, au lieu d'un blanc plus soutenu).
- Ajout de deux indicateurs de scroll animés, sur le modèle de « CARTE »/« BIBLIOTHÈQUE » déjà présents sur l'accueil : « ACCUEIL » en haut (flèche `⌃`) et « CORRESPONDANCES » en bas (flèche `⌄`).
- Distance flèche↔bord de section réduite de moitié (36px → 18px) sur les 4 indicateurs concernés (accueil et bibliothèque), et alignée sur celui de `CVDetailSection` (spacer réduit de 6px à 3px) — écart flèche↔bord désormais cohérent partout ; l'écart flèche↔libellé (`gap-1`) l'était déjà.

**Cartes de la grille (`CVCardOptimistic.tsx`, `CVCardPlaceholder.tsx`, `CVCardSkeleton.tsx`) :** layout aligné sur le nouveau format de carte (coins `14px`, padding `9px`, zone d'aperçu en `flex-1`) pour rester visuellement cohérentes avec `CVCard` dans la nouvelle grille.

**Bouton de suppression (`CVCard.tsx`) :**
- Icônes remplacées par `lucide-react` (`Trash2`, `X`, `Check`) à la place des SVG faits main.
- Correction du rognage de l'icône au repos : mesure en conditions réelles (DOM rects) a montré que l'icône (14px) a besoin de 20px de dégagement sous la carte pour ne pas être coupée par son bord (6px de marge fixe + 14px de hauteur), alors que le palier de repos ne sortait que de 14px. Tous les paliers de révélation (repos, survol carte, survol icône, armé) relevés en conséquence.
- Ajout de fils de connexion horizontaux entre la poubelle et les boutons annuler/confirmer (seul le fil vertical carte→poubelle existait auparavant), avec les mêmes animations d'apparition/disparition. Les fils touchent maintenant réellement les boutons (l'espacement de la rangée flottait autour d'eux auparavant) ; épaisseur uniforme à 1px sur les trois fils.
- Correction d'un chevauchement visuel au clic : le bouton passait au-dessus de la carte (`z-index`) instantanément, avant d'avoir fini son changement de forme/position (~300ms), et apparaissait donc brièvement par-dessus l'aperçu du CV. Le passage au-dessus est désormais différé (`transition-delay` sur `z-index`) jusqu'à la fin du mouvement, uniquement à l'armement — l'annulation reste immédiate, ce qui est correct pour que le bouton se rétracte bien derrière la carte.
- Animation de retour après annulation accélérée ×2 (délai de fermeture 240ms→120ms, animations de sortie 0.16s→0.08s, morph du bouton 300ms→150ms au retour uniquement — l'armement garde sa vitesse d'origine).

**Tests :** `LibrarySection.test.tsx` (nouveau, couvre la grille et le slot d'ajout). `CVCard.test.tsx` mis à jour pour refléter que le bouton reste monté en permanence (visibilité pilotée par le parent) et que l'annulation joue une animation de fermeture avant de revenir à l'état idle.

### Décisions techniques

- **En-tête en `absolute` plutôt qu'en flux** : découplé de la grille, qui restait auparavant dans le même `flex-col` — chaque ajustement de l'espacement de l'un déplaçait l'autre alors que les deux ont été itérés indépendamment.
- **Seuil de révélation du bouton poubelle dérivé de la géométrie réelle** plutôt qu'ajusté à l'oeil : mesuré directement via les DOM rects de la carte réelle en conditions réelles, après plusieurs itérations à l'aveugle infructueuses.
- **`z-index` différé uniquement à l'armement, jamais à la fermeture** : dissymétrie volontaire — passer au-dessus de la carte doit attendre que le bouton l'ait quittée (sinon chevauchement visible), mais repasser en dessous doit rester immédiat pour que le bouton se cache correctement derrière elle en se rétractant.

---

## PR #161 — feat(webapp): redéclencher le matching quand les champs d'intention du profil changent

**Date :** 2026-07-08
**Branche :** `feature/profile-intent-rematch` → `dev`

### Contexte

Depuis la PR #158, le niveau d'expérience et les informations complémentaires du profil alimentent un `intent_embedding` qui pondère le score de matching. Mais modifier ces champs ne relançait aucun matching : les scores affichés restaient calculés avec l'ancienne intention jusqu'au prochain run planifié (fetch d'offres quotidien) ou au prochain upload de CV. L'utilisateur qui affinait sa description ne voyait aucun effet immédiat sur ses correspondances.

Le déclencheur existait déjà côté pipeline : l'agent `cv_analysis` envoie un message `offer-ready` une fois les codes ROME extraits, et l'agent matching consomme cette queue pour re-scorer toutes les paires CV×offre. Il suffisait de brancher `PUT /profile` sur le même mécanisme.

### Ce qui a été fait

**Backend (`agents/webapp/routers/profile.py`) :**
- `put_profile` détecte un changement réel d'intention : les valeurs résolues d'`experience_level` et `candidate_description` (champ présent dans la requête, sinon valeur de la ligne existante — même résolution que le recalcul d'embedding) sont comparées aux valeurs stockées. La ligne existante étant déjà chargée pour recalculer l'`intent_embedding`, la détection ne coûte aucune requête supplémentaire.
- Si au moins une des deux valeurs diffère, un message `offer-ready` est envoyé **après le commit** — le matching doit voir le nouvel `intent_embedding` en base quand il s'exécute. Payload au même schéma que le trigger `cv_analysis` (`run_date`, `rome_codes: []`, compteurs à 0) avec `trigger: "profile_update"` ; l'agent matching ne lit que `run_date`, aucun changement de son côté.
- Envoi extrait dans un helper `_dispatch_offer_ready` (fire-and-forget) : une `ServiceBusError` est loguée (`profile_put_offer_ready_failed`) mais ne fait jamais échouer la requête — le profil est déjà committé et le prochain run planifié rattrapera le nouvel embedding. Même pattern que le trigger d'analyse dans `cv.py:upload_cv`.
- Un PUT sans changement réel (mêmes valeurs renvoyées) ou ne touchant que `commune_codes` ne redéclenche rien.

**Tests (`test_webapp_profile.py`) :**
- 4 nouveaux tests : dispatch sur changement d'intention (queue, `trigger`, `rome_codes` vérifiés), pas de dispatch si valeurs inchangées, pas de dispatch sur `commune_codes` seul, `ServiceBusError` au dispatch → 200 quand même.
- Fixture autouse patchant `routers.profile.send_message` — les tests existants de recalcul d'embedding déclenchent désormais le dispatch et n'auraient jamais dû atteindre Azure.

### Décisions techniques

- **Comparaison des valeurs de champs plutôt que des embeddings** : détecter le changement sur `experience_level`/`candidate_description` résolus est équivalent à comparer les `intent_embedding` (l'embedding est une fonction déterministe du texte construit) et évite de comparer des vecteurs de 1536 flottants.
- **Envoi après commit, jamais avant** : si le message partait avant le commit et que celui-ci échouait, le matching re-scorerait avec l'ancien embedding — ordre identique à celui déjà établi dans `upload_cv`.
- **Fire-and-forget plutôt qu'échec de la requête** : la mise à jour du profil est l'opération principale et a réussi ; le re-matching est une optimisation de fraîcheur dont l'échec est rattrapé par le run planifié suivant. Faire échouer le PUT aurait laissé l'utilisateur croire que son profil n'était pas sauvegardé.
- **Pas de worktree `dev` disponible** (occupé par le clone principal `job-finder`) : branche créée directement depuis `origin/dev` — résultat identique au workflow standard fetch + checkout + ff-only.

---

## PR #162 — feat: agent d'analyse IA (CV seul + paires CV↔offre), crédits d'analyse

**Date :** 2026-07-08
**Branche :** `feature/agent-analyse-cv-offres` → `dev`

### Contexte

`ADR-018` posait l'architecture de monétisation : séparer strictement le matching (pgvector, gratuit, jamais rationné) de l'analyse (GPT-4o-mini, coûteuse, toujours rationnée). L'ancien plan `cv_reviews`/`agents/cv_review/` (BACKLOG PR8, une review globale par CV basée sur le top-3 des matchs) ne permettait ni de facturer une analyse individuelle par offre ni de construire un modèle de paliers — l'ADR le remplace par une analyse par paire CV↔offre déclenchée automatiquement sur le top N courant des matchs de chaque CV, complétée par un déclenchement manuel à crédits. Un addendum du même jour a réintroduit, hors périmètre initial de l'ADR, une analyse du CV seul (structure, formulation, cohérence avec l'intention, score ATS), rattachée à l'agent `cv_analysis` existant plutôt qu'à un nouvel agent.

### Ce qui a été fait

**Backend — données (`shared/models.py`, migrations 017-019) :** deux nouvelles tables — `cv_analyses` (1 ligne par CV, statut `pending/processing/done/error`, score ATS, points forts/faibles, suggestions, cohérence) et `match_analyses` (1 ligne par match, compétences correspondantes en badges, points forts/points d'amélioration, synthèse, `triggered_by` auto/manuel) — plus `analysis_credits_remaining`/`analysis_credits_reset_at` sur `user_profiles` (`server_default=30`, rétroactif pour les bêta-testeurs déjà inscrits, cadeau de bienvenue non renouvelable).

**Backend — agent `cv_analysis` étendu :** un appel GPT-4o-mini supplémentaire à chaque upload, best-effort et isolé — un échec ne bloque jamais le pipeline ROME → matching. Gratuit, jamais gaté par des crédits. `AZURE_OPENAI_ROME_DEPLOYMENT` renommé `AZURE_OPENAI_CV_ANALYSIS_DEPLOYMENT` (le déploiement sert désormais l'extraction ROME et l'analyse qualité) — renommage corrigé en revue : un nom générique `AZURE_OPENAI_CHAT_DEPLOYMENT` partagé par convention avec l'agent `match_analysis` (chacun avec sa propre valeur Terraform indépendante, donc sans couplage réel) prêtait à confusion ; chaque Container App Job garde désormais un nom d'env var qui lui est propre.

**Backend — nouvel agent `agents/match_analysis/` :** consomme la queue `match-analysis`, compare CV et offre (compétences correspondantes, points forts/d'amélioration, synthèse orientée candidat). Match supprimé entre l'enfilement et le traitement = skip propre. Env var de déploiement `AZURE_OPENAI_MATCH_ANALYSIS_DEPLOYMENT` (renommée depuis `AZURE_OPENAI_CHAT_DEPLOYMENT` par cohérence avec `job_cv_analysis`, cf. Décisions techniques).

**Backend — `matching/main.py` :** `_enqueue_top_n_analyses` recalcule à chaque run le top `MATCH_ANALYSIS_AUTO_TOP_N` (= 1 en bêta) sur l'ensemble des matchs de chaque CV (pas seulement les nouveaux) et enfile uniquement les matchs sans analyse existante — un match qui remonte au classement est capté, un match déjà analysé n'est jamais ré-analysé automatiquement.

**Backend — API webapp :** `GET /cv/{cv_id}/analysis` (pending par défaut), `POST /cv/{cv_id}/analysis/retry` (relance gratuite de l'analyse qualité seule, sans retoucher ROME ni matching), `POST /matches/{cv_id}/offers/{offer_id}/analyze` (décrément de crédit atomique par `UPDATE ... WHERE analysis_credits_remaining >= 1`, `402` si épuisé, endpoint idempotent), `MatchOut.analysis` sérialisé sur `GET /matches`/`GET /matches/cv/{id}`, `ProfileOut.analysis_credits_remaining` exposé. `_delete_cv` nettoie `match_analyses`/`cv_analyses` avant leurs parents (FK sans CASCADE).

**Terraform + CI :** nouveau job `job-jf-dev-frc-match-analysis`, queue `match-analysis`, entrée dans `all_job_ids` (alertes), `MATCH_ANALYSIS_AUTO_TOP_N` explicite sur le job matching, build/push/deploy de l'image dans `buildAgents.yml`.

**Frontend :** onglets renommés « Matchs » → « Correspondances », « Review » → « Analyse du CV » (`CorrespondancesPanel.tsx`) — l'analyse du CV vit dans ce second onglet plutôt que sous la miniature, la miniature retrouvant son layout d'origine. `CvAnalysisCard` (score ATS, points, bouton de relance sur erreur), `MatchAnalysisPanel` remplaçant le placeholder statique de la review par offre (bouton « Analyser cette offre », badges de compétences correspondantes, synthèse + points), polling 3s sur les deux avec cleanup des timers. Nouveau `CreditsBadge` épinglé à côté du bouton de connexion (même hauteur explicite `h-8`), lien vers `/profile` qui affiche désormais le solde de crédits.

**Tests :** `test_match_analysis.py` (nouveau), extensions de `test_cv_analysis.py` (`_analyze_cv_quality`, `_upsert_cv_analysis`, `_run_quality_analysis`, branche retry de `main()`), `test_webapp_cv.py`, `test_webapp_matches.py`, `test_webapp_profile.py`, `CvAnalysisCard.test.tsx` et `CreditsBadge.test.tsx` (nouveaux), extensions de `MatchItem.test.tsx`. `_enqueue_top_n_analyses` documentée comme exclusion (SQL PostgreSQL-spécifique `ROW_NUMBER() OVER`, incompatible SQLite, même régime que `_get_all_matches`).

### Décisions techniques

- **Renommage de job non nécessaire** : `cv_analysis` assumait déjà mal son nom (extraction ROME uniquement) ; en lui ajoutant l'analyse qualité, son nom devient exact au lieu d'être ambigu — seul `match_analysis` est un agent réellement nouveau.
- **Env vars de déploiement OpenAI scopées par job** (`AZURE_OPENAI_CV_ANALYSIS_DEPLOYMENT`, `AZURE_OPENAI_MATCH_ANALYSIS_DEPLOYMENT`), pas un nom générique `AZURE_OPENAI_CHAT_DEPLOYMENT` partagé : le choix initial (nom générique volontairement partagé entre `job_cv_analysis` et `job_match_analysis`) a été signalé en revue comme un risque de régression silencieuse sur `job_cv_analysis` (renommage d'une env var lue par un agent déjà en prod). Chaque job a sa propre valeur Terraform indépendante, donc pas de couplage réel entre les deux — mais un nom partagé entre deux Container App Jobs distincts prêtait à confusion sur ce qui était effectivement renommé. Les deux jobs ont désormais un nom d'env var qui leur est propre, éliminant l'ambiguïté des deux côtés plutôt que de la limiter au job concerné par le risque de régression identifié.
- **`_analyze_match`/`_get_match_context` : deux `ValueError` distincts, pas un seul bloc `except` commun** — le retour anticipé sur match supprimé (skip propre) doit rester séparé de l'épuisement des retries JSON (doit marquer la ligne `error`), sans quoi un échec d'analyse serait silencieusement traité comme un skip et la ligne resterait bloquée en `processing` indéfiniment.
- **Validateurs Pydantic `mode="before"` sur les listes JSONB** (`CvAnalysisOut`, `MatchAnalysisOut`) : les colonnes JSONB restent `NULL` tant que l'agent n'a pas écrit une ligne `done`/`error` — sans coercition `NULL → []`, sérialiser une ligne `pending`/`processing` ferait planter `GET /matches` (500).
- **Décrément de crédit par `UPDATE` conditionnel atomique, jamais `SELECT ... FOR UPDATE`** (ADR-018 addendum) : une seule instruction SQL, aucune fenêtre de course possible, plus simple pour une décrémentation bornée sans logique conditionnelle complexe.
- **Retry de l'analyse qualité limité à la ré-analyse, pas à la réparation d'un échec ROME** : `_get_cv_text` ne dépend pas du statut global du CV, donc le retry fonctionne même si `CV.status = "error"` — mais ne corrige pas ce cas plus large (aucun retry n'existe nulle part dans l'app pour un échec d'upload complet), volontairement laissé hors périmètre.
- **`CreditsBadge` lie vers `/profile` plutôt que vers une page d'achat** : conforme à l'ADR-018, qui reporte le rachat de crédits à un flux concierge Stripe une fois la demande validée — le bouton rend visible un solde déjà existant en base sans construire de parcours d'achat.
- **Hauteur explicite (`h-8`) sur les pastilles épinglées** (`AuthButton`, `CreditsBadge`) plutôt que hauteur pilotée par le contenu : la pastille authentifiée d'`AuthButton` est plus haute que le texte seul à cause de l'avatar circulaire (24px) — sans hauteur explicite partagée, les deux contrôles épinglés étaient visuellement dépareillés.
- **Deux onglets renommés en cours de revue** (« Matchs » → « Correspondances », « Review » → « Analyse du CV ») : décision prise après la première implémentation — l'analyse du CV devait vivre dans un onglet dédié plutôt que sous la miniature, remplaçant le placeholder « offres à revoir » qui n'était qu'un texte statique sans fonctionnalité réelle.

---

## PR #164 — feat: prompt coach carrière et schéma enrichi pour l'analyse de correspondance

**Date :** 2026-07-08
**Branche :** `feature/enrich-match-analysis-prompt` → `dev`

### Contexte

Le prompt système de l'agent `match_analysis` (PR #162) était resté à sa version initiale : synthèses redondantes commençant toutes par « Cette offre est pertinente pour vous car... » et aucun des champs enrichis discutés avec Claude Cowork (ADR-018, section « prompt complet pour la review de l'offre vs CV »). Le reste de l'implémentation (migration 018, auto top-N dans `matching`, endpoint manuel à crédits) était correct et n'a pas été touché.

### Ce qui a été fait

**Migration 020 + `shared/models.py` :** 7 nouvelles colonnes nullable sur `match_analyses` — `verdict`, `company_summary`, `mission_summary`, `why_good_fit_for_user`, `why_good_candidate`, `score_explanation` (Text) et `questions_entretien_potentielles` (JSONB). Les colonnes existantes (`points_forts`, `points_amelioration`, `matched_skills`, `synthese`) gardent leur type — seule la forme des données de `points_amelioration` change (items `{constat, suggestion_concrete}` au lieu de plain strings).

**Agent `match_analysis` :** nouveau `MATCH_ANALYSIS_SYSTEM_PROMPT` — persona coach carrière du marché français, contrat JSON strict, ouverture de synthèse variée selon le point le plus marquant (jamais l'ancienne formule), règle absolue de non-invention d'informations entreprise (`company_summary: null` si l'offre ne dit rien au-delà du nom), ton bienveillant. `_get_match_context` remonte désormais `Match.score` et `_analyze_match` l'injecte dans le user content (« Score de correspondance déjà calculé : 87% ») — le modèle explique le score pgvector, il ne le recalcule pas. L'extraction du JSON est déportée dans `_parse_analysis_payload` (la fonction dépassait 40 lignes sinon) : coercition défensive `str()` avec `None` préservé sur les champs texte nullable (y compris `synthese`, corrigé en revue — l'ancien fallback `""` était incohérent avec la colonne nullable), rejet silencieux des seuls items `points_amelioration` sans `constat` — une `suggestion_concrete` absente devient `None` (corrigé en revue : exiger les deux clés jetait silencieusement une réponse partielle valide, alors que le chemin de lecture accepte déjà cette forme pour les lignes legacy).

**`MatchAnalysisOut` (webapp) — hors périmètre initial mais nécessaire :** sans adaptation, le typage `points_amelioration: list[str]` aurait fait renvoyer un 500 à `GET /matches` dès la première analyse au nouveau format (dicts). Le schéma expose les 7 nouveaux champs, et un validator `mode="before"` coerce les lignes legacy pré-020 (items plain string) vers `{constat, suggestion_concrete: null}` pour que anciennes et nouvelles lignes sérialisent pareil.

**Frontend — adaptation minimale :** `PointAmelioration` + nouveaux champs dans `lib/api/types.ts`, `MatchAnalysisPanel` rend `constat — suggestion_concrete` sur une ligne dans la liste existante. L'affichage riche des nouveaux champs (verdict, résumés mission/entreprise, questions d'entretien) relève du chantier UI-UX mené séparément.

**Tests :** `test_match_analysis.py` (payload enrichi, rejet d'items invalides, score dans le user content, `match_score` dans le contexte), `test_webapp_matches.py` (sérialisation des nouveaux champs + lignes legacy), `MatchItem.test.tsx` (nouveau format de fixture, rendu constat—suggestion).

### Décisions techniques

- **Adapter `MatchAnalysisOut` et le frontend malgré le périmètre annoncé (migration + modèle + prompt)** : laisser le typage API en `list[str]` rendait la branche inmergeable — 500 sur `GET /matches` à la première nouvelle analyse, crash React sur le rendu d'objets. Adaptation minimale des deux couches plutôt qu'un état intermédiaire cassé sur `dev`.
- **Rétro-compatibilité des lignes pré-020 par coercition côté API, pas par migration de données** : les anciens items plain string deviennent `{constat: <texte>, suggestion_concrete: null}` à la sérialisation. Pas de réécriture des JSONB existants en migration — les données restent brutes, la normalisation vit dans le schéma Pydantic, et `suggestion_concrete` est nullable côté TS pour matérialiser ce cas.
- **Un seul validator `mode="before"` pour `points_amelioration`** (NULL → `[]` + coercition legacy) plutôt que deux validators empilés : l'ordre d'exécution de deux before-validators sur le même champ est une subtilité Pydantic qu'un seul validator élimine.
- **`questions_entretien_potentielles` ajoutée au validator NULL → `[]` existant** : même régime que les autres colonnes JSONB de liste — NULL tant que l'agent n'a pas écrit une ligne `done`, et NULL définitif sur les lignes analysées avant 020.
- **Deux retours de revue déclinés, avec justification** : (1) l'asymétrie colonne nullable / défaut Pydantic `[]` sur `questions_entretien_potentielles` est exactement le régime existant de `points_forts`/`points_amelioration`, déjà documenté par le commentaire du validator — la faire diverger (colonne `default=list` façon `matched_skills`) créerait une incohérence avec la migration 020 (`NULL`) ; (2) les commentaires `//` dans le bloc JSON du prompt font partie du texte validé avec Claude Cowork — le restructurer passe par lui, et `response_format=json_object` garantit de toute façon une sortie sans commentaires.

---

## PR #163 — fix: backfill des analyses CV manquantes + timeout de réception Service Bus

**Date :** 2026-07-08
**Branche :** `fix/cv-analysis-backfill-and-receive-timeout` → `dev`

### Contexte

Deux symptômes remontés par l'utilisateur après le déploiement des PR #161 et #162 : « changer la description ne relance pas le matching » et « la review du CV reste bloquée sur "Analyse de votre CV en cours" pour mes CV déjà en place ». Session de diagnostic menée directement dans Azure (Log Analytics, files Service Bus, exécutions Container App Jobs) plutôt que dans le code seul — les trois conclusions ci-dessous en sont sorties, dont un faux positif.

**Le re-matching sur changement d'intention (PR #161) fonctionne.** Les logs de production le prouvent : à 09:36:58 UTC, la suppression d'un « . » dans les informations complémentaires a produit `profile_intent_changed (description_changed=True)` puis `profile_put_offer_ready_sent` ; le job matching a consommé le message à 09:37:10 et terminé à 09:37:39 (`matching_run_completed cvs_processed=2 new_matches=408`). Le PUT de 10:11 pointé comme « sans effet » ne contenait aucun champ d'intention (c'était l'enregistrement de zone de communes de la page d'accueil — la page profil, elle, envoie toujours les deux champs). La fonctionnalité a été perçue comme cassée car l'UI n'en montre rien : pas d'indicateur « matching relancé », pas de rafraîchissement des correspondances — noté au backlog en `[recommandé]`.

**Le blocage « Analyse de votre CV en cours » est un vrai bug de la PR #162.** Les CV importés avant cette PR n'ont aucune ligne `cv_analyses`, et le dispatch de l'analyse n'a lieu qu'à l'upload : `GET /cv/{id}/analysis` masquait l'absence de ligne en renvoyant `status="pending"`, `CvAnalysisCard` pollait toutes les 3 s un résultat qui ne pouvait jamais arriver, et le bouton « Relancer » n'apparaît que sur `error`. Aucune issue dans l'UI.

**Bug latent découvert au passage :** l'exécution matching `c1ak134` (09:48 UTC) a échoué en `DeadlineExceeded` — `receive_messages` sans `max_wait_time` bloque indéfiniment sur une queue vide, alors que le chemin « queue vide → RuntimeError » documenté dans `bus.py` suppose un retour. Cause identifiée après coup avec l'utilisateur : c'était son **rerun manuel** du job, lancé alors que la queue était vide (le message de 09:36 avait déjà été consommé par le run automatique de 09:37) — le job a pendu 5 minutes en attente d'un message inexistant, a été tué par le replica timeout et remonté **Failed**. Le même blocage frapperait une course KEDA (job déclenché pour un message consommé par un run chevauchant ou expiré vers la DLQ avant le démarrage du conteneur) ; le correctif couvre les deux cas.

### Ce qui a été fait

**Backend (`agents/webapp/routers/cv.py`) :**
- `GET /cv/{id}/analysis` devient auto-réparateur : si aucune ligne n'existe et que le CV a dépassé le pipeline d'upload (statut ∉ {pending, processing}), l'endpoint réserve une ligne `pending` puis re-dispatche un message `retry_quality_only` (helper `_backfill_cv_analysis`).
- La réservation passe par `INSERT ... ON CONFLICT DO NOTHING ... RETURNING` : avec le polling frontend à 3 s, seul le poll qui gagne l'insert dispatche — sans cette réclamation, chaque tick enverrait un nouveau message jusqu'à ce que l'agent écrive la ligne.
- Si l'envoi Service Bus échoue, la réservation bascule en `error` : l'UI affiche alors le bouton « Relancer l'analyse » au lieu d'attendre un message jamais parti.
- Rattrapage best-effort de bout en bout : toute erreur (DB ou bus) est loguée et avalée — une lecture qui a réussi ne devient jamais un 500 parce que la réparation a échoué.
- Aucun changement frontend : la carte polle déjà, elle se remplit seule au passage de l'agent (~30–60 s).

**Shared (`shared/bus.py`) :**
- `receive_message` passe `max_wait_time=RECEIVE_MAX_WAIT_SECONDS` (30 s) à `receive_messages` — le chemin « queue vide » existe désormais réellement : le job sort proprement en `no_message` au lieu de pendre jusqu'au timeout du replica.

**Matching (`agents/matching/main.py`) :**
- Question de l'utilisateur (« le job marchera sans message ? ») qui a révélé un trou dans le fix : `matching` n'attrapait pas le `RuntimeError` levé quand `receive_message` ne yield pas (queue vide) — l'exécution échouait en traceback brut, sans log expliquant la cause. D'abord aligné sur `cv_analysis`/`match_analysis` (no-op « Succeeded »), puis **décision inverse actée avec l'utilisateur** : un run matching qui n'a rien consommé n'a fait aucun matching et ne doit pas ressembler à un succès — `except RuntimeError` → `logger.error("matching_no_message_failing_run")` puis re-raise, l'exécution sort en « Failed » en ~30 s avec un log explicite (au lieu de 5 min de blocage muet). L'asymétrie avec les deux autres agents est volontaire : ce sont des workers par message où une queue vide est une course normale sans travail attendu, alors qu'un run matching est censé traiter quelque chose.

**Tests (`test_webapp_cv.py`) :** 5 nouveaux tests sur le backfill — dispatch pour un CV terminal sans ligne, aucun dispatch pendant le pipeline d'upload, réservation perdue → pas de dispatch, échec d'envoi → ligne en `error` (réponse toujours 200), erreur DB sur la réservation → toujours 200. Suite complète : 189 passed.

### Décisions techniques

- **Auto-rattrapage dans le GET plutôt qu'un script de backfill one-shot** : un script ponctuel aurait réparé les CV existants mais pas les cas futurs (crash de l'agent avant toute écriture de ligne) ; le GET se déclenche exactement quand un utilisateur regarde l'analyse, ne répare que ce qui est consulté, et ne nécessite aucune opération manuelle au déploiement.
- **Réservation en base avant dispatch, plutôt que dispatch à chaque détection** : le polling 3 s de `CvAnalysisCard` transformerait sinon chaque affichage en rafale de messages Service Bus (et d'exécutions de job KEDA) tant que l'agent n'a pas écrit sa ligne.
- **Garde sur le statut du CV (∉ pending/processing) plutôt que sur l'âge de la ligne** : pendant le pipeline d'upload, l'absence de ligne est légitime (l'agent ne l'écrit qu'en cours de traitement) — déclencher le backfill là créerait des doublons d'analyse systématiques à chaque upload.
- **`max_wait_time=30 s`** : largement suffisant pour un message réellement présent (retour immédiat), assez long pour absorber une lenteur d'authentification/connexion AMQP, très en dessous du replica timeout de 300 s qui transformait chaque course KEDA/message en exécution `Failed`.
- **Diagnostic en production avant tout code** : les deux symptômes remontés pointaient vers la PR #161 ; les logs ont montré que le premier était un faux positif (le mécanisme fonctionnait, seul le feedback UI manque) et que le second venait de la PR #162 — sans cette vérification, le correctif aurait visé le mauvais composant.


---

## PR #166 — fix(match-analysis): réduire redondance et hallucination dans le prompt de review

**Date :** 2026-07-08
**Branche :** `feature/match-analysis-prompt-qualite` → `dev`

### Contexte

Une review réelle générée par l'agent `match_analysis` (score 57 %, CV junior 0-2 ans vs poste DevOps exigeant 5 ans) a révélé six défauts de contenu : redondance du même fait (l'écart d'expérience) dans `mission`, `why_good_fit_for_user` et `score_explanation` ; explication de score auto-contradictoire ; points forts génériques sans lien avec l'offre ; lacune de compétence affirmée sans ancrage dans le CV ; conseils passe-partout ignorant le contexte de reconversion pourtant fourni en entrée ; questions d'entretien template. Cause racine du point score (diagnostic Claude Cowork) : le `match_score` est une similarité cosinus pgvector calculée sans LLM (ADR-018) — le prompt demandait au modèle d'« expliquer » un score dont il ne connaît pas la décomposition, le poussant structurellement à confabuler.

### Ce qui a été fait

Réécriture de `MATCH_ANALYSIS_SYSTEM_PROMPT` (seul changement — schéma JSON de sortie, `_parse_analysis_payload` et `_analyze_match` intacts) avec six règles :

1. **Non-redondance entre champs** — un fait marquant ne se développe qu'une fois (dans `synthese`, `score_explanation` OU `points_amelioration`), les autres champs apportent un angle différent.
2. **`score_explanation` ancré dans ce qui est su** — le score est présenté comme une similarité sémantique globale dont le modèle ne connaît pas la décomposition ; interdiction de le décomposer en poids par critère ; description qualitative cohérente avec le niveau du score (pas de signaux contradictoires non hiérarchisés).
3. **`points_forts` reliés à un besoin explicite de l'offre** — formulations généralistes interdites ; liste courte acceptée plutôt que du remplissage.
4. **Anti-hallucination étendue aux lacunes** — un `constat` d'absence de compétence exige que la compétence soit demandée par l'offre ET absente du texte du CV, jamais déduite du métier.
5. **`suggestion_concrete` personnalisée** — doit exploiter `experience_level` / `candidate_description` ; conseils passe-partout interdits sauf rattachés à un élément concret du profil.
6. **Questions d'entretien dérivées de l'analyse** — au moins une question reformule un `constat` de `points_amelioration` de cette même analyse.

Conservé tel quel : la règle absolue `company_summary` (désormais première puce du bloc « règles absolues » qui l'étend aux lacunes), la contrainte de variation d'ouverture de `synthese`, le ton coach bienveillant, le bloc JSON de sortie.

**Complément (retour de revue) :** les règles 2 et 5 étaient formulées de façon purement déclarative alors qu'elles vont contre un biais naturel du modèle (décomposer un score en pourcentages, produire des conseils de carrière génériques). Un exemple ❌/✅ de 2-3 lignes a été ajouté immédiatement après chacune de ces deux règles — exemples illustratifs génériques (pas de profil réel), ton coach conservé. Les règles 1, 3, 4, 6 et le format JSON restent sans exemple, non signalés comme à risque — l'objectif est de renforcer les deux règles fragiles sans gonfler le prompt au point de diluer l'attention sur le reste.

**Vérification :** `pytest tests/test_match_analysis.py` — 15 passed sans modification (les tests n'assertent que la forme des données). Relecture de cohérence interne du prompt : non-redondance compatible avec la consigne d'ouverture de `synthese` ; l'exemple « Match élevé (87 %) » cite le score sans le décomposer. Le test manuel recommandé (rejouer le cas junior/DevOps et juger la sortie à l'œil) reste à faire en environnement réel — LLM non déterministe, non automatisable.

### Décisions techniques

- **Correctif prompt uniquement, pas de changement de schéma ni de parsing** : les défauts sont des défauts de contenu, pas de forme — toucher `_parse_analysis_payload` aurait élargi le périmètre sans bénéfice.
- **Le calcul du score reste hors périmètre** : la séparation gratuit (matching pgvector) / payant (analyse LLM) est un choix délibéré de l'ADR-018 — le correctif aligne le discours du modèle sur ce qu'il sait réellement du score au lieu de changer le score.
- **Règles regroupées par blocs thématiques titrés** plutôt qu'une liste plate : chaque défaut observé correspond à un bloc nommé (score, redondance, ancrage, personnalisation, questions), ce qui rend le prompt auditable règle par règle lors des prochaines itérations qualité.


---

## PR #165 — feat(frontend): affichage complet de l'analyse de match enrichie

**Date :** 2026-07-08
**Branche :** `feature/match-analysis-panel-display` → `dev`

### Contexte

La PR #164 a enrichi `MatchAnalysisOut` de 7 champs (`verdict`, `company_summary`, `mission_summary`, `why_good_fit_for_user`, `why_good_candidate`, `score_explanation`, `questions_entretien_potentielles`), mais le frontend n'en faisait qu'une adaptation minimale : `MatchAnalysisPanel` n'affichait que `synthese`, `points_forts` et `points_amelioration` — ce dernier aplati en une seule ligne « constat — suggestion » (correctif posé pour ne pas planter, pas un rendu définitif). Ce chantier habille les champs manquants selon la hiérarchie d'information définie avec Claude Cowork, sans toucher au backend, aux types ni à `MatchItem.tsx`.

### Ce qui a été fait

**`MatchAnalysisPanel.tsx` :** rendu complet de l'analyse `done`, du plus glanceable au plus détaillé — `verdict` au-dessus du titre « Review de l'agent » (texte simple proéminent, `text-[15px] font-bold`), `synthese` inchangée (paragraphe encadré `bg-card`), nouvelles sections « Mission » et « Entreprise » (cette dernière conditionnelle : rien si `null`), bloc « Pourquoi ça matche » regroupant `why_good_fit_for_user` et `why_good_candidate` sous deux sous-titres courts « Pour vous » / « Pour eux », « Pourquoi ce score » en `text-muted` (justification, pas un point d'action), puis points forts / points d'amélioration, et « Questions d'entretien potentielles » avec une puce « ? » `text-accent` (différenciée des jugements ✓/•) juste avant « Compétences détectées ». Un helper local `SummarySection` et une constante `SECTION_TITLE_CLASS` factorisent les titres de section.

**`AnalysisPointsList.tsx` :** les items acceptent désormais `(string | AnalysisPoint)[]` avec `AnalysisPoint = {text, suggestion?}`. Rendu à deux niveaux : le constat en ligne principale (puce du variant parent), la `suggestion_concrete` en ligne secondaire indentée réutilisant la puce « suggestion » (→, `text-accent`) définie depuis l'origine mais jamais utilisée. `suggestion` absente ou `null` (lignes legacy pré-migration 020) → pas de ligne secondaire. Compatibilité conservée avec `CvAnalysisCard.tsx`, qui passe toujours des `string[]` simples.

**Tests (`MatchItem.test.tsx`) :** l'assertion de l'ancien aplatissement est remplacée par deux assertions séparées (constat / suggestion) ; deux tests ajoutés — rendu des champs enrichis (dont l'absence de la section « Entreprise » quand `company_summary` est `null`) et lignes legacy sans suggestion (aucune flèche →). Suite frontend : 89 passed, tsc et ESLint sans erreur.

### Décisions techniques

- **Verdict en texte simple, sans code couleur sémantique** : `verdict` est un TEXT libre, pas un enum — un mapping couleur fiable demanderait un champ structuré côté backend qu'on n'a pas encore.
- **Pas de divulgation progressive** : avec des paragraphes courts et des sections conditionnelles, la carte reste lisible tout affiché — le repli au-delà des points forts/amélioration (option laissée ouverte par le brief) reste envisageable si le contenu réel s'avère plus dense.
- **Extension d'`AnalysisPointsList` par union de type plutôt qu'un nouveau composant** : `typeof item === "string"` normalise en interne, le rendu deux niveaux réutilise la puce « suggestion » existante, et l'appelant `CvAnalysisCard` reste inchangé.
- **Aucune section placeholder pour les champs `null`** : le prompt agent (PR #164) impose `company_summary: null` quand l'offre ne dit rien de l'entreprise — afficher un texte de remplacement suggérerait un manque là où l'IA a correctement refusé d'inventer.


---

## PR #167 — fix(match-analysis): ancrer suggestion_concrete dans le profil avec un exemple entrée→sortie

**Date :** 2026-07-08
**Branche :** `feature/match-analysis-rule5-personnalisation` → `dev`

### Contexte

Troisième itération sur la règle 5 (`suggestion_concrete` personnalisée) de `MATCH_ANALYSIS_SYSTEM_PROMPT`. La comparaison de deux reviews réelles avant/après le fix few-shot de la PR #166 a montré une correction de surface seulement : les formulations exactement bannies par l'exemple ❌ (« stage ou alternance », « cours ou certifications ») ont disparu, mais les nouvelles suggestions (« suivre une formation », « participer à des projets open source ») restent tout aussi génériques et n'exploitent toujours pas l'intention du candidat. Diagnostic (Claude Cowork) : le modèle a évité les mots interdits sans intégrer le principe — l'exemple ✅ ne montrait qu'une sortie plausible, pas le lien entrée→sortie, donc le modèle n'avait qu'un style à imiter, pas un mécanisme à reproduire. Cas limite découvert au passage : la règle ne disait rien sur quoi ancrer la suggestion quand l'intention est vide (fallback « Aucune intention renseignée par l'utilisateur. »).

### Ce qui a été fait

Réécriture du seul bloc « SUGGESTIONS PERSONNALISÉES » (règles 1, 2, 3, 4, 6 et format JSON intacts) :

- **Mécanisme explicite et obligatoire** : avant d'écrire `suggestion_concrete`, identifier un élément concret et vérifiable dans l'intention du candidat (projet nommé, certification, technologie mentionnée) ; la suggestion doit citer explicitement cet élément.
- **Chaîne de repli quand l'intention est vide** : ancrer sur le texte du CV en priorité, puis sur un point précis de l'offre (description ou compétences demandées) en dernier recours — jamais un conseil de carrière générique par défaut.
- **Exemple entrée→sortie complet** à la place de l'exemple de sortie seule : l'intention en entrée est montrée (« Reconversion Unity vers Cloud/Azure, certification AZ-104 obtenue, projet Terraform personnel en cours »), puis le ❌ (générique, ignore l'intention) et le ✅ (cite l'élément trouvé dans l'intention) — le modèle voit le lien de cause à effet.

**Vérification :** `pytest tests/test_match_analysis.py -v` — 15 passed sans modification (aucun changement de schéma JSON). Le test manuel reste à faire : rejouer le cas profil Cloud/Azure/AZ-104 vs offre Java/JEE/TensorFlow et vérifier que `suggestion_concrete` référence un élément identifiable du profil.

### Décisions techniques

- **Le prompt référence les libellés que le modèle voit réellement** (« Intention du candidat », le texte exact du fallback, « CV », « description ou compétences demandées ») plutôt que les noms de variables internes (`candidate_description`, `cv_text`) — le modèle ne voit jamais ces noms dans le message utilisateur construit par `_analyze_match`.
- **Garde-fou d'itération acté** : si la sortie reste générique après ce changement, ne pas re-itérer sur le few-shot une troisième fois — vérifier d'abord que `candidate_description` est effectivement rempli en base pour le profil testé (le problème serait alors une donnée d'entrée manquante, pas un problème de prompt).


---

## PR #168 — feat(frontend): pagination de la liste des correspondances (20 offres par page)

**Date :** 2026-07-08
**Branche :** `feature/matches-pagination` → `dev`

### Contexte

La page des correspondances affichait toutes les offres d'un CV en une seule liste défilante. Toutes les correspondances étant déjà chargées côté client par le parent (`HomeClient` → prop `matches`), une pagination purement client suffit — aucun changement backend.

### Ce qui a été fait

- **Nouveau composant `PaginationBar`** (`app/_components/`) : numéros de pages fenêtrés (première/dernière toujours visibles, ±1 autour de la page courante, ellipse pour les trous), boutons Précédent/Suivant, `aria-current="page"` sur la page active, tokens de thème uniquement. Rendu `null` quand il n'y a qu'une seule page.
- **Découpage dans `CorrespondancesPanel`** : la liste filtrée/triée est tranchée par pages de 20 (`PAGE_SIZE`), la pagination s'applique donc après recherche, filtres et tri. Le changement de page fait remonter le panneau en haut (`scrollTo` sur le conteneur défilant).
- **Tests** : 4 nouveaux cas dans `CorrespondancesPanel.test.tsx` (tranche de la première page, navigation page 2, barre masquée à ≤ 20 offres, retour page 1 au changement de tri).

**Vérification :** `tsc --noEmit`, `next lint` et `jest` — 93 passed (89 existants + 4 nouveaux).

### Décisions techniques

- **Reset vs clamp** : la page revient à 1 quand l'utilisateur redéfinit l'ensemble visible (recherche, filtres, tri, changement de CV) — via un `useEffect` dédié ; mais quand la liste rétrécit sur place (offre rejetée depuis la dernière page), la page est seulement bornée (`Math.min(page, totalPages)`) pour garder l'utilisateur au plus près de là où il était.
- **Pagination client, pas serveur** : l'endpoint `/matches/cv/{id}` renvoie déjà la liste complète et le tri/filtrage est local ; paginer côté serveur aurait cassé la recherche instantanée et le tri sans bénéfice à l'échelle actuelle (dizaines d'offres). À revisiter si le volume par CV dépasse quelques centaines.
- **`Element.prototype.scrollTo` mocké dans les tests** : jsdom n'implémente pas `scrollTo` sur les éléments — mock global dans `beforeAll` plutôt qu'une garde dans le composant.


---

## PR #169 — feat: recharge de crédits admin (+10) contrôlée par ADMIN_USER_IDS

**Date :** 2026-07-08
**Branche :** `feature/admin-credits-refill` → `dev`

### Contexte

Les 30 crédits d'analyse offerts à l'inscription (ADR-018) ne sont pas renouvelables et aucun flux d'achat n'existe. Besoin d'une échappatoire réservée au compte propriétaire du projet : un bouton « +10 crédits » sur la page profil, invisible et inaccessible pour tout autre utilisateur.

### Ce qui a été fait

- **Backend** : variable d'environnement `ADMIN_USER_IDS` (claims `sub` JWT séparés par des virgules, vide = aucun admin) parsée dans `auth.py` ; helper `is_admin()` et dépendance FastAPI `get_current_admin_user` (403 pour les non-admins). Nouvel endpoint `POST /profile/credits/refill` : +10 crédits sur le profil de l'admin lui-même via un `UPDATE … RETURNING` atomique (même motif que le décrément de `request_match_analysis`), 404 si aucun profil. `GET/PUT /profile` exposent désormais `is_admin`.
- **Frontend** : composant `AdminRefillButton` dans la carte crédits de `/profile`, rendu uniquement si `is_admin` ; met à jour le solde affiché depuis la réponse et notifie le bus crédits pour rafraîchir le `CreditsBadge` du header.
- **Terraform (couche app uniquement)** : variable `admin_user_ids` (défaut `""` = fonction désactivée) câblée en env var `ADMIN_USER_IDS` sur le Container App webapp. `python/.env.example` documente la variable pour le dev local.

**Vérification :** pytest — 198 passed (9 nouveaux : flag is_admin, 403 non-admin, refill nominal, 404, 500) ; frontend — 91 passed (2 nouveaux), `tsc --noEmit` et `next lint` propres ; `terraform fmt -check` propre (validate en CI).

### Décisions techniques

- **Autorisation par env var plutôt que colonne `is_admin` en base** : un seul admin prévu, pas de flux de gestion d'admins — une migration + du SQL manuel seraient de la complexité sans bénéfice. L'env var est versionnée dans Terraform et auditable.
- **Env var en clair, pas un secret** : les valeurs sont des GUID Entra opaques, pas des identifiants — l'autorisation exige toujours un JWT signé valide pour ce `sub`. Même raisonnement que le split tenant/client ID déjà commenté dans `webapp.tf`.
- **`is_admin` calculé, pas persisté** : champ Pydantic avec défaut `False` surchargé via `model_copy(update=…)` dans les endpoints profile — `ProfileOut` reste `from_attributes` sans exiger de colonne DB.
- **Le backend décide, le frontend masque** : le bouton n'est qu'un confort d'affichage conditionné par `is_admin` ; la vraie barrière est la dépendance `get_current_admin_user` côté API.
- **Activation** : renseigner `admin_user_ids` avec le `user_id` renvoyé par `GET /profile` (claim `sub` du JWT) — localement via `python/.env`, en Azure via la variable Terraform.


---

## PR #170 — feat(webapp): persister les claims d'identité (email, display_name) dans user_profiles

**Date :** 2026-07-08
**Branche :** `feature/profile-identity-claims` → `dev` (empilée sur la PR #169)

### Contexte

Découverte en configurant `ADMIN_USER_IDS` (PR #169) : le backend ne stocke que le claim `sub` du JWT comme `user_id` — un identifiant pairwise opaque, différent de l'Object ID du portail Entra et impossible à résoudre vers un utilisateur d'annuaire (aucune API Microsoft ne le permet, c'est une propriété anti-corrélation voulue). Le nom affiché dans l'app vient du cache MSAL navigateur, jamais du backend. Conséquence : `user_profiles` était une liste de GUID anonymes, l'opérateur ne pouvait pas savoir qui est qui.

### Ce qui a été fait

- **`auth.py`** : nouvelle dépendance `get_current_identity` retournant un `UserIdentity(user_id, email, display_name)` extrait du JWT validé ; `get_current_user` devient un simple wrapper (aucun changement pour les endpoints existants). Repli sur le claim `emails` (liste, style B2C) quand `email` est absent.
- **Migration 021 + modèle** : colonnes nullable `email` / `display_name` sur `user_profiles` — nullable car le user flow Entra peut ne pas émettre ces claims dans l'access token.
- **Écriture** : l'upload CV (création du profil) capture les claims ; `PUT /profile` les rafraîchit à chaque appel, mais uniquement quand ils sont présents dans le jeton — un jeton sans claims n'écrase jamais des valeurs stockées.

**Vérification :** pytest — 205 passed (7 nouveaux : extraction des claims dans `test_webapp_auth.py`, rafraîchissement upsert + non-écrasement dans `test_webapp_profile.py`).

### Décisions techniques

- **Métadonnées opérateur uniquement** : jamais utilisées pour l'autorisation, absentes de toute réponse API (`ProfileOut` inchangé), jamais loggées (même règle que `candidate_description`), effacées avec le profil par `DELETE /profile` (droit à l'effacement).
- **Rafraîchissement sur PUT, capture à la création** : un compte renommé ou un email changé converge au prochain enregistrement du profil ; `GET` ne déclenche aucune écriture.
- **Point de vigilance post-déploiement** : si `email`/`display_name` restent NULL, c'est que le user flow Entra External ID n'émet pas ces claims dans l'access token — les activer dans les application claims du user flow (ou en optional claims sur l'app registration de l'API).
- **Tests d'upsert via `_post_values_clause.update_values_to_set`** : attribut privé SQLAlchemy mais seul point d'observation du `set_` avec une session entièrement mockée ; commenté comme tel dans le test.


---

## PR #171 — refactor(webapp): factoriser default_profile_values + fix: GET /profile crée le profil au lieu de 404

**Date :** 2026-07-08
**Branche :** `feature/userprofile-defaults-refactor` → `dev` (empilée sur la PR #170)

### Contexte

Implémentation de deux prompts Claude Cowork enchaînés (`prompt-userprofile-defaults-refactor.md` puis `prompt-get-profile-creation-si-absent.md`, empilés sur la même branche comme prévu par le second) : `upload_cv` et `put_profile` — les deux endpoints qui créent paresseusement la ligne `UserProfile` au premier write authentifié — dupliquaient les valeurs par défaut d'un profil neuf. Et un bug UX : un nouvel utilisateur qui ouvre sa page profil avant tout upload de CV recevait un 404 au lieu de voir ses 30 crédits de bienvenue.

### Ce qui a été fait

- **Refactor** : nouveau module `agents/webapp/profile_defaults.py` — `default_profile_values(identity)` retourne les colonnes de base (id, user_id, email, display_name, rome_codes, crédits, created_at). Les call sites ne gardent que leurs champs propres : `commune_codes=[]` explicite dans `cv.py`, les champs du body PUT dans `profile.py`. Sémantiques d'upsert distinctes et atomicité du PUT inchangées ; `routers/matches.py` hors périmètre.
- **Fix** : `GET /profile` crée la ligne avec les défauts partagés quand elle n'existe pas (`on_conflict_do_nothing` rend la course entre deux premiers appels concurrents sûre) et ne renvoie plus jamais 404. Troisième point de création paresseuse — un one-liner grâce au helper. La création par GET capture aussi email/display_name (dépendance `get_current_identity`), et le flag `is_admin` (PR #169) est préservé dans la réponse.

**Vérification :** pytest — 206 passed ; le commit refactor n'a modifié **aucun test** (comportement observable inchangé), le commit fix remplace le test 404 par un test de création au premier GET + un test d'idempotence ; `analysis_credits_remaining=30` n'apparaît plus qu'une fois dans `agents/webapp/` ; aucun import circulaire (le module ne dépend que d'`auth`).

### Décisions techniques

- **Écart assumé vs le prompt** : le prompt (rédigé avant la PR #170) spécifiait `default_profile_values(user_id: str)` et citait la capture email/nom comme motivation *future*. Cette fonctionnalité étant livrée (#170), le helper prend le `UserIdentity` et inclut `email`/`display_name` — les laisser aux deux call sites aurait conservé exactement la duplication que ce refactor supprime.
- **`created_at` généré dans le helper** (au lieu du `now` externe des call sites) : chaque site capturait déjà son propre `now` juste avant l'upsert, aucune précision temporelle observable perdue — anticipé par le prompt.
- **Empilement de PR** : merge dans l'ordre #169 → #170 → #171.


---

## PR #172 — feat(cv-analysis): synthèse en prose + règles de non-redondance/ancrage dans CV_QUALITY_SYSTEM_PROMPT

**Date :** 2026-07-08
**Branche :** `feature/cv-analysis-qualite-review` → `dev`

### Contexte

Implémentation du prompt Claude Cowork `prompt-cv-analysis-qualite-review.md` : l'analyse qualité de CV produite par l'agent `cv_analysis` souffrait des mêmes défauts déjà corrigés sur `match_analysis` — un même fait répété jusqu'à trois fois entre `points_faibles` et `suggestions`, des points génériques applicables à n'importe quel CV ("structure claire avec des sections bien définies"), et un format tout en listes à puces là où l'utilisateur attend la lecture d'ensemble d'un vrai coach.

### Ce qui a été fait

- **Modèle + migration 022** : colonne `synthese` (Text, nullable) sur `cv_analyses` — le paragraphe de synthèse (3 à 5 phrases, ton coach) écrit par l'agent ; nullable car les analyses antérieures n'en ont pas.
- **`CV_QUALITY_SYSTEM_PROMPT` réécrit** : format JSON documenté champ par champ, et les règles validées sur `match_analysis` avec leurs exemples few-shot ❌/✅ dès la première version (l'historique de `match_analysis` a montré que la règle déclarative seule ne suffit pas) — non-redondance (chaque fait une seule fois dans toute la réponse), ancrage dans un élément identifiable de CE CV, suggestions personnalisées à l'intention du candidat, interdiction de décomposer `ats_score` en points inventés.
- **Chaîne API → UI** : `synthese` parsée dans `_analyze_cv_quality` (persistée sans changement via `**result`), exposée dans `CvAnalysisOut` (backend + types frontend), affichée dans `CvAnalysisCard` entre le score ATS et les listes de points — la lecture d'ensemble précède le détail. Même style et même garde d'affichage que `coherence_intention`.
- **Correction doc au passage** : quatre références obsolètes à `POSTGRESQL_CONNECTION_STRING` (`.env.example`, `alembic.ini`, docstring et message d'erreur de `migrations/env.py`) alors que tout le code lit `DATABASE_URL` — un `.env` rempli depuis l'exemple plantait à l'import.

**Vérification :** pytest `test_cv_analysis.py` + `test_webapp_cv.py` — 72 passed ; Jest `CvAnalysisCard` — 9 passed dont 3 nouveaux (synthèse rendue au-dessus des listes vérifiée par position DOM, bloc absent quand `""` et quand `null`) ; réversibilité de la migration 022 validée contre un Postgres 16 + pgvector jetable en Docker (`upgrade head` → `downgrade -1` → `upgrade head`).

### Décisions techniques

- **Écart assumé vs le prompt** : le prompt (rédigé avant la PR #170) demandait une migration `021`, déjà prise par `021_add_profile_identity.py` — la migration est `022` avec `down_revision = "021"`.
- **`synthese` distincte des listes, pas un résumé** : la règle du prompt interdit qu'un même fait apparaisse à la fois dans la synthèse et dans un point — la synthèse apporte le fil conducteur du parcours et l'impression globale, les listes le détail actionnable.
- **Aucun changement dans `_upsert_cv_analysis`** : la persistance passe par `**result`, ajouter la clé au dict retourné par `_analyze_cv_quality` suffit.
- **Tests webapp : `synthese` posée explicitement sur les MagicMock** — Pydantic rejetterait l'attribut auto-mocké (ni `str` ni `None`) au moment de la validation `from_attributes`.
- **Test manuel qualitatif en attente de déploiement** : relire une analyse générée sur le CV réel Cloud/Azure/AZ-104 — aucun fait répété entre `synthese`/`points_faibles`/`suggestions`, au moins un point ancré sur un élément nommé du CV, au moins une suggestion appuyée sur l'intention du profil.

---

## PR #174 — fix(frontend): démontage de la vue correspondances + retour accueil à la suppression du dernier CV

**Date :** 2026-07-08
**Branche :** `feature/library-empty-reset` → `dev`

### Contexte

Après suppression de tous les CVs de la bibliothèque, la vue de correspondance (`CVDetailSection`) restait montée et accessible au scroll, alors que la bibliothèque elle-même se masquait correctement. Attendu : retour à l'accueil et vue de correspondance inaccessible.

### Ce qui a été fait

- **Cause** : `LibrarySection` ne propageait la liste des CVs au parent (`onCvsChange`) que sur les fetchs — `handleCvDeleted` filtrait le state local sans notifier `HomeClient`, qui gardait une `cvList` périmée. `selectedCvId` restait donc valide et la condition `{selectedCvId && <CVDetailSection …>}` ne démontait jamais la section.
- **`LibrarySection.tsx`** : la liste `cvs` est miroitée vers le parent via un `useEffect` déclenché à chaque changement (fetchs et suppressions locales), à la place de l'appel manuel qui n'existait que dans `fetchCvs` — la copie du parent ne peut structurellement plus diverger.
- **`HomeClient.tsx`** : quand la liste se vide alors qu'un CV était sélectionné, la sélection est effacée (démonte la vue de correspondance) et un `scrollIntoView` ramène sur la section accueil (`#home`) plutôt que de laisser le scroll sur une section disparue.
- **Test de régression** : le flux réel de suppression dans `LibrarySection.test.tsx` (armer la corbeille → confirmer → `DELETE /cv/1`) vérifie que `onCvsChange` reçoit la liste vide.

**Vérification :** Jest — 99 passed (dont le nouveau test de régression) ; `tsc --noEmit` et ESLint propres.

### Décisions techniques

- **Miroir par effet plutôt qu'appel dans `handleCvDeleted`** : appeler `onCvsChange` dans l'updater de `setCvs` serait un effet de bord dans un updater (double invocation possible en StrictMode) ; l'effet sur `cvs` couvre tous les chemins de mutation présents et futurs.
- **Garde `if (selectedCvId)` avant le scroll accueil** : la liste est vide au montage initial (avant le premier fetch) — sans le garde, chaque chargement de page déclencherait un `scrollIntoView` parasite.

---

## PR #173 — refactor(frontend): analyse CV sous la vignette (accordéon) + onglets Offres/Sauvegardées

**Date :** 2026-07-08
**Branche :** `feature/cv-detail-analyse-accordeon` → `dev`

### Contexte

Implémentation du prompt Claude Cowork `prompt-cv-detail-analyse-repositionnement.md` : `CvAnalysisCard` était un onglet ("Analyse du CV") dans `CorrespondancesPanel`, à côté des correspondances — mal positionné puisque l'analyse concerne le CV, pas les offres. La colonne gauche (38 %) n'affichait que la vignette.

### Ce qui a été fait

- **`CVDetailSection.tsx`** : `CvAnalysisCard` déplacé sous la vignette dans un accordéon ouvert par défaut (`aria-expanded`/`aria-controls`, chevron rotatif) ; `max-h-[46%]` en lecture ouverte avec scroll interne — la vignette (`flex-1 min-h-0`) se rétrécit mécaniquement, sans mesure manuelle.
- **`CvAnalysisCard.tsx`** : titre "Analyse de votre CV" retiré — porté désormais par le bouton d'accordéon.
- **`CorrespondancesPanel.tsx`** : onglets renommés `Offres` (ex-Correspondances) et `Sauvegardées` (ex-Analyse du CV) ; l'onglet Sauvegardées filtre les items sur `isSaved` (bouton favori existant) ; sous-titre d'en-tête dynamique ; barre de filtres et pagination réservées à l'onglet Offres.
- **`LibrarySection.tsx`** : hint de scroll `CORRESPONDANCES` → `OFFRES`.
- **Revue** : commentaires ajoutés sur le couplage filtres/onglet Sauvegardées et sur l'intention du cap 46 % ; chevron remplacé par `ChevronDown` de lucide-react (déjà la source d'icônes ailleurs).

**Vérification :** Jest — 24 passed dont `CVDetailSection.test.tsx` (nouveau) et 3 cas "onglet Sauvegardées" ; ESLint propre.

### Décisions techniques

- **Écart vs le prompt, signalé dans la PR** : le bloc de remplacement de la zone de contenu omettait `ref={contentRef}` et `PaginationBar` — appliqué tel quel, il cassait la pagination et le lint (variables inutilisées). Conservés, pagination restreinte à l'onglet Offres.
- **Persistance de `saved` volontairement hors scope** (entrée BACKLOG séparée) : l'état reste en mémoire pure, remis à zéro au changement de CV.
- **Limitation acceptée** : les filtres Nouvelles/Vues et la pagination s'appliquent en amont du split Sauvegardées — documenté en commentaire pour éviter un "fix" non concerté.

---

## PR #175 — feat(frontend): bandeau encadrant la zone d'analyse + redimensionnement au drag

**Date :** 2026-07-08
**Branche :** `feature/cv-analysis-banner` → `dev`

### Contexte

Suite de la PR #173 : la zone d'analyse sous la vignette n'était pas visuellement délimitée (le cadre appartenait à `CvAnalysisCard`, le bandeau de titre flottait au-dessus), le plafond de 46 % était jugé trop bas, et la hauteur n'était pas ajustable.

### Ce qui a été fait

- **Cadre unique** : le wrapper de l'accordéon porte le cadre (`rounded-xl border border-faint bg-chip`) ; `CvAnalysisCard` perd le sien (doublon) et ne garde que son padding.
- **Bandeau** : bouton pleine largeur, flèche centrée en haut, titre centré en dessous, `border-b` séparant le bandeau du contenu ouvert. Flèche inversée : vers le haut repliée (déplier), vers le bas ouverte (refermer).
- **Redimensionnement au drag** : maintenir le bandeau et glisser verticalement redimensionne la zone via pointer events, borné entre `ANALYSIS_MIN_HEIGHT_PX` (140 px) et `ANALYSIS_MAX_HEIGHT_RATIO` (80 % de la colonne). Un clic sec (déplacement < 4 px) replie/déplie ; le `click` émis par le navigateur après un drag est avalé (`wasDragRef`). Hauteur choisie conservée entre replis/dépliages.
- **Hauteur par défaut = maximale** : tant qu'aucun resize manuel n'a eu lieu, la zone ouvre à `h-[80%]` (même borne que le drag max).

**Vérification :** Jest — 4 passed sur `CVDetailSection` dont 2 cas dédiés (un drag ne replie pas la zone ; un appui-relâchement immobile replie) ; ESLint propre.

### Décisions techniques

- **Pointer events plutôt que mouse/touch** : un seul jeu de handlers, `setPointerCapture` garde le drag actif hors du bandeau (optionnel — absent de jsdom, d'où l'appel gardé `?.`).
- **Seuil de 4 px** pour distinguer clic et drag — le même bouton porte les deux gestes ; `cursor-row-resize` + `touch-none`/`select-none` quand la zone est ouverte.
- **Défaut fixe plutôt qu'adapté au contenu** : pendant les états courts (analyse en cours, erreur), la zone occupe quand même 80 % avec de l'espace vide — à conditionner au statut `done` si gênant à l'usage.

---

## PR #176 — fix(analysis): température/seed fixés + analyse CV exhaustive + retrait du conseil télétravail non ancré

**Date :** 2026-07-08
**Branche :** `feature/analysis-determinism-and-depth` → `dev`

### Contexte

Implémentation du prompt Claude Cowork `prompt-analysis-determinism-and-depth.md` — trois problèmes remontés sur une review réelle après la PR #172 : score ATS variant de +10 points entre deux analyses du même CV (aucun `temperature`/`seed` fixé, température par défaut 1.0), review jugée trop superficielle (3-4 points par liste), et suggestion "ajouter une préférence télétravail" persistant alors que `candidate_description` était vide — conseil générique non ancré, et de toute façon non conventionnel sur un CV français.

### Ce qui a été fait

- **`shared/config.py`** : `ANALYSIS_TEMPERATURE` (défaut `0`) et `ANALYSIS_SEED` (défaut `42`), surchargeables par env var.
- **`agents/cv_analysis/main.py` et `agents/match_analysis/main.py`** : `temperature=`/`seed=` passés aux appels `chat.completions.create` de `_analyze_cv_quality` et `_analyze_match` — les deux agents avaient exactement le même trou.
- **`CV_QUALITY_SYSTEM_PROMPT`** : règle d'exhaustivité (relecture section par section, chaque erreur réelle relevée, pas de plafond implicite) et règle interdisant de suggérer l'ajout d'une information personnelle/préférence absente du CV et de l'intention — le télétravail se recommande en lettre de motivation ou entretien, pas dans le corps du CV.

**Vérification :** pytest — 50 passed dont 2 nouveaux tests vérifiant `temperature`/`seed` dans les kwargs de l'appel ; aucun test existant n'assertait strictement ces kwargs (vérifié au préalable comme demandé par le prompt).

### Décisions techniques

- **Écart signalé dans la PR** : l'exemple few-shot de la règle non-redondance (PR #172) montrait en ✅ "ajouter le télétravail dans l'objectif du CV" — en contradiction frontale avec la nouvelle règle. Exemple remplacé par un sujet neutre (résultats chiffrés), règle intacte.
- **`_extract_rome_codes` hors périmètre** : sa sortie est déjà validée contre le référentiel ROME, le non-déterminisme y est sans conséquence.
- **Le seed OpenAI n'est pas une garantie absolue** de déterminisme, mais combiné à `temperature=0` la variance devient marginale.
- **Vérifications manuelles restantes** : relancer 2× l'analyse d'un même CV (stabilité du score) ; confirmer en base que `candidate_description` est vide pour l'utilisateur de test — si une mention télétravail y persiste malgré la suppression côté frontend, c'est un bug `PUT /profile` distinct à signaler séparément.

---

## PR #178 — feat(cv-analysis): checklist de vérification obligatoire + few-shot chronologie dans CV_QUALITY_SYSTEM_PROMPT

**Date :** 2026-07-08
**Branche :** `feature/cv-analysis-expertise-checklist` → `dev`

### Contexte

Implémentation du prompt Claude Cowork `prompt-cv-analysis-expertise-percue.md`. Deux reviews réelles générées après le déploiement de la règle déclarative d'exhaustivité (PR #176) produisaient toujours exactement 3 points forts / 3 points faibles / 3 suggestions, et aucune n'a relevé les deux inversions de dates manifestes du CV testé (Akanea 09/2025-05/2025, LS Group 09/2024-09/2022) — exactement le type d'erreur factuelle qu'une lecture systématique doit attraper. Même leçon que sur `match_analysis` : une règle déclarative seule ne fait pas dévier gpt-4o-mini de sa taille de liste conventionnelle.

### Ce qui a été fait

Trois ajouts dans `CV_QUALITY_SYSTEM_PROMPT` (`agents/cv_analysis/main.py`), aucun changement de schéma ni de code applicatif :

- **Checklist obligatoire de 4 angles** à vérifier explicitement avant de rédiger `points_faibles`/`suggestions` — cohérence chronologique (dates inversées, trous, chevauchements), impact/formulation (quantification, verbes faibles, répétitions), structure/lisibilité, cohérence interne (compétence jamais illustrée, intitulé incohérent). Placée juste avant la règle d'exhaustivité existante, conservée telle quelle. Un angle sans problème réel ne doit pas être inventé, mais la vérification n'est jamais optionnelle.
- **Exemple few-shot sur la cohérence chronologique** (❌ généralités de style / ✅ dates inversées citées avec leur impact ATS) — la catégorie la plus objectivement vérifiable, pour ancrer concrètement ce que « vérifier » veut dire, comme pour `score_explanation` sur `match_analysis`.
- **Règle « expertise perceptible »** : voix de recruteur technique senior du domaine visé par le candidat, citation/paraphrase de la formulation exacte du CV critiquée plutôt qu'une critique abstraite, synthese donnant le sentiment d'une lecture méthodique sans formule d'ouverture générique.

**Vérification :** pytest `test_cv_analysis.py` — 34 passed, aucun test modifié (le contenu du prompt système n'est pas testé unitairement, seul le comportement de `_analyze_cv_quality` sur un JSON donné l'est).

### Décisions techniques

- **Écart mineur vs le prompt Cowork** : la règle de ton référençait l'interdiction de la formule d'ouverture générique comme « déjà proscrit plus haut », mais rien dans le prompt système ne la proscrivait explicitement — la règle ajoutée porte elle-même cette proscription au lieu d'y renvoyer.
- **Test manuel décisif en attente de déploiement** : relancer l'analyse sur le CV aux deux inversions de dates → `points_faibles` doit en relever au moins une ; vérifier que la taille des listes varie entre CVs de qualité différente. Si la review reste superficielle, le prompt a probablement atteint le plafond de gpt-4o-mini sur ce type de vérification multi-angles — tester `gpt-4o` via `AZURE_OPENAI_CV_ANALYSIS_DEPLOYMENT` (simple variable d'environnement), mais tout changement de modèle par défaut est une décision de coût à valider côté Cowork (ADR-018), pas à automatiser.

---

## PR #179 — fix(frontend): onglet Sauvegardées découplé des filtres/pagination de l'onglet Offres + signet bleu

**Date :** 2026-07-08
**Branche :** `feature/correspondances-saved-tab-fix` → `dev`

### Contexte

Implémentation du prompt Claude Cowork `prompt-correspondances-saved-tab-fix.md`. L'onglet Sauvegardées était dérivé de `items`, lui-même issu de `paginated`/`filtered` : une offre sauvegardée en page 2, ou masquée par le filtre Nouvelles/Vues, disparaissait silencieusement de l'onglet. Un commentaire documentait ce couplage comme un choix assumé — à tort. Second point : le signet coché utilisait les tokens verts des compétences matchées (`border-match bg-match-skill text-match-skill`), à passer en bleu.

### Ce qui a été fait

- **`CorrespondancesPanel.tsx`** : extraction du mapping match → `MatchItemData` dans une fonction `toItemData()`, utilisée à la fois par `items` (liste Offres paginée) et par une nouvelle liste `savedItems` construite depuis l'ensemble complet `matches` filtré uniquement sur `!rejected && saved` — indépendante de query/contrat/score/Nouvelles-Vues/pagination. `displayedItems` bascule entre les deux selon l'onglet.
- **`MatchItem.tsx`** : le signet coché passe aux tokens bleus existants `border-accent bg-accent-muted text-accent` (ceux du badge `rome_code`). Chips de compétences, bordure de carte dépliée et bouton « Sauvegardée ✓ » restent verts, hors périmètre.
- **Tests** : deux tests de régression ajoutés au describe « onglet Sauvegardées » (offre sauvegardée en page 2 visible après retour page 1 ; offre sauvegardée visible malgré son bucket Nouvelles décoché). Les trois tests existants sont inchangés.

**Vérification :** Jest 43/43, ESLint propre. Les deux nouveaux tests ont été vérifiés rouges sur le code d'avant correction (`git stash` du composant → 2 failed) — ce sont de vrais tests de régression.

### Décisions techniques

- **Hors scope, conformément au prompt** : pas de persistance de `saved` (toujours un `useState` local remis à zéro au reload) ; le bouton texte « Sauvegardée ✓ » du panneau déplié reste vert — décisions séparées à valider avec Vincent.

---

## PR #181 — feat(frontend): pagination de l'onglet Sauvegardées + barres de pagination en haut et en bas

**Date :** 2026-07-08
**Branche :** `feature/correspondances-saved-pagination` → `dev`

### Contexte

Suite directe de la PR #179, sur demande utilisateur : doter l'onglet Sauvegardées de la même pagination que l'onglet Offres, et afficher les barres de pagination en haut **et** en bas de la liste.

### Ce qui a été fait

- **`CorrespondancesPanel.tsx`** : état `savedPage` indépendant de `page` (même `PAGE_SIZE` de 20), avec clamp quand la liste rétrécit et reset au changement de CV. Le compteur du header affiche le total d'offres sauvegardées (`savedMatches.length`), pas la taille de la page courante. Un objet `pagination` sélectionne page/totalPages/handler selon l'onglet actif, et `PaginationBar` est rendue au-dessus (`mb-4`) et en dessous (`mt-5`) de `MatchList` sur les deux onglets.
- **`PaginationBar.tsx`** : prop `className` pour l'espacement dépendant de la position (le `mt-5` était codé en dur) ; se masque toujours d'elle-même quand `totalPages <= 1`.
- **Tests** : nouveau test — 25 offres sauvegardées → pagination indépendante sur Sauvegardées (page 1 en montre 20, « Suivant » révèle le reste) et header « 25 offres sauvegardées » ; tests de pagination existants adaptés à la double barre (`getAllByRole`).

**Vérification :** Jest 44/44, ESLint propre.

### Décisions techniques

- **Incident de flux git** : la PR #179 a été mergée pendant l'implémentation — le push est arrivé après le merge et a recréé la branche distante supprimée. Le commit a été cherry-pické sur une nouvelle branche `feature/correspondances-saved-pagination` basée sur `dev` à jour. La branche recréée `feature/correspondances-saved-tab-fix` reste à supprimer manuellement (`git push origin --delete`), la suppression distante ayant été refusée en mode auto.
- **État de page séparé par onglet** plutôt que partagé : changer de page sur un onglet ne perturbe pas la position de l'autre, et le clamp existant gère les listes qui rétrécissent (offre retirée des favoris en dernière page).

---

## PR #180 — feat(matching): pondération par rareté relative au corpus pour le bonus de compétences

**Date :** 2026-07-08
**Branche :** `feature/matching-corpus-relative-skills-weighting` → `dev`

### Contexte

Implémentation du prompt Claude Cowork `prompt-matching-corpus-relative-term-weighting.md`. La liste figée `shared/tech_keywords.json` (~140 termes, PR #177) est structurellement limitée au secteur tech, alors que l'application doit servir tout candidat de tout secteur. Décision de conception actée : pondérer les termes partagés CV↔offre par leur **rareté relative au corpus d'offres** (principe proche de l'IDF), sans aucune liste de vocabulaire à maintenir.

### Ce qui a été fait

- **Table `term_stats`** (migration 025 + modèle `TermStat`) : fréquence documentaire de chaque lexème français racinisé sur l'ensemble des descriptions d'offres, avec le snapshot `total_offers` et l'horodatage du calcul. PK naturelle `term` (exception documentée dans `conventions-sql.md`).
- **`offer_fetching`** : `_refresh_term_stats()` via `ts_stat()` de Postgres sur `to_tsvector('french', description)` — signature validée contre la doc Postgres 16 réelle, jamais devinée. Remplacement complet (`TRUNCATE` + `INSERT`) en une transaction, à chaque fin de run de fetch, avant l'envoi d'`offer-ready` pour que le matching déclenché voie des stats fraîches. Calcul batch uniquement, jamais à la volée pendant le matching.
- **`matching`** : le bonus de compétences devient la part de la masse de rareté de l'offre couverte par le CV — chaque lexème partagé pèse `1 - doc_frequency/total_offers`, les termes présents dans plus de `TERM_STOPWORD_THRESHOLD` (0.75) des offres sont totalement exclus (mots vides de fait, couperet net). `SHARED_TERM_BONUS_WEIGHT` (0.1) remplace `TECH_KEYWORDS_WEIGHT`. Strictement additif, plafonné à 1.0 — jamais un malus.

**Vérification (Postgres 16 réel, Docker pgvector) :** cycle upgrade/downgrade/upgrade de la migration OK ; cas synthétique cross-secteur (40 offres tech + 40 santé + 1 compta, CV infirmier + CV tech) : termes universels exclus, `terraform`/`kubernet`/`ci/cd` conservés (`CI/CD` survit comme lexème unique à la tokenisation française), bonus moyen du CV infirmier 0.032 sur la santé et 0.000 sur le tech (symétrique côté tech), jamais-un-malus vérifié sur les 162 paires, bonus exactement 0 sans terme partagé, dégradation propre avec `term_stats` vide. `pytest` 230/230.

### Décisions techniques

- **Remplacer, pas compléter** : le bonus `tech_keywords` du matching est remplacé (deux signaux conceptuellement identiques seraient redondants), mais `shared/tech_keywords.py`/`.json`, ses tests, les colonnes et l'extraction à l'ingestion/upload sont conservés intacts — leur suppression mérite une discussion dédiée.
- **`tsvector` calculés à la volée** dans la requête de matching : à ~4600 offres et 2 runs/jour, une colonne précalculée + index GIN n'est pas encore justifiée.
- **Retours de review appliqués** : `TRUNCATE` au lieu de `DELETE` pour le full-replace (pas de verrou ligne à ligne ni de WAL par ligne) ; commentaires explicitant le choix de `tsvector_to_array` et la déduplication des lexèmes par construction (les `SUM(rarity)` ne double-comptent jamais).
- **Retours de review écartés (assumés)** : `total_offers` répété sur chaque ligne (une table meta séparée serait plus propre mais sans intérêt pratique à ce volume) ; `created_at`/`computed_at` toujours égaux (les deux conservés — `created_at` exigé par les conventions SQL, `computed_at` porte la sémantique métier du snapshot).
- **Validation post-déploiement à faire** (corpus réel probablement mono-sectoriel tech, cf. backlog) : vérifier après le premier run de fetch que les termes discriminants ne sont pas exclus par le seuil 0.75 — `SELECT term, doc_frequency, total_offers FROM term_stats WHERE term IN ('terraform','ci/cd');` — et valider le classement sur de vraies offres d'un secteur non-tech dès qu'un profil non-tech existe en base.

---

## PR #182 — feat(frontend): cases à cocher inline dans la barre de filtres de l'onglet Offres

**Date :** 2026-07-09
**Branche :** `feature/correspondances-filter-checkboxes` → `dev`

### Contexte

Sur demande utilisateur : la barre de filtres de l'onglet Offres portait 4 contrôles en dropdown (Trier, Contrat, Score, et le popover « Filtre » contenant Nouvelles/Vues), jugés trop nombreux et peu visibles. Clarification des attentes par questions ciblées avant implémentation, car convertir Contrat/Score en cases à cocher changeait leur sémantique (sélection exclusive → filtre OR) : décision retenue — suppression pure des dropdowns Trier/Contrat/Score (le tri reste fixé par pertinence, décroissant), et les cases Nouvelles/Vues affichées directement dans la barre au lieu d'être cachées dans le popover Filtre.

### Ce qui a été fait

- **`CorrespondancesPanel.tsx`** : suppression des états `sort`/`contract`/`minScore`/`filterOpen`, des types `SortKey`/`ContractFilter`/`ScoreFilter`, de `SCORE_THRESHOLDS` et de `parseSalaryMax()` (devenu mort avec le tri par salaire). Le tri du `useMemo` `filtered` est fixé à `b.score - a.score`. Les 3 `<select>` et le bouton/popover « Filtre » sont remplacés par un bloc unique dans la barre : label « Offres » suivi des cases à cocher Nouvelles/Vues, visibles sans interaction supplémentaire.
- **Tests** : le test de reset de pagination au changement de tri (`getByDisplayValue("Trier : Pertinence")`) est remplacé par un équivalent sur changement de recherche texte, seul déclencheur de reset restant hors Nouvelles/Vues. Le test « offre sauvegardée visible malgré son bucket Nouvelles décoché » clique directement sur la case à cocher au lieu d'ouvrir le popover Filtre supprimé.

**Vérification :** Jest 19/19 sur `CorrespondancesPanel.test.tsx`, `tsc --noEmit` et ESLint propres.

### Décisions techniques

- **Clarification avant implémentation plutôt qu'interprétation** : la demande groupait 4 dropdowns sous un même verbe « supprimer », mais Trier n'est pas un filtre (n'exclut rien) et Contrat/Score étaient des sélections exclusives — une conversion silencieuse en cases à cocher OR aurait changé le comportement sans validation. Questions posées via `AskUserQuestion` avant tout code ; réponses obtenues : tri retiré (pertinence fixe), Contrat et Score retirés purement et simplement (seuls Nouvelles/Vues restent).

---

## PR #183 — fix(frontend): rafraîchissement silencieux des correspondances quand match_count change

**Date :** 2026-07-09
**Branche :** `feature/cv-detail-matches-live-refresh` → `dev`

### Contexte

Bug remonté par Vincent : quand l'analyse d'un CV se termine et que son `match_count` se met à jour sur la carte de la bibliothèque, le panneau « Vos correspondances » du détail n'affiche rien de nouveau tant que la page entière n'est pas rechargée. Diagnostic posé en session Cowork le 09/07 (`docs/prompts/prompt-cv-detail-matches-live-refresh.md`) : deux fetches indépendants qui ne se parlent pas — `LibrarySection.tsx` poll `GET /cv/` et remonte `match_count` au parent en direct, mais l'effet de `CVDetailSection.tsx` qui fetch `GET /matches/cv/{id}` ne dépend que de `[selectedCvId, zoneVersion]` et ignore la prop déjà à jour.

### Ce qui a été fait

- **`CVDetailSection.tsx`** : l'effet de fetch des correspondances gagne `currentCv?.match_count` dans ses dépendances, avec une ref `prevMatchesKeyRef` qui distingue un **reset dur** (changement de `selectedCvId`/`zoneVersion` : vidage de la liste, spinner, bannière d'erreur possible) d'un **rafraîchissement silencieux** (seul `match_count` a changé sur le même CV/zone : refetch en arrière-plan, remplacement de `matches` uniquement au succès, jamais de spinner ni de bannière d'erreur sur un raté transitoire de poll).
- **Tests** (`CVDetailSection.test.tsx`) : nouveau describe dédié — refetch déclenché par un changement de `match_count` seul, absence de refetch sur un changement de prop sans rapport (même valeur, nouvelle référence de tableau), et liste existante conservée sans bannière d'erreur quand le rafraîchissement silencieux échoue.

**Vérification :** Jest 7/7 sur `CVDetailSection`, ESLint propre. Le test manuel décisif (upload d'un CV, laisser l'analyse se terminer sans toucher à la page, confirmer l'apparition de la liste sans reload ni flash de chargement) n'a **pas** été exécuté dans cette session — nécessite la stack complète (backend, pipeline d'analyse Azure OpenAI) ; à faire par Vincent avant merge.

### Décisions techniques

- **Aucun changement côté `LibrarySection.tsx`, `HomeClient.tsx` ni backend** : `match_count` était déjà correct et déjà propagé jusqu'à `CVDetailSection` ; il manquait uniquement le fil entre les deux composants frontend, conformément au prompt.

---

## PR #184 — feat(offer-distillation): pipeline asynchrone de distillation LLM des offres avant embedding

> **Superseded** — la distillation décrite ci-dessous a été retirée entièrement (voir l'entrée
> de retrait plus bas dans ce journal, `docs/prompts/prompt-remove-offer-distillation.md`).
> Entrée conservée telle quelle pour l'historique.

**Date :** 2026-07-09
**Branche :** `feature/offer-distillation-pipeline` → `dev`

### Contexte

Suite du diagnostic mené avec Vincent les 09-10/07 (`docs/prompts/prompt-matching-skills-bonus-ratio-fix.md`, `docs/prompts/prompt-matching-llm-distillation-manual-test.md`). Le test manuel a validé qu'un prompt de distillation en verbe + objet (plutôt qu'une liste de noms d'outils bruts) sépare nettement mieux les offres pertinentes des hors-sujet avant embedding. Cette tâche (`docs/prompts/prompt-offer-distillation-pipeline.md`) passe cette distillation en production dans le pipeline d'ingestion, sans faire de `offer_fetching` un point bloquant : la distillation devient un agent asynchrone séparé, déclenché par offre via Service Bus.

### Ce qui a été fait

- **Migration 027 + `Offer.distilled_skills`** : colonne texte nullable persistant le texte distillé (débogabilité) — le prompt suggérait le numéro 025, déjà pris par `term_stats` (PR #180) ; d'abord numérotée 026, puis renumérotée en 027 lors du rebase sur `dev` une fois PR #185 mergée (qui avait elle-même pris le numéro 026 entre-temps).
- **`shared/bus.py::send_messages_batch`** : nouveau helper réutilisant une seule connexion/sender pour publier plusieurs messages, au lieu d'ouvrir une connexion AMQP par message (`send_message` existant) — nécessaire pour le fan-out par offre (potentiellement des milliers par run) sans réintroduire la latence que l'architecture asynchrone est censée éliminer.
- **`offer_fetching`** : ne fait plus que fetch + upsert. `_embed_pending_offers` et l'appel `embed()` supprimés ; publie désormais un message par offre à `embedding IS NULL` sur la nouvelle queue `distillate-offer-fetched`. Le dispatch de fin de run vers l'ancienne `offer-ready` est supprimé (il ne captait plus rien d'utile une fois la distillation asynchrone). Secrets/env vars OpenAI retirés du job Terraform associé, devenus inutiles.
- **Nouvel agent `agents/offer_distillation`** : consomme `distillate-offer-fetched` (un `offer_id` par message), idempotent (no-op si l'offre a déjà un embedding — message rejoué), distille via GPT-4o-mini (prompt verbe + objet validé, texte brut en sortie), embed via `shared/embedder.py::embed()`, écrit `distilled_skills` + `embedding`. Aucun message en sortie. Pas de boucle de retry JSON (contrairement à `cv_analysis`) : la sortie est du texte brut, pas de JSON à parser — une erreur (API ou réponse vide) remonte telle quelle, laissant Service Bus réessayer le message au niveau transport (pas de colonne de statut sur `offers`).
- **Nouvel agent `agents/matching_heartbeat`** : job timer minimal (`*/15 * * * *`), envoie un seul message `start-matching` et termine — filet de rattrapage puisque la distillation asynchrone n'a plus de signal "lot terminé" par offre (un compteur partagé a été envisagé puis écarté avec Vincent, fragile face à la livraison "au moins une fois"). N'importe ni `shared.db` ni `shared.models` — ce job n'a délibérément aucun accès base ni secret OpenAI/France Travail.
- **Renommage `offer-ready` → `start-matching`** : constante `OFFER_READY_QUEUE`/valeur dans `agents/matching`, `agents/cv_analysis`, `agents/webapp/routers/profile.py` (+ commentaire dans `routers/cv.py`) — comportement inchangé, granularité par événement déclencheur (jamais par offre), cohérent avec la nouvelle `distillate-offer-fetched` qui elle est bien par offre.
- **Terraform** : queue `distillate-offer-fetched` ajoutée, `offer-ready` renommée `start-matching` dans `servicebus.tf` ; deux nouveaux modules `job_offer_distillation` (`job-jf-dev-frc-distill`, queue, `max_executions = 20` pour absorber un afflux de milliers d'offres) et `job_matching_heartbeat` (`job-jf-dev-frc-heartbeat`, timer, secrets réduits au strict nécessaire Service Bus + Application Insights) dans `container_apps.tf`.
- **CI (`buildAgents.yml`)** : ajout des deux nouvelles images (`offer-distillation`, `matching-heartbeat`) — build/push, résumé de build, mise à jour du Container App Job. Non demandé explicitement par le prompt de tâche (qui ne couvre que l'architecture des 6 commits Python/Terraform), mais sans ce câblage les deux nouveaux jobs Terraform référenceraient des images jamais construites — fonctionnalité non déployable sinon.

**Vérification :** `pytest` 243/243 après rebase sur `dev` (nouveau `test_offer_distillation.py`/`test_bus.py`, mise à jour `test_offer_fetching.py`/`test_webapp_profile.py` pour le renommage de queue et pour le retrait de `_refresh_term_stats`). `terraform fmt -check` et `terraform validate` propres sur `envs/dev`. Grep du dépôt entier : plus aucune référence code à `offer-ready`/`OFFER_READY_QUEUE` (seules les mentions historiques dans `BACKLOG.md`/`ROADMAP.md`/`JOURNAL.md`/ADR subsistent, volontairement non réécrites). Aucune ressource critique détruite/remplacée — seules des queues et jobs ajoutés/modifiés à l'intérieur du namespace Service Bus existant (`prevent_destroy`/`protect` inchangés).

### Décisions techniques

- **Hygiène de branche avant de démarrer** : la branche `feature/matching-skills-bonus-ratio-fix` avait un diff local non commité sur `agents/matching/main.py` alors que le nouveau prompt indiquait ce fix "déjà mergé" — écart confirmé réel (aucun commit sur `dev`), et le diff s'est avéré être une copie obsolète du fix déjà réellement appliqué ailleurs (branche `tmp` parallèle de Vincent, contenant le test manuel de distillation validé). Diff écarté sur confirmation explicite de Vincent avant de repartir de `dev` à jour.
- **Numéro de migration 027, pas 025** : le prompt de tâche suggérait 025, déjà pris par `term_stats` (PR #180, mergée après la rédaction du prompt) — un numéro dupliqué aurait fait échouer Alembic au démarrage. Numérotée 026 dans un premier temps, puis 027 après rebase (voir plus bas).
- **Pas de retry JSON dans `offer_distillation`** : le prompt demandait "même politique que `_extract_rome_codes`", mais cette politique retry sur erreur de parsing JSON — la distillation retourne du texte brut, il n'y a rien à parser. Propagation de l'erreur (transport Service Bus) retenue à la place, cohérente avec l'esprit du prompt ("laisser Service Bus gérer le retry").
- **`send_messages_batch` ajouté, non demandé explicitement** : publier un message par offre avec `send_message` (une connexion AMQP par appel) aurait réintroduit à l'intérieur d'`offer_fetching` la latence cumulée que l'architecture asynchrone cherche justement à éliminer, à l'échelle de milliers d'offres. Justifié par l'échelle mentionnée dans le prompt lui-même (10 000 offres/run), pas une optimisation gratuite.
- **Secrets OpenAI retirés du job `offer_fetching` en Terraform** : conséquence directe de la suppression de l'appel `embed()` de cet agent — non demandé explicitement par le prompt mais nécessaire (moindre privilège, l'agent n'a plus aucun besoin d'Azure OpenAI).
- **Rebase sur `dev` après merge de PR #185** (qui retire tout le bonus lexical `tech_keywords`/`term_stats`) : deuxième collision de numéro de migration (026 pris cette fois par `026_remove_lexical_bonus`, en plus du 025 déjà pris par `term_stats`) — renumérotée en 027, `down_revision` rebasé sur 026. `_refresh_term_stats()` n'existe plus après PR #185 : l'appel prévu dans `offer_fetching.main()` après `_publish_pending_offers_for_distillation()` est retiré (plus rien à rafraîchir), de même que les imports `UserProfile`/`tech_keywords` devenus morts et la classe de test `TestRefreshTermStats`.

---

## PR #185 — refactor(matching): retirer tout bonus lexical du score de matching

**Date :** 2026-07-09
**Branche :** `feature/matching-remove-lexical-bonus` → `dev`

### Contexte

Exécution de `docs/prompts/prompt-matching-remove-lexical-bonus.md`. Décision actée avec Vincent le 09/07 : sur 6 offres réelles diagnostiquées, aucune formule purement statistique sur des mots isolés ne peut distinguer un terme rare-mais-pertinent d'un terme rare-mais-hors-sujet (ex. « sport » d'une offre QA, « jeux » d'un CV avec passé Unity) — le bonus lexical est retiré entièrement, pas juste corrigé. Le score final devient `GREATEST(0, base_score - pénalité_expérience)`.

### Ce qui a été fait

- **Étape 0 (obligatoire avant tout retrait)** a corrigé deux prémisses du prompt : le mécanisme `term_stats`/rareté corpus-relative (PR #180) n'était pas incertain — déjà mergé et vivant sur `dev`, ayant déjà remplacé le bonus `tech_keywords` dans la requête de scoring elle-même (`shared/tech_keywords.py`/`.json` et les colonnes restaient cependant vivants ailleurs, en poids mort). PR #177 référencée dans le prompt est déjà **mergée** et concerne une PR différente (introduction initiale de `tech_keywords`) — rien à fermer. La branche `feature/matching-skills-bonus-ratio-fix` n'a aucun commit d'avance sur `dev` et aucun WIP retrouvé dans les 3 worktrees — abandon = no-op (suppression de la branche locale laissée à Vincent, bloquée par le classifieur de sécurité auto-mode).
- **`agents/matching/main.py::_get_all_matches`** : retrait des CTEs `offer_terms`/`cv_terms`/`offer_rarity_mass`/`covered_rarity`/`final` ; `scored`/`after_experience` (blend embedding + pénalité expérience) inchangés. Docstring réécrite.
- **Découverte absente du prompt** : `_refresh_term_stats()` (`agents/offer_fetching/main.py`) et le modèle ORM `TermStat` (`shared/models.py`) devenaient orphelins après le retrait des CTEs — retirés également.
- Suppression complète de `shared/tech_keywords.py`/`.json`, des colonnes `offers.tech_keywords`/`cvs.tech_keywords`, de la table `term_stats`, des call sites d'extraction (`offer_fetching/main.py`, `webapp/routers/cv.py`), et des constantes `SHARED_TERM_BONUS_WEIGHT`/`TERM_STOPWORD_THRESHOLD` (`TECH_KEYWORDS_WEIGHT` déjà absent). Aucun `env_vars` Terraform ne les référençait.
- Migration `026_remove_lexical_bonus` (downgrade recrée colonnes/table sans données). Tests mis à jour, `test_tech_keywords.py` supprimé.

**Vérification :** `pytest tests/` 221/221. Cycle migration `upgrade head` → `downgrade -1` → `upgrade head` validé contre Postgres 16 + pgvector jetable (Docker). Requête simplifiée rejouée sur données synthétiques reproduisant le cas diagnostique (offre truffée de « sport »/« jeux » hors-sujet) : score = embedding pur (1.0, aucun bonus résiduel) ; offre avec écart d'expérience de 3 ans : score = 0.91 = 1.0 − (3 × 0.03), pénalité seule.

### Décisions techniques

- **Remplacer par rien, pas par une formule alternative** : contrairement au remplacement `tech_keywords` → `term_stats` de PR #180, aucun mécanisme lexical de repli n'est introduit — la décision actée est qu'un LLM en amont de l'embedding (`prompt-offer-distillation-pipeline.md`, indépendant) est la seule voie retenue pour ce signal.
- **Bénéfice complet différé** : le classement sur les 6 offres de référence ne sera pleinement correct qu'une fois la distillation LLM également en production (le `base_score` actuel reste sur texte brut) — ce retrait est correct et livrable indépendamment.

---

## PR #186 — feat(frontend): inclure la description de l'offre dans la recherche des correspondances

**Date :** 2026-07-09
**Branche :** `feature/correspondances-search-description` → `dev`

### Contexte

Demande utilisateur : la barre de recherche de l'onglet Offres ne matchait que titre/entreprise/localisation — une recherche « Azure » ne remontait pas une offre qui mentionne Azure uniquement dans sa description.

### Ce qui a été fait

- **`CorrespondancesPanel.tsx`** : le filtre de recherche (`useMemo` `filtered`) inclut désormais `offer.description` dans la chaîne concaténée testée par `.includes(q)`, en plus de titre/entreprise/localisation. Aucun changement backend : `description` était déjà retourné par `GET /matches` et typé dans `MatchOut` côté frontend, simplement pas exploité par la recherche.
- **Garde `?? ""`** sur `offer.description` dans le filtre : une description absente du payload se serait interpolée en la chaîne littérale `"undefined"`, produisant un faux positif pour une recherche sur ce mot.
- **Retour visuel sur le match** (`MatchItem.tsx`) : la requête de recherche active est propagée via un nouveau champ `searchQuery` de `MatchItemData`, uniquement pour l'onglet Offres (l'onglet Sauvegardées ignore la recherche par design, aucune query ne lui est passée). `highlightMatches()` enveloppe chaque occurrence insensible à la casse dans un `<mark>` (tokens `bg-accent-muted`/`text-accent`), appliqué à la description affichée dans le panneau déplié — sans lui, un match en plein milieu d'une longue description n'offrait aucun indice visuel de la raison du rapprochement.
- **Tests** : nouveau cas — une offre matchée uniquement via un mot-clé présent dans sa description, une autre offre au même mot-clé absent restant exclue ; côté `MatchItem`, mise en évidence effective avec query, absence de `<mark>` sans query ou sans correspondance.

**Vérification :** Jest 48/48 (`CorrespondancesPanel.test.tsx` + `MatchItem.test.tsx`), `tsc --noEmit` et ESLint propres.

---

## PR #187 — fix(profile): retirer experience_level du texte d'intent_embedding (garder uniquement le malus)

**Date :** 2026-07-10
**Branche :** `feature/profile-decouple-experience-from-intent-embedding` → `dev`

### Contexte

Exécution de `docs/prompts/prompt-profile-decouple-experience-intent.md`, suite du retrait du bonus lexical (PR #185) et du pipeline de distillation (PR #184). Diagnostic du 09/07 (Vincent, son propre profil vs l'offre WALLIX `ft_id 3976333`) : `base_score` en production tombait à 0.4971 — juste sous `MATCHING_SCORE_THRESHOLD = 0.5` — alors que la similarité CV↔offre distillée mesurée séparément était de ~0.696. Cause : `_build_intent_text` combinait une phrase générique dérivée d'`experience_level` (ex. « Profil confirmé, 2 à 5 ans d'expérience ») avec `candidate_description` ; quand cette dernière est vide (cas de Vincent), `intent_text` se réduisait à cette seule phrase, quasiment vide de contenu sémantique distinctif une fois embedée, et suffisait à faire chuter un excellent match sous le seuil une fois mélangée à 30 % (`INTENT_EMBEDDING_WEIGHT`) dans le score final.

### Ce qui a été fait

- **`agents/webapp/routers/profile.py::_build_intent_text`** : signature réduite à `candidate_description: str | None` seul, retrait des trois branches `if/elif` sur `experience_level`. Le corps retourne désormais `candidate_description.strip()` ou une chaîne vide.
- **`agents/webapp/routers/profile.py::put_profile`** : le recalcul de l'embedding (`_build_intent_text` + `embed()`) ne s'exécute plus que si `description_changed` est vrai — un changement d'`experience_level` seul ne touche plus à `intent_embedding`, ni à la clé `"intent_embedding"` du dict `updated` passé à `on_conflict_do_update(set_=updated)` (la valeur déjà stockée n'est donc pas écrasée). `intent_changed = experience_changed or description_changed` reste inchangé — un changement d'`experience_level` seul redéclenche toujours `matching` via `_dispatch_start_matching`, puisque le malus d'expérience en dépend. Les deux déclenchements (recalcul d'embedding, redéclenchement de matching), auparavant confondus sous un seul flag, sont maintenant découplés.
- **`agents/matching/main.py::_get_all_matches`** : docstring corrigée — `intent_embedding` ne reflète plus que `candidate_description`, le malus d'expérience reste documenté séparément.
- **Tests (`test_webapp_profile.py`)** : `test_experience_level_bucket_text` remplacé par `test_experience_level_alone_never_recomputes_embedding` (les trois valeurs d'`experience_level`, seul, ne doivent jamais appeler `embed()`) ; `test_experience_and_candidate_description_recomputes_intent_embedding` mis à jour (`embed()` appelé avec la description seule, sans le fragment expérience) ; `test_partial_put_preserves_existing_candidate_description_in_intent` réécrit pour vérifier qu'`embed()` n'est plus appelé du tout quand seule la description reste inchangée, et que la clé `"intent_embedding"` est absente du `set_` de l'upsert ; nouveau test `test_experience_level_alone_still_dispatches_start_matching` distinguant explicitement « pas de recalcul d'embedding » de « pas de redéclenchement de matching ».
- **Repéré mais volontairement laissé intact** : `agents/match_analysis/main.py::_analyze_match` et `agents/cv_analysis/main.py::_analyze_cv_quality` contiennent chacun une copie dupliquée des mêmes fragments `experience_level` (commentaire explicite : « dupliquée sciemment, les agents ne doivent pas dépendre d'agents/webapp »). Hors périmètre : ce texte alimente un prompt LLM (« Intention du candidat » pour l'analyse de correspondance / la cohérence CV↔intention), pas `intent_embedding` — un LLM n'est pas sensible à la dilution sémantique d'un embedding par une phrase générique, contrairement à une similarité cosinus.

**Vérification :** `pytest` 244/244 (`test_webapp_profile.py` et `test_matching.py` inclus, ce dernier sans changement de comportement — docstring uniquement). Historique de commits vérifié à chaque étape (34/35 tests verts avant l'ajout du test de découplage, 244/244 après le commit final). Grep du dépôt entier sur les fragments `"Profil junior"/"Profil confirmé"/"Profil senior"` : seules les copies intentionnellement dupliquées de `match_analysis`/`cv_analysis` (hors périmètre) subsistent.

### Décisions techniques

- **Backfill non scripté, mais le repli « resauvegarder son profil » suggéré par le prompt de tâche ne suffit pas pour le cas de Vincent** : le recalcul ne se déclenche que sur un `PUT /profile` où `description_changed` est vrai (`new_description != old_description`). Le profil de Vincent a `candidate_description` vide (`None` en base), et le formulaire frontend (`app/profile/page.tsx:81`, `candidateDescription.trim() || null`) renvoie `null` pour un champ vide — une resauvegarde sans toucher au champ envoie donc `None == None`, `description_changed` reste faux, et l'`intent_embedding` bugué (calculé avec l'ancienne formule) n'est jamais effacé. Corrigé pendant la revue avant ce commit ; décision explicitement reportée à Vincent (`UPDATE user_profiles SET intent_embedding = NULL` en une fois, ou saisir puis effacer une description pour forcer deux changements réels) — non scripté ici, à traiter après déploiement.
- **Découpage en 3 commits atomiques** : le retrait du texte d'expérience (`_build_intent_text` + mise à jour du site d'appel, sans encore conditionner l'appel à `embed()`) est séparé du découplage des deux déclencheurs (ajout de la garde `if description_changed:`) — chaque commit intermédiaire reste vert (34 tests après le premier commit `test_webapp_profile.py` + `test_matching.py`, 35 après le second) plutôt que de livrer un diff monolithique sur `put_profile`.

---

## PR #189 — feat(claude): process automation (skills, hooks, reviewer subagents, claude-code-action)

**Date :** 2026-07-10
**Branche :** `feature/claude-process-automation` → `dev`

### Contexte

Mise en place de l'infrastructure `.claude/` du projet (jusque-là inexistante) : migration des conventions `docs/conventions-*.md` vers des skills auto-chargées, ajout de subagents de review en lecture seule par domaine, et de hooks mécaniques faisant respecter des règles déjà documentées en prose dans `CLAUDE.md` (Git Workflow, Terraform Conventions, Code Review Standards). Une fois ces prérequis en place, ajout de `anthropics/claude-code-action@v1` pour fermer la boucle : permettre d'invoquer Claude Code directement depuis un commentaire de PR/issue.

### Ce qui a été fait

- **`.claude/skills/conventions-{frontend,python,sql,terraform}/SKILL.md`** : migration des 4 fichiers `docs/conventions-*.md` en skills, avec description déclenchant leur chargement automatique selon le type de fichier édité (au lieu d'une instruction manuelle « lis ce doc d'abord » dans `CLAUDE.md`).
- **`.claude/hooks/pre_bash_guard.py`** (`PreToolUse` sur Bash, via `.claude/settings.json`) : bloque mécaniquement, pour toute instance Claude (session locale ou `claude-code-action` en CI) : push direct vers `main`/`dev`, force-push sans `--force-with-lease`, `git merge` pour rattraper une base, `terraform apply/destroy` local, commande Azure CLI mutante, cmdlet PowerShell Azure mutant, et `gh pr create` sans `docs/JOURNAL.md` à jour ou avec un historique non conforme. Échoue ouvert (exit 0) sur toute erreur interne.
- **`.claude/agents/reviewer-{frontend,backend,infra}.md`** : trois subagents de review en lecture seule (`Read, Grep, Glob`, plus `Bash` en lecture seule pour `reviewer-infra`), un par domaine, chacun scopé à sa convention skill correspondante. Structurellement incapables de corriger — seul livrable : un verdict + rapport `fichier:ligne`.
- **`.claude/hooks/require_reviewer.py`** (`Stop`) : inspecte le transcript de session avant qu'une réponse se termine ; par catégorie de fichier touchée, bloque si le reviewer correspondant n'a pas été rappelé depuis la dernière édition, ou si son dernier verdict n'est pas `APPROUVÉ`. Limite de 3 cycles consécutifs de blocage par reviewer avant abandon de l'enforcement (avertissement non bloquant), pour éviter une boucle infinie.
- **`.claude/hooks/post_edit_format.py`** (`PostToolUse` sur Edit/Write) : `terraform fmt` best-effort après édition d'un `.tf`, `eslint --fix` après édition d'un fichier frontend. Ne bloque jamais.
- **`.claude/commands/new.md`** : commande `/new` pour cadrer une nouvelle tâche (vérifie les skills pertinentes, propose un plan, écrit `docs/prompts/prompt-<slug>.md` une fois validé).
- **`.github/workflows/claudeCodeAction.yml`** : `claude-code-action@v1`, déclenché **exclusivement** par une mention `@claude` explicite (commentaire de PR/issue, commentaire de review, ou corps de review) — jamais automatiquement, quel que soit le domaine de fichier touché. `settings: .claude/settings.json` et `claude_args: --allowedTools Bash,Task,Edit,Write,Read,Grep,Glob` passés explicitement pour que les hooks et les subagents reviewer restent utilisables dans ce contexte CI (non garanti implicitement).
- **`.github/CLAUDE_ACTION.md`** : documente le choix du déclenchement manuel-only (une piste de correction automatique frontend/backend basée sur le verdict `REQUEST_CHANGES` du bot de review existant a été envisagée puis abandonnée avant implémentation — voir Décisions techniques), le setup manuel requis (réutilise le secret `CLAUDE_API_KEY` déjà en place pour `reviewerAgent.yml`, installation de la GitHub App Claude), et les points de vérification encore ouverts.
- **`CLAUDE.md`** : sections Terraform/Python/SQL/Frontend Conventions repointées vers les skills ; nouvelles sections documentant l'enforcement par hooks et les subagents reviewer.
- **`.claude/agents/doc-writer.md`** : quatrième subagent, seul à disposer d'`Edit`/`Write` (les reviewer-* sont en lecture seule) — vérifie et corrige lui-même les docstrings Python obsolètes/manquantes, les commentaires WHY, et écrit/actualise l'entrée `docs/JOURNAL.md` de la tâche en cours (numéro de PR déterminé via `gh api`/`gh pr list`, jamais deviné). Conçu pour tourner avant les reviewers, au moment de l'ouverture de la PR.
- **`.claude/hooks/pre_bash_guard.py::check_pr_create`** : `gh pr create` bloque désormais aussi si `doc-writer` n'a pas été rappelé (via `Task`/`Agent`) depuis la dernière édition du transcript, en plus des vérifications déjà en place (JOURNAL.md présent, historique de commits propre).
- **`.claude/agents/explorer.md`** : cinquième subagent, en lecture seule (`Read, Grep, Glob`), à appeler avant de démarrer l'implémentation d'une feature non-triviale plutôt qu'après (contrairement aux reviewer-*/`doc-writer`, appelés en fin de tâche). Répond à une question de repérage précise (fichiers pertinents, pattern déjà utilisé pour un cas similaire, conventions réelles au-delà de ce qu'un skill documente en général) par un résumé court, sans jamais proposer de plan d'implémentation ni corriger de code — pensé pour éviter que la session principale ne se remplisse de dizaines de `Read`/`Grep` devenus inutiles une fois le plan en main.
- **Retrait du hook `Stop` sur les reviewer-\*** : `.claude/hooks/require_reviewer.py` et son entrée `Stop` dans `.claude/settings.json` sont supprimés. La vérification (catégorie touchée → reviewer rappelé depuis la dernière édition → verdict `APPROUVÉ`) est déplacée dans `pre_bash_guard.py::check_pr_create`, la même fonction qui gate déjà `docs/JOURNAL.md`, l'historique de commits et `doc-writer` — les quatre vérifications sont maintenant collectées en un seul passage du transcript (`docs_and_reviews_readiness()`) et rapportées ensemble dans un seul message de blocage plutôt qu'une à la fois.
- **Réaction aux remarques non-bloquantes, plafonnée à 3 tentatives** : les trois `reviewer-*.md` doivent désormais toujours inclure une ligne `Remarques non-bloquantes :` (`aucune`, ou liste courte), même verdict `APPROUVÉ` — jusqu'ici cette information existait seulement en prose libre dans le rapport, sans signal exploitable mécaniquement. `pre_bash_guard.py::has_warnings()` la parse ; si non-vide (ou absente — traité pareil qu'un verdict indéterminé, par prudence), `gh pr create` est aussi bloqué, avec un compteur persisté à côté du transcript (`.pr_create_warning_state.<stem>.json`, `MAX_WARNING_ATTEMPTS = 3`) qui abandonne l'enforcement pour cet agent après 3 tentatives consécutives et repart à zéro dès que l'agent répond `aucune` ou n'est plus concerné. Testé manuellement (transcript JSONL synthétique) : blocage aux tentatives 1/3, 2/3, 3/3, laisser-passer silencieux à la 4e avec remise à zéro, nouveau cycle 1/3 ensuite.
- **Revue externe de `pre_bash_guard.py`/`.claude/commands/new.md`, 5 points corrigés ou clarifiés** :
  - `check_merge()` reposait sur `re.search(r"\bgit\s+merge\b", command)` sur la commande brute — `echo "please dont git merge here"` ou `grep "git merge" fichier.py` déclenchaient un faux positif. Remplacé par un scan de tokens (`shlex.split`) cherchant un token `git` (nu ou qualifié par chemin, `/git`/`\git`) suivi, après les flags globaux commençant par `-`, du token `merge`. Vérifié manuellement : les deux faux positifs ci-dessus passent désormais, `git merge origin/dev` bloque toujours, `--ff-only` reste exempté, et `git --no-pager merge origin/dev` bloque en plus désormais (l'ancienne regex ne le détectait pas non plus, `--no-pager` cassant `\s+` entre `git` et `merge` — gain net, pas de régression). Limite documentée et assumée : `git -C /repo merge` n'est toujours pas détecté (un flag qui consomme une valeur, `-C <path>`, n'est pas un simple "commence par -" à sauter) — déjà un angle mort de l'ancienne regex aussi, pas une régression introduite ici. Le même type d'imprécision (regex sur la commande brute) existe encore dans `check_terraform_destructive`/`check_azure_cli`/`check_powershell`, non touchés ici faute de demande explicite.
  - `save_state()` avalait toute exception avec un `pass` nu et un commentaire trompeur (« a lost counter just resets to 0 ») : en cas d'échec *persistant* d'écriture (permissions sur le dossier du transcript), le compteur ne peut jamais être écrit, donc `state.get(agent, 0)` lit toujours 0, donc `MAX_WARNING_ATTEMPTS` n'est jamais atteint — `gh pr create` bloquerait alors indéfiniment au lieu de finir par céder, l'inverse de ce que disait le commentaire. `sys.stderr.write()` ajouté pour rendre cet échec visible au lieu de le supposer silencieusement bénin.
  - Message de blocage enrichi du fichier concerné : `f"{agent} n'a pas ete rappele ({cat})"` ne disait pas *quel* fichier n'était pas couvert. `last_touch` stocke maintenant `(line_no, file_path)` au lieu de `line_no` seul ; les deux messages (« pas rappelé » et « verdict pas approuvé ») citent désormais le fichier.
  - `.claude/commands/new.md` : note ajoutée précisant que l'étape 4 (« On discute du plan ») suppose un échange humain interactif, donc que la commande est réservée aux sessions locales (Cowork/Code) et ne s'applique pas à un run `claude-code-action` en CI.
  - Deux points de la revue portaient sur `require_reviewer.py` (même défaut `pass` nu dans son `save_state()`, et absence du fichier concerné dans ses messages) — obsolètes : ce fichier a été supprimé plus haut dans cette même PR (retrait du hook `Stop`). Le premier défaut est corrigé de toute façon dans le `save_state()` actuel de `pre_bash_guard.py` (partagé pour `doc-writer`/reviewers/warnings) ; le second est couvert par le point ci-dessus. Un troisième point comparait la vérification `doc-writer` à celle des reviewers dans `require_reviewer.py` (« plus faible, ne fait pas le même cross-check ») — également obsolète : les deux vérifications partagent désormais exactement le même code (`docs_and_reviews_readiness()`), il n'y a plus d'asymétrie à corriger.
- **Deuxième passe de revue (rapport CI formel), 5 points traités** :
  - `check_azure_cli()` : `AZ_MUTATING_RE` cherchait un verbe mutant n'importe où après `az` et des tokens `[\w-]+` répétés — le faux positif cité dans le rapport (`--query "[?name=='delete']"`) ne se reproduisait en fait pas (guillemets/crochets cassent la chaîne de tokens requise), mais un vrai faux positif existait bien ailleurs : `az storage blob list --prefix create` (lecture seule, filtrée sur un préfixe qui contient littéralement le mot "create") était bloqué à tort, la valeur du flag étant confondue avec le verbe. Remplacé par une lecture positionnelle : le "verbe" est le dernier token avant le premier flag (`az <groupe> [<sous-groupe>...] <verbe> --options`), pas un mot cherché n'importe où. Vérifié manuellement : 4 cas de faux positifs désormais autorisés (dont celui ci-dessus), 4 vraies commandes mutantes toujours bloquées. Limite assumée : une option globale placée immédiatement après `az` (`az --output json vm create ...`) fait échouer l'ancrage positionnel — pattern jugé rare dans ce projet (les flags viennent conventionnellement après la commande), traité comme le même type d'angle mort documenté que `-C <path>` sur `check_merge`.
  - Référence de section corrigée sur le message de blocage `docs/JOURNAL.md` : citait « CLAUDE.md > Terraform Conventions », alors que la règle vit sous « Git Workflow > Enforcement via hooks ».
  - Commentaire ajouté à l'endroit où `tool_input.get("subagent_type")` est lu, pour documenter explicitement le couplage au schéma du transcript (mentionné comme acceptable par la revue, mais méritant un commentaire).
  - Journal Terraform CI vide sur cette PR (aucun fichier `.tf` touché, plan à blanc) : signalé par la revue comme un problème d'infrastructure CI, pas un problème de cette PR — aucune action ici.
  - Fragment de docstring "coupé" sur `conventions-python/SKILL.md` signalé par la revue comme possible artefact d'affichage de diff, à vérifier si réel : vérifié dans le fichier commité, la phrase est complète (« Une variable manquante lève une `ValueError` explicite avec le nom de la variable. ») -- confirmé artefact d'affichage, rien à corriger.
  - Suggestions appliquées : commande `git log --oneline <base>..HEAD` ajoutée au message de blocage sur les commits non conformes ; repli documenté dans `doc-writer.md` si `gh` n'est pas authentifié (reprendre le dernier `## PR #NNN` de `docs/JOURNAL.md` et incrémenter) ; règle ajoutée dans `explorer.md` pour signaler explicitement si une tâche touche plus de 2 domaines à la fois plutôt que de tout couvrir en silence.
  - Suggestion non appliquée, consciemment : remplacer les numéros de ligne du transcript par un hash de contenu comme horloge logique, pour rester correct même si un transcript était rejoué/réutilisé entre sessions reprises. Explicitement qualifiée de « significativement plus complexe » par la revue elle-même pour un bénéfice qui ne s'est encore jamais manifesté (le transcript est actuellement toujours append-only) -- laissé de côté, à reconsidérer si ce comportement de reprise de session change réellement.

### Décisions techniques

- **Déclenchement manuel-only, pas de distinction automatique frontend/backend vs infra** : la demande initiale prévoyait une correction automatique (sans mention `@claude`) pour le frontend/backend dès qu'un commentaire de review signale un problème bloquant, avec infra réservée à un déclenchement humain explicite et une limite d'une itération automatique par PR. Écarté avant l'implémentation : classifier fiablement le domaine touché depuis les seules conditions d'un workflow, suivre un état « déjà auto-corrigé une fois » par PR sans le confondre avec une correction manuelle ultérieure (le bot pousse des commits sous la même identité `claude[bot]` dans les deux cas), et éviter une course entre un run automatique et un run manuel concurrent sur la même branche, ajoutaient une surface de correction réelle pour un gain de confort marginal. Décision : tout déclenchement passe par un `@claude` explicite, pour tout domaine — la distinction frontend/backend vs infra reste portée entièrement par `pre_bash_guard.py` (bloque `terraform apply/destroy` et les commandes Azure mutantes, quel que soit l'appelant) plutôt que par la logique du workflow.
- **Inheritance des hooks/subagents en CI explicitée, pas supposée** : la documentation officielle de `claude-code-action` ne confirme pas explicitement que `.claude/hooks`/`.claude/agents`/`.claude/skills` sont chargés automatiquement au checkout. Plutôt que de compter sur un comportement non documenté, le workflow passe `settings: .claude/settings.json` et autorise explicitement `Bash`/`Task` via `claude_args`. Premier `@claude` réel après merge à traiter comme la vérification effective, pas seulement le comportement en session locale.
- **Pas de test de bout en bout dans cette PR** : les workflows déclenchés par `issue_comment`/`pull_request_review`/`pull_request_review_comment` s'exécutent toujours avec la copie du fichier de workflow présente sur la branche par défaut (`main`), jamais celle de la PR — même mise en garde déjà documentée dans `reviewerAgent.yml`. Un test réel (mention `@claude` sur une PR frontend ; mention `@claude` demandant un `terraform apply` sur une PR infra, pour confirmer que le hook bloque toujours) ne peut avoir lieu qu'une fois ce fichier mergé sur `main`.
- **Réorganisation en 7 commits atomiques** : le commit de travail initial (tout `.claude/` d'un coup) a été redécoupé — skills, `pre_bash_guard` + wiring minimal, subagents reviewer, `require_reviewer` + wiring, `post_edit_format` + wiring, commande `/new`, puis documentation `CLAUDE.md` — chaque commit intermédiaire laissant `.claude/settings.json` cohérent avec les seuls fichiers de hooks déjà présents à ce point de l'historique.
- **`doc-writer` et reviewer-\* désormais gatés ensemble sur `gh pr create`, plus sur deux hooks distincts** : initialement, `doc-writer` était vérifié par `pre_bash_guard.py` (`PreToolUse` sur `gh pr create`) tandis que les reviewer-* l'étaient par un `Stop` hook séparé (`require_reviewer.py`, fin de session). Demande explicite : uniformiser sur le modèle `gh pr create`, comme pour `doc-writer`. Bénéfice au passage, pas seulement la cohérence demandée : le `Stop` hook bloquait la *fin de session elle-même* si un reviewer ne validait jamais, ce qui justifiait sa mécanique de limite de cycles (3 blocages consécutifs puis abandon, pour ne jamais laisser l'agent définitivement bloqué) ; gaté sur `gh pr create` à la place, un reviewer qui ne valide jamais bloque seulement l'ouverture de la PR — Claude peut toujours choisir de ne pas ouvrir la PR et remonter le désaccord à l'utilisateur, donc plus besoin de cette soupape de sécurité, supprimée avec le hook.
- **Séquencement `doc-writer` → reviewers toujours non garanti mécaniquement** : les deux sont désormais vérifiés dans le même passage du transcript (`docs_and_reviews_readiness()`), mais rien n'empêche qu'un reviewer ait été appelé avant `doc-writer` plutôt qu'après — seule leur présence individuelle depuis la dernière édition est vérifiée, pas leur ordre relatif. Reste une instruction (description du subagent `doc-writer`), au même titre que la frontière Cowork/Code déjà documentée comme non hook-enforced plus haut dans `CLAUDE.md`.
- **Pas de hook pour `explorer`** : contrairement à `doc-writer` (`gh pr create` a un moment précis et détectable) et aux reviewer-* (une édition de fichier a un moment précis et détectable), « cette feature est assez grosse pour justifier une exploration dédiée » n'a pas de signal mécanique fiable — pas de fichier particulier touché, pas de commande particulière lancée. Reste une décision de jugement portée par la description du subagent, comme le générique `Explore` déjà disponible plus largement, dont `explorer` est ici la spécialisation projet (conventions/patterns réels de ce repo plutôt qu'une recherche générique).
---

## PR #188 — refactor(offer-fetching): retirer la distillation LLM des offres, revenir à l'embedding direct

**Date :** 2026-07-10
**Branche :** `feature/remove-offer-distillation` → `dev`

### Contexte

Suite de l'investigation menée avec Vincent le 2026-07-10 sur l'ajout d'un étage de reranking
au-dessus du retrieval par embedding (jugement LLM en lot, cross-encoder BGE, fusion RRF
embedding+lexical) — toutes ces pistes ont été testées via de vrais scripts diagnostiques et
rejetées (coût, vitesse, ou angles morts sémantiques). Décision : rester sur un matching embedding
simple. Ce constat a remis en question la distillation LLM des offres elle-même (PR #184) :
`scripts/diagnostic_llm_distillation_embedding_test.py` avait testé 3 variantes du prompt de
distillation contre la version en production pour corriger le biais de fine-ranking observé (offres
verbeuses/hors-sujet surclassant des offres focalisées et pertinentes sur la seule similarité
cosinus) — aucune variante ne l'a corrigé de façon fiable. Vincent a décidé de retirer la
distillation entièrement et de revenir à un embedding direct du texte brut de l'offre
(titre + description), comme c'est déjà le cas pour les CV.

### Ce qui a été fait

- **`agents/offer_fetching/main.py`** : `_publish_pending_offers_for_distillation` remplacée par
  `_embed_pending_offers` — embed direct (`shared.embedder.embed()`, batché) des offres à
  `embedding IS NULL`, sans distillation LLM préalable. Nouvelle fonction
  `_dispatch_start_matching`, appelée uniquement si au moins une offre a été embedée dans le run —
  remplacement direct et événementiel du rôle de `matching_heartbeat` (fire-and-forget, même
  trade-off que les autres producteurs de `start-matching`).
- **Suppression complète d'`agents/offer_distillation` et `agents/matching_heartbeat`** (main.py,
  Dockerfile) — le premier n'a jamais tenu la promesse pour laquelle il avait été introduit, le
  second n'existait que pour rattraper le délai qu'introduisait le premier.
- **`shared/models.py`** : colonne `distilled_skills` retirée de `Offer`. Migration `028` (miroir de
  la migration `026`) : `drop_column` en `upgrade()`, `add_column` sans restauration de données en
  `downgrade()`.
- **Terraform (`envs/dev`)** : queue `distillate-offer-fetched` retirée de `servicebus.tf` ; modules
  `job_offer_distillation` et `job_matching_heartbeat` retirés de `container_apps.tf` ;
  `job_offer_fetching` gagne le secret `openai-api-key` et les env vars `AZURE_OPENAI_*` qu'il lui
  faut désormais pour embedder directement (miroir de `job_cv_analysis`).
- **CI (`buildAgents.yml`)** : steps de build/push, lignes de résumé, et appels
  `az containerapp job update` pour les deux agents retirés supprimés.
- **Tests** : `test_offer_distillation.py` supprimé ; `test_offer_fetching.py` mis à jour pour
  couvrir `_embed_pending_offers` et `_dispatch_start_matching` (cas avec offres en attente, cas
  sans, cas d'échec Service Bus fire-and-forget).
- **Documentation** : README et BACKLOG mis à jour (retrait des mentions de la queue/des agents
  retirés) ; l'entrée PR #184 de ce journal est conservée telle quelle pour l'historique, flaguée
  « superseded » en tête.

**Vérification :** `pytest` 230/230. `terraform fmt -check` / `terraform validate` sur `envs/dev` —
OK. Grep du dépôt entier sur `offer_distillation|offer-distillation|matching_heartbeat|matching-heartbeat|distillate-offer-fetched|distilled_skills` —
aucune occurrence résiduelle hors historique (`docs/JOURNAL.md`, `docs/prompts/prompt-offer-distillation-pipeline.md`,
migrations 027/028) et faux positif attendu (`test_bus.py`, nom de queue arbitraire pour tester
`send_messages_batch`).

### Décisions techniques

- **Sûreté du retour au synchrone confirmée avant exécution** : l'architecture asynchrone de la
  distillation n'existait que parce qu'un appel LLM par offre en séquentiel dépasserait le timeout
  d'1h d'`offer_fetching` sur potentiellement des milliers d'offres. `shared.embedder.embed()` batch
  déjà ses entrées par 100 en interne, sans appel générateur par offre — le retrait ne réintroduit
  donc pas le problème de latence qui avait justifié l'architecture asynchrone à l'origine.
- **`alembic upgrade head` / `downgrade -1` et le test manuel jumpbox non exécutés dans cette
  session** : pas de connectivité à la base de dev depuis cet environnement — à vérifier sur le
  jumpbox avant merge (indiqué dans la description de la PR).

---

## PR #190 — fix(db): sérialiser `run_migrations()` avec un advisory lock Postgres

**Date :** 2026-07-11
**Branche :** `fix/alembic-migration-lock` → `dev`

### Contexte

Repéré par Vincent en marge de la vérification jumpbox de la PR #188 (`alembic upgrade head`/`downgrade -1`) : `shared.db.run_migrations()` est appelée au démarrage par sept processus indépendants (`agents/offer_fetching`, `agents/matching`, `agents/match_analysis`, `agents/cv_analysis`, `agents/cleanup`, `agents/offer_distillation`, `agents/webapp`), chacun une instance de Container App Job ou le webapp, sans aucune sérialisation. Si deux instances démarrent dans la même fenêtre (deux triggers timer qui se chevauchent, un redéploiement qui recouvre un job déjà en cours), les deux peuvent lire la même révision Alembic courante avant que l'une des deux ait fini d'écrire la nouvelle — collision réelle possible entre deux `ALTER TABLE` concurrents sur la même table.

### Ce qui a été fait

- **`shared/db.py::run_migrations()`** : l'appel à `command.upgrade(cfg, "head")` est désormais encadré par un verrou consultatif Postgres session-level (`pg_advisory_lock`/`pg_advisory_unlock`, clé fixe `ALEMBIC_MIGRATION_LOCK_ID`), acquis sur une connexion dédiée (`isolation_level="AUTOCOMMIT"`, puisque ce type de verrou n'est pas lié à une transaction). Le deuxième appelant bloque jusqu'à ce que le premier libère le verrou ; à ce moment la migration est déjà appliquée, donc son propre `alembic upgrade head` est un no-op.
- Trois blocs `try/except` distincts (acquisition du verrou, `command.upgrade()`, libération du verrou en `finally`), chacun avec son propre event `structlog` (`alembic_migration_lock_failed`, `alembic_migrations_failed`, `alembic_migration_unlock_failed`) — pour ne jamais logguer un échec de migration comme un échec de verrou ou inversement.
- **`tests/test_db.py`** (nouveau) : trois tests — ordre verrou → upgrade → déverrouillage vérifié via un mock parent partagé (`attach_mock`, pour prouver l'ordre réel des appels plutôt que juste leur nombre) ; déverrouillage systématique même si l'upgrade échoue ; upgrade jamais appelée si l'acquisition du verrou échoue.

**Vérification :** `pytest` 247/247 (244 existants + 3 nouveaux). Pas de fichier `.tf` touché.

### Décisions techniques

- **Verrou session-level (`pg_advisory_lock`) plutôt que transactionnel (`pg_advisory_xact_lock`)** : `command.upgrade()` ouvre sa propre connexion (via `migrations/env.py::run_migrations_online()`, qui appelle le même `get_engine()`) — le verrou doit donc survivre indépendamment de la transaction de cette deuxième connexion et être libéré explicitement, pas au commit.
- **Couplage de pool documenté, pas éliminé** : la connexion qui tient le verrou et celle qu'utilise `command.upgrade()` viennent du même engine singleton (`@lru_cache`) — deux connexions du pool sont donc retenues simultanément le temps de la migration. Sans risque avec la configuration actuelle (`QueuePool` par défaut, `pool_size=5`), mais un commentaire explicite a été ajouté dans le code pour que `pool_size` ne soit jamais réduit à 1 sans revoir ce point.
- **`get_session()` non touchée** : son `except Exception:` nu (préexistant, même pattern que `shared/bus.py:124`) a été signalé par `reviewer-backend` comme une violation littérale de la convention Python, mais volontairement laissée en l'état — narrowing vers `SQLAlchemyError` casserait le rollback pour toute exception métier non-DB levée par un appelant dans son bloc `with`, une régression réelle et hors périmètre de ce fix.
- **4 passes de `reviewer-backend`** avant `APPROUVÉ` sans remarque : ordre constante/logger, `except Exception` trop large autour de `command.upgrade()`, double log avec un nom d'event trompeur en cas d'échec de migration (le `try/except SQLAlchemyError` englobait initialement tout le bloc), puis un test qui ne prouvait pas réellement l'ordre d'appel (deux mocks indépendants) — corrigés un à un. Dernière remarque non-bloquante (type hints manquants sur `tests/test_db.py`) également corrigée avant le verdict final.

---

## PR #191 — feat(infra): déployer le frontend Next.js comme Container App

**Date :** 2026-07-11
**Branche :** `feature/frontend-web-deployment` → `dev`

### Contexte

Premier des deux PR issus du prompt de handoff écrit par Claude Cowork le 2026-07-10
(`docs/prompts/prompt-frontend-web-deployment.md`) pour déployer le frontend Next.js
(`JobFinder/frontend/`) sur `jobfinder.vincentboutin.dev`, jusqu'ici jamais buildé ni
déployé en dehors du poste de dev. Le rattachement du domaine personnalisé lui-même est
volontairement hors périmètre de ce PR : il dépend d'une propagation DNS chez OVH
(enregistrements TXT/CNAME) que seul Vincent peut initier, et suivra dans un second PR
(`feature/frontend-custom-domain`) une fois cette propagation confirmée. La mise à jour
du redirect URI sur l'app registration Entra External ID (CIAM) est du même ressort —
action manuelle de Vincent, hors périmètre de Claude Code.

### Ce qui a été fait

- **`JobFinder/frontend/Dockerfile`** : ajout de 6 `ARG`/`ENV` (`NEXT_PUBLIC_ENTRA_CLIENT_ID`,
  `NEXT_PUBLIC_ENTRA_AUTHORITY`, `NEXT_PUBLIC_ENTRA_KNOWN_AUTHORITY`,
  `NEXT_PUBLIC_ENTRA_API_SCOPE`, `NEXT_PUBLIC_REDIRECT_URI`, `NEXT_PUBLIC_API_URL`), entre
  `COPY . .` et `RUN npm run build` — Next.js inline ces variables dans le bundle JS au
  moment du build, pas à l'exécution, donc des `env_vars` sur la Container App n'auraient
  aucun effet.
- **`JobFinder/Terraform/envs/dev/frontend.tf`** (nouveau) : `module "frontend"` réutilisant
  `modules/container_app` (même patron que `module "webapp"` dans `webapp.tf`), même
  environnement `cae-jf-dev-frc`, `target_port = 3000`, `min_replicas = 0`, sans secrets ni
  `env_vars` — tout est déjà figé dans l'image au build. Nouvel output
  `custom_domain_verification_id` sur `modules/container_app_environment/outputs.tf`, et deux
  nouveaux outputs sur `envs/dev/outputs.tf` (`frontend_url`,
  `container_app_environment_custom_domain_verification_id`) — à lire via `terraform output`
  après l'apply de ce PR pour que Vincent puisse créer les enregistrements TXT/CNAME chez OVH
  avant le PR de suivi.
- **`envs/dev/webapp.tf`** : `CORS_ALLOWED_ORIGINS` étendu de `"http://localhost:3000"` à
  `"http://localhost:3000,https://${var.frontend_custom_domain}"`. Suppression du commentaire
  devenu obsolète qui pointait vers cette tâche précise.
- **`envs/dev/variables.tf`** : ajout de `variable "frontend_custom_domain"` (type string,
  default `"jobfinder.vincentboutin.dev"`, validation regex format hostname DNS) — remplace le
  littéral précédemment codé en dur dans `CORS_ALLOWED_ORIGINS`. Nouvel
  `output "frontend_custom_domain"` sur `envs/dev/outputs.tf` (echo de la variable), aux côtés de
  `frontend_url` et `container_app_environment_custom_domain_verification_id` — les trois
  ensemble donnent à Vincent tout ce qu'il faut pour construire les enregistrements TXT/CNAME
  chez OVH via un seul `terraform output`.
- **`.github/workflows/buildAgents.yml`** : renommé de « Build Agent Images » à « Build
  Application Images » (n'est plus agent-only). Ajout de `JobFinder/frontend/**` au
  déclencheur de chemins, d'une étape `docker/build-push-action@v6` buildant
  `JobFinder/frontend/Dockerfile` avec les 6 build-args `NEXT_PUBLIC_*` sourcés depuis des
  variables de repo GitHub (`vars.*`, pas des secrets — mêmes précédent que
  `ENTRA_EXTERNAL_TENANT_ID`/`CLIENT_ID` côté backend), et d'un
  `az containerapp update --name app-jf-dev-frc-frontend ...` dans l'étape finale (renommée
  « Update Container App and Container App Job images », puisqu'elle met désormais aussi à
  jour une Container App qui n'est pas un Job).
- **`JobFinder/frontend/Dockerfile`** : fix `RUN npm ci` → `RUN mkdir -p public && npm ci`.
  Bug préexistant démasqué en vérifiant localement le build de ce Dockerfile (jamais buildé
  avant ce PR, `buildAgents.yml` n'incluait pas le frontend) : le postinstall de
  `pdfjs-dist` (`cp node_modules/pdfjs-dist/build/pdf.worker.min.js public/pdf.worker.min.js`)
  échouait car `public/` n'existait pas encore dans le contexte de build à ce stade — seuls
  `package.json`/`package-lock.json` avaient été `COPY`'s. Commentaire ajouté dans le Dockerfile
  pour expliquer pourquoi le répertoire doit être créé avant `npm ci`.

**Vérification :** `terraform fmt -check` et `terraform validate` sur `envs/dev` — OK en local.
`terraform plan` non exécuté localement (nécessite le backend Azure réel) — s'exécutera en CI
via `terraformPlan.yml` à l'ouverture du PR. Aucun `terraform apply` local (CI-only, convention
du projet). `docker build` du `Dockerfile` frontend exécuté localement avec des build-args
`NEXT_PUBLIC_*` factices : succès après le fix `mkdir -p public`. `docker run -p 3000:3000` sur
l'image obtenue puis `curl http://localhost:3000/` → HTTP 200. Conteneur et image supprimés
(`docker stop`, `docker rmi`) après vérification.

### Décisions techniques

- **`frontend_custom_domain` en variable plutôt qu'en littéral dupliqué** : `CORS_ALLOWED_ORIGINS`
  ne peut de toute façon pas référencer `module.frontend.fqdn` — ce dernier renverrait le FQDN par
  défaut `*.azurecontainerapps.io` tant que le domaine personnalisé n'est pas rattaché (PR de
  suivi), pas le domaine cible. Plutôt que coder le domaine en dur ici et le retaper dans le PR 2
  pour la ressource `azurerm_container_app_custom_domain`, il est déclaré une seule fois comme
  variable (`envs/dev/variables.tf`) : source de vérité unique partagée entre l'usage CORS de ce
  PR et le rattachement du domaine dans le PR 2, qui référencera `var.frontend_custom_domain` au
  lieu de retaper le littéral. La valeur par défaut de la variable reste le domaine cible réel
  (`jobfinder.vincentboutin.dev`) — seul le mécanisme change (variable au lieu de littéral), le
  comportement au moment de l'apply est identique.
- **`NEXT_PUBLIC_*` en build-args, jamais en secrets GitHub** : ces valeurs finissent inlinées en
  clair dans le bundle JS servi au navigateur — les traiter comme des secrets donnerait une
  fausse impression de confidentialité sans bénéfice réel.
- **Découpage en deux PR** : ce PR déploie l'infrastructure et l'image avec le FQDN par défaut ;
  le rattachement du domaine personnalisé (ressource de certificat managé + binding) attend une
  propagation DNS externe hors du contrôle de Claude Code, d'où le second PR
  `feature/frontend-custom-domain`, ouvert seulement après confirmation de Vincent.
- **Fix du bug `npm ci`/`public/` corrigé dans ce PR plutôt que différé** : bug préexistant, sans
  lien direct avec l'objectif du PR (déploiement Container App), mais bloquant pour la propre
  étape de vérification de ce PR — impossible de valider que l'image se build et démarre
  correctement sans corriger d'abord ce point. Déployer une Container App dont l'image ne build
  même pas n'a aucun sens ; le fix reste donc dans le périmètre.
