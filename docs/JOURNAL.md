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
- **Exemple entrée→sortie complet** à la place de l'exemple de sortie seule : l'intention en entrée est montrée (une reconversion vers un domaine technique, une certification obtenue, un projet personnel en cours), puis le ❌ (générique, ignore l'intention) et le ✅ (cite l'élément trouvé dans l'intention) — le modèle voit le lien de cause à effet.

**Vérification :** `pytest tests/test_match_analysis.py -v` — 15 passed sans modification (aucun changement de schéma JSON). Le test manuel reste à faire : rejouer un cas de profil en reconversion vs offre technique et vérifier que `suggestion_concrete` référence un élément identifiable du profil.

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
- **Test manuel qualitatif en attente de déploiement** : relire une analyse générée sur un CV réel — aucun fait répété entre `synthese`/`points_faibles`/`suggestions`, au moins un point ancré sur un élément nommé du CV, au moins une suggestion appuyée sur l'intention du profil.

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

Exécution de `docs/prompts/prompt-matching-remove-lexical-bonus.md`. Décision actée avec Vincent le 09/07 : sur 6 offres réelles diagnostiquées, aucune formule purement statistique sur des mots isolés ne peut distinguer un terme rare-mais-pertinent d'un terme rare-mais-hors-sujet (ex. « sport » d'une offre QA, « jeux » d'un CV issu d'un domaine sans lien avec l'offre) — le bonus lexical est retiré entièrement, pas juste corrigé. Le score final devient `GREATEST(0, base_score - pénalité_expérience)`.

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

Exécution de `docs/prompts/prompt-profile-decouple-experience-intent.md`, suite du retrait du bonus lexical (PR #185) et du pipeline de distillation (PR #184). Diagnostic du 09/07 (Vincent, son propre profil vs une offre réelle `ft_id 3976333`) : `base_score` en production tombait à 0.4971 — juste sous `MATCHING_SCORE_THRESHOLD = 0.5` — alors que la similarité CV↔offre distillée mesurée séparément était de ~0.696. Cause : `_build_intent_text` combinait une phrase générique dérivée d'`experience_level` (ex. « Profil confirmé, 2 à 5 ans d'expérience ») avec `candidate_description` ; quand cette dernière est vide (cas de Vincent), `intent_text` se réduisait à cette seule phrase, quasiment vide de contenu sémantique distinctif une fois embedée, et suffisait à faire chuter un excellent match sous le seuil une fois mélangée à 30 % (`INTENT_EMBEDDING_WEIGHT`) dans le score final.

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

---

## PR #192 — fix(claude): parité entre le reviewer CI et les subagents reviewer-*

**Date :** 2026-07-11
**Branche :** `feature/reviewer-ci-context-parity` → `dev`

### Contexte

Vincent a remarqué que le reviewer CI (`.github/workflows/reviewerAgent.yml`) est systématiquement plus pointilleux que les subagents `reviewer-backend`/`reviewer-frontend`/`reviewer-infra` déclenchés localement par Claude Code, alors que les deux sont censés appliquer les mêmes conventions. Investigation en deux temps.

### Ce qui a été fait

**1. Écart de critères et de seuil de blocage entre les subagents (`.claude/agents/reviewer-*.md`)**

- Les trois subagents ne bloquaient que sur une règle explicitement phrasée « jamais/toujours » ; tout le reste (docstring manquante, fonction >40 lignes, règle « obligatoire » non phrasée en absolu…) était systématiquement déclassé en remarque non-bloquante. Le prompt CI, lui, bloque par défaut sur toute violation d'une convention de CLAUDE.md sauf mention contraire explicite. Reformulé le critère de blocage dans les trois fichiers pour adopter le même défaut.
- `reviewer-backend` n'avait aucun équivalent à la section « Senior Python review (beyond conventions) » du prompt CI. 4 des 5 règles bloquantes de cette section étaient déjà couvertes par le skill `conventions-python` (context managers, env vars au niveau module, `raise` nu, pas d'`except Exception` nu) — seul le pattern N+1 (bloquant) et trois remarques (batch vs boucle unitaire, portée de transaction, `load_dotenv()` manquant) manquaient réellement. Ajoutés à `reviewer-backend.md`.
- Confirmé sur l'historique réel (PR #188) : le CI avait flaggé deux fois un pattern N+1 dans `_embed_pending_offers` qu'un `reviewer-backend` local n'aurait pas pu détecter faute de cette règle.

**2. Le reviewer CI ne recevait jamais les fichiers de skills (`.github/workflows/reviewerAgent.yml`, `.github/reviewer-agent/system-prompt.md`)**

- Écart plus sérieux : `reviewerAgent.yml` n'a jamais envoyé au reviewer CI que le contenu de `CLAUDE.md`. Or depuis la migration des conventions vers `.claude/skills/` (commit `b2e8e94`), `CLAUDE.md` ne fait plus que pointer vers les skills pour Terraform/Python/SQL/Frontend — le détail (nommage Azure, docstrings, format `structlog`, conventions Alembic/SQLAlchemy, conventions frontend) vit uniquement dans `.claude/skills/*/SKILL.md`. Le reviewer CI était donc structurellement aveugle à ces quatre domaines entiers depuis cette migration, alors que `CLAUDE.md` gardait en clair les sections Sécurité/Coût/Lifecycle/Blocking criteria — ce qui explique pourquoi le CI restait fiable sur ces points précis tout en ratant le reste.
- `reviewerAgent.yml` récupère désormais la liste des fichiers modifiés de la PR (`gh api pulls/$PR_NUMBER/files`) et charge uniquement les `SKILL.md` pertinents selon l'extension/le chemin des fichiers touchés (`.tf` → `conventions-terraform`, `JobFinder/python/migrations/` ou `models.py` → `conventions-sql`, `JobFinder/python/` → `conventions-python`, `JobFinder/frontend/` → `conventions-frontend`), pour ne pas gonfler le prompt inutilement sur les PR qui ne touchent qu'une seule catégorie.
- `system-prompt.md` mis à jour pour refléter que les skills font maintenant partie du contexte fourni, et sa section « Senior Python review » réduite au seul item réellement absent du skill (N+1) — les quatre autres dupliquaient désormais ce que `conventions-python` couvre directement.

**Vérification :** YAML validé (`yaml.safe_load`), bloc Python du heredoc extrait et validé (`py_compile`). Pas de vérification end-to-end possible depuis cet environnement (nécessite un run du workflow sur une vraie PR avec `CLAUDE_API_KEY`/`REVIEWER_GITHUB_TOKEN`) — à surveiller sur la prochaine PR touchant du Terraform/Python/SQL/frontend.

### Décisions techniques

- **Chargement des skills filtré par fichiers touchés, pas systématique** : charger les 4 skills sur chaque PR aurait été plus simple mais aurait gonflé inutilement le prompt (et le coût) des PR qui ne touchent qu'une seule catégorie — la plupart des PR de ce projet respectent déjà la règle « jamais mélanger plateforme et appli » de CLAUDE.md, donc une PR ne touche généralement qu'une ou deux catégories.
- **`conventions-sql` déclenché aussi par `models.py`, pas seulement par les migrations** : `shared/models.py` porte les conventions SQLAlchemy (clés UUID, nommage des contraintes) même hors contexte de migration Alembic.

---

## PR #193 — feat(infra): rattacher le domaine personnalisé et le certificat managé au frontend

**Date :** 2026-07-11
**Branche :** `feature/frontend-custom-domain` → `dev`

### Contexte

Second des deux PR du déploiement du frontend Next.js sur `jobfinder.vincentboutin.dev`. Le PR #191
(déjà mergé) a déployé le frontend comme Container App sur son FQDN par défaut
`*.azurecontainerapps.io`, et exposé deux outputs Terraform (`frontend_url`,
`container_app_environment_custom_domain_verification_id`) nécessaires à Vincent pour créer les
enregistrements DNS chez OVH. Entre les deux PR, Vincent a créé ces enregistrements : un `CNAME` sur
`jobfinder.vincentboutin.dev` pointant vers le FQDN par défaut de la Container App, et un `TXT` sur
`asuid.jobfinder.vincentboutin.dev` portant l'ID de vérification de l'environnement. Les deux ont été
confirmés propagés (`Resolve-DnsName` sur les deux types d'enregistrement, valeurs identiques) avant
l'écriture des changements Terraform de ce PR.

### Ce qui a été fait

- **`JobFinder/Terraform/envs/dev/frontend.tf`** : ajout de deux ressources après le bloc
  `module "frontend"` existant.
  1. `azurerm_container_app_environment_managed_certificate.frontend` — certificat TLS managé
     gratuit pour `var.frontend_custom_domain` (`subject_name`), `domain_control_validation =
     "CNAME"` (Azure valide en vérifiant que le CNAME déjà créé chez OVH résout vers l'app, plutôt
     que par le challenge `HTTP` par défaut) — nécessite donc que le CNAME/TXT décrits ci-dessus
     soient déjà propagés avant l'apply. Tags environment/project/owner.
  2. `azurerm_container_app_custom_domain.frontend` — rattache `var.frontend_custom_domain` à
     `module.frontend.id`, référence le certificat managé via
     `container_app_environment_certificate_id`, `certificate_binding_type = "SniEnabled"`.
  - Les deux types de ressource et chaque nom d'attribut ont été vérifiés contre le schéma réel du
    provider azurerm 4.72.0 installé (`terraform providers schema -json`) plutôt que devinés depuis
    les données d'entraînement — la syntaxe de ces ressources a changé selon les versions du
    provider azurerm, piège déjà documenté par le projet.
- Le commentaire WHY déjà présent en tête de section (prérequis DNS, pourquoi `CNAME` et non `HTTP`)
  a été relu contre le diff final : exact, non redondant avec le code — laissé inchangé.

**Vérification :** `terraform fmt -check` et `terraform validate` sur `envs/dev` — OK en local.
`terraform plan` non exécuté localement (nécessite le backend Azure réel) — s'exécutera en CI via
`terraformPlan.yml` à l'ouverture du PR. Aucun `terraform apply` local (CI-only, convention du
projet). `reviewer-infra` a revu ce diff exact et retourné APPROUVÉ, zéro remarque non-bloquante.

### Décisions techniques

- **`domain_control_validation = "CNAME"` plutôt que le défaut `HTTP`** : le CNAME
  `jobfinder.vincentboutin.dev` → FQDN de la Container App existe déjà et est propagé (prérequis de
  ce PR) — Azure peut donc valider la propriété du domaine en constatant que ce CNAME résout déjà
  vers l'app, sans challenge HTTP additionnel à orchestrer séparément.
- **`container_app_environment_certificate_id` malgré un certificat « managed »** : c'est le nom
  d'attribut documenté par le schéma du provider azurerm pour rattacher un certificat *managé* (créé
  et renouvelé par Azure) à un `azurerm_container_app_custom_domain`.
  `container_app_environment_managed_certificate_id` existe bien comme nom mais désigne un attribut
  calculé (read-only), pas un argument qu'on peut fournir en entrée — confusion facile vu la
  proximité des deux noms, d'où l'intérêt de vérifier le schéma plutôt que de deviner.
- **Vérification par schéma provider plutôt que confiance dans la syntaxe connue** : la syntaxe
  Terraform de ces deux types de ressource a changé entre versions successives d'azurerm (avertissement
  déjà présent dans les conventions du projet) — écrire ces ressources sans vérifier le schéma réel de
  la version 4.72.0 installée risquait un échec silencieux ou tardif (`validate` OK mais `plan`/`apply`
  en échec faute d'attribut reconnu).

---

## PR #194 — refactor(frontend): remplacer le bouton Postuler (stub non persisté) par un lien Consulter l'offre

**Date :** 2026-07-11
**Branche :** `feature/offer-consult-link` → `dev`

### Contexte

Sur la page de correspondances, le bouton « Postuler » d'une carte d'offre dépliée ne faisait que basculer un état local (`applied`) — un stub jamais persisté côté backend, marqué d'un commentaire `// TODO: persist applied state to backend`. Demande utilisateur : renommer ce bouton en « Consulter l'offre » et le faire pointer vers la page d'offre France Travail, plutôt que d'implémenter la persistance du stub.

### Ce qui a été fait

- **`MatchItem.tsx`** : le bouton devient un lien `<a>` vers `${FT_OFFER_URL}/${offer.ft_id}` (ouvert dans un nouvel onglet), le même motif d'URL déjà utilisé par le lien du titre de l'offre. Libellé « Consulter l'offre ».
- **`MatchItem.tsx`** : `isApplied` et `onApply` retirés de l'interface `MatchItemData` — un grep sur l'ensemble du dépôt a confirmé qu'aucun autre consommateur ne lisait cet état, uniquement utilisé pour désactiver/relabelliser ce bouton.
- **`CorrespondancesPanel.tsx`** : état `applied`/`setApplied` et le commentaire obsolète qui s'y référait supprimés — plus rien ne les alimentait une fois `onApply` retiré de `MatchItemData`.
- **Tests (`MatchItem.test.tsx`, `MatchList.test.tsx`)** : fixtures et assertions alignées sur le nouveau lien (`getByRole("link", { name: "Consulter l'offre" })`, vérification de `href` contenant le `ft_id` et de `target="_blank"`) ; références à `isApplied`/`onApply` retirées des builders de props.

**Vérification :** Jest, `tsc --noEmit` et ESLint propres (exécutés avant la revue de doc). Grep du dépôt entier sur `isApplied|onApply|applied|Postuler` : aucune occurrence restante.

### Décisions techniques

- **Suppression complète de `isApplied`/`onApply` plutôt que dépréciation progressive** : ce n'était pas un état métier réel — jamais persisté côté backend, sans autre lecteur dans le code — donc le garder « au cas où » aurait juste laissé du code mort à côté du nouveau lien.

---

## PR #195 — fix(infra): résoudre le deadlock d'ordre de création domaine/certificat du frontend

**Date :** 2026-07-11
**Branche :** `fix/frontend-custom-domain-two-phase` → `dev`

### Contexte

Le `terraform apply` du PR #193 (mergé) a échoué en CI avec une vraie erreur d'API Azure :

```
Error: creating Managed Certificate ...: unexpected status 400 (400 Bad Request) with error:
RequireCustomHostnameInEnvironment: Creating managed certificate requires hostname
'jobfinder.vincentboutin.dev' added as a custom hostname to a container app or route
in environment 'cae-jf-dev-frc'
```

Cause racine : Azure exige que le hostname soit déjà enregistré comme domaine personnalisé sur la
Container App avant de pouvoir créer un certificat managé pour ce hostname. Or le code du PR #193
faisait référencer par `azurerm_container_app_custom_domain.frontend` l'`.id` du certificat managé
(`container_app_environment_certificate_id`), ce qui poussait Terraform à créer le certificat
*avant* le domaine personnalisé — l'inverse de ce qu'Azure impose. Un vrai interblocage d'ordre de
création à l'intérieur d'un seul apply, indépendant de la propagation DNS déjà gérée par le PR #193.

### Ce qui a été fait

- **`JobFinder/Terraform/envs/dev/frontend.tf`** — passage à une création en deux phases :
  - `azurerm_container_app_custom_domain.frontend` : retrait de
    `container_app_environment_certificate_id`, `certificate_binding_type` mis explicitement à
    `"Disabled"`. Phase 1 : le hostname est enregistré comme domaine personnalisé sans référencer
    aucun certificat, donc plus aucune raison au niveau attribut pour Terraform de créer le
    certificat en premier.
  - `azurerm_container_app_environment_managed_certificate.frontend` : ajout de
    `depends_on = [azurerm_container_app_custom_domain.frontend]` — une arête de dépendance
    explicite (pas une référence d'attribut) qui force la création du domaine personnalisé avant
    celle du certificat, ce qui correspond à la précondition réelle imposée par Azure.
  - Phase 2 n'est **pas** dans ce commit : un commit de suivi, seulement une fois cet apply phase 1
    passé en CI, réintroduira `certificate_binding_type = "SniEnabled"` et
    `container_app_environment_certificate_id = azurerm_container_app_environment_managed_certificate.frontend.id`
    sur `azurerm_container_app_custom_domain.frontend`.
  - Commentaire WHY ajouté au-dessus des deux ressources expliquant l'interblocage et les deux
    phases, et un second expliquant pourquoi `azurerm_container_app_custom_domain` n'a pas de bloc
    `tags` (attribut absent du schéma du provider pour ce type de ressource — même catégorie
    d'exception que `azurerm_subnet`, voir `conventions-terraform`).
- **`JobFinder/Terraform/envs/dev/outputs.tf`** : description de l'output `frontend_custom_domain`
  corrigée — elle disait encore « pas encore rattaché », alors que le rattachement est en cours
  (phase 1 appliquée, phase 2 à venir).

**Vérification :** `terraform fmt -check` et `terraform validate` sur `envs/dev` — OK en local.
`terraform plan` n'a **pas** pu être exécuté localement cette fois — la variable `alert_email` est
requise et le `.tfvars` local est gitignored par convention du projet, donc pas de valeurs
disponibles en local pour la lancer. L'absence de diff Terraform inattendu repose donc sur le
raisonnement fait à partir du schéma du provider et du graphe de dépendances (attribut retiré côté
domaine, `depends_on` ajouté côté certificat), pas sur un `plan` réel — sera confirmé par
`terraformPlan.yml` en CI à l'ouverture de la PR. Aucun `terraform apply` local (CI-only, convention
du projet). `reviewer-infra` a revu ce diff exact et retourné APPROUVÉ, avec deux remarques non
bloquantes (description d'output obsolète, commentaire `tags` manquant) — toutes deux déjà corrigées
avant ce passage doc-writer.

### Décisions techniques

- **`depends_on` plutôt qu'une référence d'attribut pour forcer l'ordre** : les deux ressources n'ont,
  en phase 1, plus aucun attribut en commun (le domaine ne référence plus le certificat), donc
  Terraform n'a par défaut aucune information pour les ordonner. `depends_on` est le seul mécanisme
  disponible pour exprimer une contrainte d'ordre purement opérationnelle (imposée par l'API Azure,
  pas par un flux de données Terraform) sans réintroduire la référence d'attribut qui a causé le
  problème initial.
- **`certificate_binding_type = "Disabled"` explicite plutôt qu'omis** : `Disabled` est déjà la
  valeur par défaut de cet attribut dans le schéma du provider, donc l'omettre aurait un effet
  identique — mais l'écrire explicitement documente l'intention (« phase 1, volontairement sans
  certificat ») pour quiconque relit ce fichier avant que le commit de phase 2 n'arrive, plutôt que
  de laisser deviner si l'absence de l'attribut est un oubli ou un choix.
- **Phase 2 reportée à un commit séparé, après succès de la phase 1 en CI** : appliquer les deux
  phases dans le même commit reproduirait exactement le bug du PR #193 dans le state initial (aucune
  ressource existante, donc l'ordre de création dépendrait à nouveau des références d'attribut plutôt
  que d'un `depends_on` déjà résolu par un apply antérieur). Séparer les deux commits garantit que la
  phase 2 s'applique comme une mise à jour sur place d'un domaine personnalisé déjà existant, pas
  comme une création concurrente au certificat.
- **Pas de `ForceNew` sur les attributs concernés par la phase 2** : vérifié via
  `terraform providers schema -json` contre azurerm 4.72.0 — `certificate_binding_type` et
  `container_app_environment_certificate_id` sur `azurerm_container_app_custom_domain` ne sont pas
  `ForceNew`, donc le commit de phase 2 sera un `update` en place, pas un `destroy`/`create` du
  domaine personnalisé.

---

## PR #196 — feat(infra): rattacher le certificat managé au domaine personnalisé (phase 2 du PR #195)

**Date :** 2026-07-11
**Branche :** `feature/frontend-custom-domain-phase2` → `dev`

### Contexte

Le PR #195 (mergé, appliqué avec succès en CI) a résolu l'interblocage d'ordre de création
domaine/certificat en le découpant en deux phases : phase 1 enregistre le domaine personnalisé
sans référence de certificat (`certificate_binding_type = "Disabled"`), avec un `depends_on`
forçant le certificat managé à se créer après. Confirmé après coup via `az containerapp env
certificate list` / `az containerapp hostname list` (lecture seule) : certificat
`ProvisioningState: Succeeded`, hostname enregistré avec `BindingType: Disabled`. Cette PR est la
phase 2, annoncée mais volontairement reportée par le PR #195 : rattacher effectivement le
certificat au domaine.

### Ce qui a été fait

- **`JobFinder/Terraform/envs/dev/frontend.tf`** — `azurerm_container_app_custom_domain.frontend` :
  `certificate_binding_type` passé de `"Disabled"` à `"SniEnabled"`. Deux tentatives incorrectes
  avant la version finale, chacune interceptée par `reviewer-infra` avant tout `terraform apply`
  réel :
  - **1ère tentative** : `container_app_environment_certificate_id =
    azurerm_container_app_environment_managed_certificate.frontend.id`. Attribut incorrect — il
    attend un certificat *bring-your-own* uploadé (`azurerm_container_app_environment_certificate`,
    chemin ARM `.../certificates/...`), pas un certificat managé (chemin ARM
    `.../managedCertificates/...`). C'est précisément l'attribut que le PR #195 annonçait vouloir
    réintroduire en phase 2 — le raisonnement de ce PR précédent reposait donc lui-même sur le
    mauvais attribut. Erreur détectée par un `terraform plan` réel (échec dur de parsing d'ID ARM),
    pas par simple lecture du schéma.
  - Cette tentative nécessitait aussi de retirer le `depends_on =
    [azurerm_container_app_custom_domain.frontend]` posé en phase 1 sur le certificat managé —
    le garder tout en ajoutant cette référence d'attribut aurait créé un vrai cycle de dépendance
    (le domaine dépend du certificat via l'attribut, le certificat dépend du domaine via
    `depends_on`).
  - **Version finale correcte** : aucune référence de certificat sur le domaine personnalisé —
    seulement `certificate_binding_type = "SniEnabled"`.
    `container_app_environment_managed_certificate_id` (le champ qui référencerait un certificat
    managé) est en lecture seule (Computed) côté schéma provider — Azure le résout lui-même en
    faisant correspondre le `subject_name` du certificat managé à ce hostname. Confirmé par un
    `terraform plan` réel : plan propre, et `azurerm_container_app_environment_managed_certificate.frontend`
    affiche zéro changement planifié (le certificat `Succeeded` existant n'est pas touché).
  - Commentaires WHY au-dessus de la ressource mis à jour en conséquence (pourquoi aucune référence
    de certificat n'est nécessaire, pourquoi `container_app_environment_certificate_id` serait le
    mauvais choix).
- **`docs/BACKLOG.md`** — entrée `[urgent]` ajoutée : `modules/container_app/outputs.tf` calcule
  l'output `fqdn` depuis `azurerm_container_app.this.latest_revision_fqdn`, avec un commentaire du
  module affirmant que c'est « stable in Single revision mode ». Le `terraform plan` réel de cette
  PR a prouvé le contraire — la valeur a changé (`--0000002` → `--0000003`) sur un `update in-place`
  déclenché par un drift totalement indépendant (retrait de `workload_profile_name`, pré-existant).
  Impact concret : le CNAME configuré manuellement chez OVH pour `jobfinder.vincentboutin.dev`
  pointe sur une copie figée d'une valeur passée de `frontend_url`, qui peut donc devenir
  silencieusement obsolète à tout déploiement futur. Correction cible documentée
  (`ingress[0].fqdn` au lieu de `latest_revision_fqdn`), explicitement hors scope de cette PR — un
  changement de `modules/` doit passer par sa propre PR dédiée avant toute PR applicative qui en
  dépend, selon le git flow de CLAUDE.md.

**Vérification :** `terraform fmt -check` et `terraform validate` OK sur `envs/dev`. Cette fois,
`terraform plan` a pu être exécuté réellement en local (lecture seule, avec un `-var
alert_email=...` de contournement puisque le `.tfvars` local est gitignored) — plan propre,
confirmé qu'aucune ressource non liée n'est recréée par effet de cascade :
`module.frontend.azurerm_container_app.this` et `module.webapp.azurerm_container_app.this`
n'affichent que le drift pré-existant sans rapport (`workload_profile_name`), pas de replacement
déclenché par ce changement. `reviewer-infra` a revu la diff finale (3ème version, correcte) de
`frontend.tf` et retourné APPROUVÉ, avec une remarque non bloquante déjà corrigée avant ce passage
doc-writer (le commentaire affirmait à tort ce que le schéma statique du provider peut démontrer
sur `ForceNew` — reformulé pour ne décrire que le comportement observé du plan réel, pas une
affirmation invérifiable sur le fonctionnement interne du provider).

### Décisions techniques

- **Aucune référence de certificat sur le domaine personnalisé, plutôt que réintroduire l'attribut
  annoncé par le PR #195** : le PR #195 avait anticipé que la phase 2 réintroduirait
  `container_app_environment_certificate_id` pointant sur le certificat managé — un attribut qui,
  vérifié cette fois par un `terraform plan` réel et non par simple lecture du schéma, se révèle
  être le mauvais champ (bring-your-own vs managé). Le rattachement réel se fait uniquement via
  `certificate_binding_type = "SniEnabled"` ; Azure résout la correspondance de certificat de façon
  interne, sans qu'aucun attribut Terraform explicite ne soit nécessaire ou possible côté domaine.
- **`-/+ destroy and then create replacement` accepté malgré la prédiction contraire du PR #195** :
  le PR #195 concluait, sur la seule base de `terraform providers schema -json` (aucun attribut
  marqué `ForceNew`), que la phase 2 serait une mise à jour en place. Le `terraform plan` réel de
  cette PR contredit cette prédiction : la transition `"Disabled"` → `"SniEnabled"` déclenche un
  remplacement du domaine personnalisé, un comportement provider-side non visible dans le schéma
  statique. Accepté tel quel pour dev — pas de SLA, miroir prod reporté à v1.0.0 selon CLAUDE.md —
  et la fenêtre de dissociation du domaine pendant l'apply est brève et isolée à cette seule
  ressource (pas de cascade vers les Container Apps frontend/webapp, confirmé par le plan).
- **Anomalie `fqdn` instable versée au backlog plutôt que corrigée dans cette PR** : la correction
  touche `modules/container_app/`, un module partagé, alors que cette PR ne touche que
  `envs/dev/frontend.tf`. Mélanger une correction de module dans une PR applicative violerait la
  règle du git flow de CLAUDE.md (les changements de `modules/` accompagnant une feature applicative
  passent par une PR dédiée d'abord). Marquée `[urgent]` plutôt que `[optional]` parce que le risque
  concret (CNAME OVH périmé silencieusement) existe dès le prochain déploiement, pas seulement en
  théorie.

---

## PR #197 — fix(infra): stabiliser l'output `fqdn` du module container_app

**Date :** 2026-07-11
**Branche :** `fix/container-app-fqdn-stability` → `dev`

### Contexte

Le PR #196 avait versé au backlog (`[urgent]`) l'anomalie de `modules/container_app/outputs.tf` :
l'output `fqdn` était calculé depuis `azurerm_container_app.this.latest_revision_fqdn`, avec un
commentaire affirmant à tort que cette valeur était « stable in Single revision mode » — réfuté par
un `terraform plan` réel du PR #196 où un drift totalement indépendant (retrait de
`workload_profile_name`) avait à lui seul fait bumper le suffixe de révision (`--0000002` →
`--0000003`).

Cette anomalie est devenue concrètement bloquante entre les deux PR : le CNAME configuré
manuellement chez OVH pour `jobfinder.vincentboutin.dev` pointait sur une copie figée d'une valeur
passée de `frontend_url`, devenue obsolète suite à un déploiement — le site est devenu inaccessible,
confirmé directement par l'utilisateur (« je peux pas accéder à mon app »).

### Ce qui a été fait

- **`JobFinder/Terraform/modules/container_app/outputs.tf`** — l'output `fqdn` utilise désormais
  `azurerm_container_app.this.ingress[0].fqdn` au lieu de `azurerm_container_app.this.latest_revision_fqdn`.
- **`docs/BACKLOG.md`** — l'entrée `[urgent]` correspondante marquée `[RÉSOLU — PR #197]`.

**Vérification :** `terraform fmt -check` et `terraform validate` OK. Confirmé via
`terraform providers schema -json` (azurerm 4.72.0) que `ingress.fqdn` est bien un attribut
app-level, non lié à une révision — sa description de schéma dit simplement « The FQDN of the
ingress », alors que celle de `latest_revision_fqdn` dit explicitement « Latest Revision ». Un
`terraform plan -var alert_email=...` réel (lecture seule, local) confirme un impact strictement
limité aux valeurs d'output (`frontend_url` et `webapp_url` perdent leur suffixe de révision) : zéro
action de niveau ressource — un output est une projection en lecture seule, il ne peut par
construction déclencher aucun changement de ressource. Blast radius vérifié également en dehors du
plan : `CORS_ALLOWED_ORIGINS` (`webapp.tf`) utilise un domaine littéral en dur, pas
`module.webapp.fqdn`/`module.frontend.fqdn` — les seuls consommateurs réels de ces outputs de module
sont les passthroughs `webapp_url`/`frontend_url` d'`envs/dev/outputs.tf`. `reviewer-infra` a revu
ce diff exact et retourné APPROUVÉ.

### Décisions techniques

- **`ingress[0].fqdn` plutôt que `latest_revision_fqdn`** : confirmé par le schéma du provider que
  c'est l'attribut réellement app-level (constant tant que la configuration d'ingress elle-même ne
  change pas), alors que `latest_revision_fqdn` inclut le suffixe de révision courant et change à
  chaque nouvelle révision — y compris pour des changements sans rapport avec le contenu applicatif,
  comme observé dans le PR #196.
- **PR dédiée au module, avant la correction applicative qui en dépend** : ce fix ne touche que
  `modules/container_app/outputs.tf`, rien dans `envs/`. Conforme au git flow de CLAUDE.md — un
  changement de `modules/` qui accompagne une feature applicative passe par sa propre PR d'abord.
  Ici en particulier : le rattachement du certificat/domaine personnalisé du frontend (PR #195/#196)
  dépend indirectement de la stabilité de `frontend_url` pour la configuration DNS externe (CNAME
  OVH) — cette correction de module doit donc être mergée et son effet vérifié avant toute future PR
  qui retoucherait ce binding.

---

## PR #198 — fix(infra): bind managed certificate via azapi, azurerm cannot do it

**Date :** 2026-07-11
**Branche :** `fix/frontend-custom-domain-certificate-azapi` → `dev`

### Contexte

Le PR #196 avait appliqué avec succès, selon Terraform, le rattachement du certificat managé au
domaine personnalisé du frontend (`certificate_binding_type = "SniEnabled"`). En réalité,
`jobfinder.vincentboutin.dev` restait inaccessible : `az containerapp hostname list` (lecture
seule) montrait `bindingType: Disabled` côté état réel Azure, malgré un state Terraform affichant
`SniEnabled`.

Root cause confirmée cette fois en lisant directement le code Go du provider azurerm (pas
seulement sa documentation) : l'argument `container_app_environment_certificate_id` de
`azurerm_container_app_custom_domain` porte un validateur côté client qui n'accepte que les ID ARM
de certificats *bring-your-own* (`.../certificates/...`) et rejette explicitement les ID de
certificats managés Azure (`.../managedCertificates/...`). C'est un manque amont confirmé et
toujours ouvert (hashicorp/terraform-provider-azurerm issues #25788 et #27362) — la documentation
officielle du provider recommande elle-même comme contournement un `lifecycle { ignore_changes =
[...] }` combiné à un rattachement manuel hors bande, ce que le workflow CI Terraform-only de ce
projet ne permet pas.

### Ce qui a été fait

- **`JobFinder/Terraform/envs/dev/frontend.tf`** :
  - `azurerm_container_app_custom_domain.frontend` figé au seul état qu'il peut réellement
    atteindre (`certificate_binding_type = "Disabled"`, aucune référence de certificat) via
    `lifecycle.ignore_changes` sur `certificate_binding_type` et
    `container_app_environment_certificate_id` — Terraform arrête ainsi d'essayer, et d'échouer, à
    réconcilier un état hors de portée de cette ressource.
  - Nouvelle ressource `azapi_update_resource.frontend_custom_domain_binding` : PATCH direct de
    `Microsoft.App/containerApps@2024-03-01`, `properties.configuration.ingress.customDomains`,
    via l'API ARM — le même appel que fait `az containerapp hostname bind` en interne, qui accepte
    nativement les ID de certificat managé (contrairement au validateur côté client d'azurerm).
    `depends_on` explicite sur le domaine personnalisé et le certificat managé, nécessaire car
    aucun des deux n'est référencé par attribut à l'intérieur de `body` (pas d'arête de graphe
    implicite sinon).
- **`JobFinder/Terraform/envs/dev/main.tf`** : provider `azapi` (`azure/azapi ~> 2.0`) ajouté à
  `required_providers`, authentifié via les mêmes variables d'environnement `ARM_*` (OIDC) déjà
  injectées en CI pour azurerm — aucun changement de workflow CI nécessaire.
- **`.terraform.lock.hcl`** : entrée `azure/azapi` ajoutée ; `azurerm` volontairement laissé pincé
  à `4.72.0` (voir Décisions techniques).

**Vérification :** `terraform fmt -check` et `terraform validate` OK sur `envs/dev`. Un
`terraform plan` réel a été exécuté en local contre le state distant (pas seulement une inspection
de schéma/documentation) : diff nul sur la ressource `azurerm_container_app_custom_domain`
existante (aucune tentative de replacement/destroy déclenchée par l'ajout du `lifecycle
ignore_changes`), et création propre de la nouvelle ressource `azapi_update_resource` sans effet de
bord sur les autres ressources du module frontend.

### Décisions techniques

- **`azapi_update_resource` en complément d'azurerm plutôt qu'un contournement hors Terraform** :
  le contournement documenté en amont (`ignore_changes` + rattachement manuel via le portail ou
  `az containerapp hostname bind`) est incompatible avec le workflow CI Terraform-only de ce
  projet (`terraformApply.yml` applique sans étape manuelle possible). Le provider `azapi` permet
  de rester dans Terraform en patchant directement l'API ARM sous-jacente, là où azurerm a un vrai
  trou de couverture confirmé en amont (issues encore ouvertes), sans introduire d'étape manuelle
  ni de script externe au pipeline.
- **Risque résiduel assumé, pas éliminé** : `azapi_update_resource` fait un merge-patch au niveau
  Terraform (seuls les chemins listés dans `body` sont touchés), mais le comportement de fusion de
  l'objet `ingress` complet côté API ARM elle-même n'est ni contrôlé ni garanti par le provider
  Terraform — rien ne prouve qu'un futur apply ne réinitialisera pas silencieusement
  `target_port`/`external`/`transport`/`traffic`. Un `terraform plan` propre ne peut pas détecter ce
  risque-là (il porte sur le state Terraform, pas sur un comportement serveur ARM non modélisé).
  Ce projet a déjà été pris en défaut une fois (PR #196) par une hypothèse non vérifiée sur le
  comportement de cette même API — la vérification post-apply (`az containerapp ingress show`) reste
  donc requise après le premier vrai apply de cette ressource, documentée en commentaire dans
  `frontend.tf` plutôt que dans ce journal seul.
- **Drift `azurerm` 4.72.0 → 4.80.0 découvert, non corrigé, laissé hors scope** : le même
  `terraform plan` réel exécuté pour valider cette PR a révélé qu'un `terraform init -upgrade`
  (qui aurait fait passer azurerm de 4.72.0 à 4.80.0) déclencherait un remplacement complet de la
  VM jumpbox (`module.jumpbox`) — confirmé même sur un checkout `origin/dev` propre et non modifié,
  via un worktree Git jetable dédié à ce test. Ce drift est totalement indépendant du sujet de
  cette PR (certificat/domaine du frontend) ; le lock file a été délibérément laissé inchangé pour
  azurerm (pincé à 4.72.0), seule l'entrée `azapi` ajoutée. Voir `docs/BACKLOG.md`.

---

## PR #199 — feat: relever le nombre d'analyses gratuites auto-lancées + retour visuel du bouton d'analyse

**Date :** 2026-07-12
**Branche :** `feature/offer-analysis-ux-improvements` → `dev`

### Contexte

Deux sujets combinés sur cette branche : un ajustement produit délibéré du palier gratuit
d'analyses de correspondance (confirmé avec l'utilisateur, cf. ADR-018), et une amélioration du
retour visuel du bouton d'analyse IA sur la page de correspondances — le bouton restait
insuffisamment clair pendant l'attente et en cas d'échec de la requête (ex. crédits épuisés).

### Ce qui a été fait

- **`JobFinder/python/shared/config.py`** : `MATCH_ANALYSIS_AUTO_TOP_N` passe de `"1"` à `"20"` —
  ce nombre correspond aux N meilleurs matchs par CV analysés automatiquement à chaque run de
  matching, sans consommer de crédit payant (cf. ADR-018). Commentaire au-dessus de la constante
  mis à jour en conséquence.
- **`JobFinder/Terraform/envs/dev/container_apps.tf`** : la variable d'environnement
  `MATCH_ANALYSIS_AUTO_TOP_N` du Container App Job de matching était codée en dur à `"1"` —
  repéré par `reviewer-backend` en revue, qui a signalé que le commit précédent aurait été un
  no-op une fois déployé en dev tant que cette valeur restait désynchronisée du nouveau défaut
  Python. Alignée à `"20"`.
- **Frontend — `MatchAnalysisPanel.tsx`, `MatchItem.tsx`, `CorrespondancesPanel.tsx`,
  `AnalyzingDots.tsx` (nouveau), `globals.css`** :
  - Le bouton « Analyser cette offre avec l'IA » et le texte qui l'entoure sont désormais centrés
    (au lieu d'alignés à gauche).
  - Pendant qu'une analyse est en cours, le bouton est entièrement remplacé par un spinner SVG
    centré (même motif inline que celui déjà utilisé dans `CVCard.tsx`) surmontant le libellé
    « Analyse en cours » — auparavant un simple bouton désactivé portant ce même texte.
  - Sur la carte repliée, la ligne teaser affiche désormais « Analyse IA en cours » avec un
    nouvel indicateur 3 points animé (`AnalyzingDots.tsx`, `@keyframes dotPulse` ajouté dans
    `globals.css`) tant qu'une analyse est en attente, à la place de l'indication générique
    « dépliez l'offre ».
  - Les échecs d'analyse au niveau de la requête (ex. HTTP 402 crédits épuisés) s'affichent
    désormais en texte rouge directement sous le bouton, scoping à la seule offre actuellement
    dépliée (`analysisError` réinitialisé dans `toggleExpand` au changement d'offre) — remplace
    l'ancien bandeau d'erreur générique qui se trouvait au-dessus de toute la liste de matchs dans
    `CorrespondancesPanel.tsx`.
  - Tests (`MatchItem.test.tsx`, `MatchList.test.tsx`) mis à jour pour couvrir le nouveau
    comportement (36 tests).

**Vérification :** `tsc --noEmit` propre, ESLint propre sur les fichiers touchés, suite Jest verte
(36 tests dans `MatchItem`/`MatchList`, mis à jour pour le nouveau comportement), serveur de dev
démarré et page d'accueil non authentifiée servie sans erreur console. `reviewer-frontend`,
`reviewer-backend` et `reviewer-infra` ont tous retourné APPROUVÉ (`reviewer-backend` a signalé le
no-op Terraform à son premier passage, corrigé puis re-approuvé). Vérification visuelle
interactive complète (centrage du bouton, animation des points, spinner) **non effectuée** — le
panneau des correspondances est derrière une authentification MSAL avec des données backend
réelles non disponibles dans cet environnement ; seule la logique (tests, typage, lint) a pu être
vérifiée, pas le rendu visuel final.

### Décisions techniques

- **Texte d'erreur crédits épuisés réactif plutôt que proactif** : l'utilisateur a été consulté sur
  le choix entre vérifier le solde de crédits avant tout clic (en connectant le composant
  `CreditsBadge` existant, aujourd'hui non branché sur cette logique) et se contenter d'afficher
  l'erreur seulement après un échec de requête HTTP 402. Réactif confirmé comme suffisant — c'est
  l'implémentation retenue, un choix assumé et non un oubli du branchement proactif.

### Complément — réservation optimiste des crédits sur le clic d'analyse (commit `7339409`)

Le retour visuel livré ci-dessus attendait toujours la réponse serveur avant de réagir, et le
solde affiché par `CreditsBadge` restait figé pendant toute la durée de l'analyse — angle mort du
choix « réactif plutôt que proactif » ci-dessus : rien n'empêchait un double-clic pendant le
round-trip, et le badge ne se mettait à jour qu'au prochain montage ou événement
`credits-consumed`. Ce commit connecte finalement `CreditsBadge` à cette logique, sans revenir sur
la décision « pas de vérification proactive avant clic » : le badge réagit au clic lui-même, pas
avant.

- **`lib/creditsBus.ts`** : deux nouveaux événements pub-sub, `credits-reserved` et
  `credits-released`, aux côtés de `credits-consumed` existant.
- **`CorrespondancesPanel.tsx` — `requestAnalysis()`** : marque désormais l'offre `pending` et
  appelle `notifyCreditsReserved()` de façon synchrone, dans le même tick que le clic et avant
  toute réponse serveur — le bouton (qui ne se rend que si `!inProgress`) disparaît et le badge de
  crédits se décrémente instantanément, sans attendre le round-trip. En cas d'échec, rollback :
  l'offre redevient non-pending, et soit `notifyCreditsReleased()` (échec générique — le crédit
  optimiste est rendu), soit `notifyCreditsConsumed()` pour une 402 (déjà à 0 crédits côté
  serveur — resynchronise avec le vrai solde plutôt que de créditer +1 sur une réservation qui
  n'avait en réalité jamais rien pris côté serveur, ce qui ferait apparaître un crédit fantôme).
- **`CreditsBadge.tsx`** : s'abonne aux deux nouveaux événements pour appliquer le -1/+1 optimiste
  sur le solde affiché.
- **`MatchAnalysisPanel.tsx`** : réordonnancement mineur — le message d'erreur s'affiche désormais
  avant le bouton plutôt qu'après.
- Tests mis à jour dans `__tests__/CorrespondancesPanel.test.tsx` et `__tests__/CreditsBadge.test.tsx`.

**Vérification :** `reviewer-frontend` a retourné APPROUVÉ. Remarque non-bloquante signalée (déjà
préexistante, non introduite par ce commit) : `CorrespondancesPanel.tsx` (~357 lignes) mélange
plusieurs responsabilités — bon candidat à l'extraction de `requestAnalysis`/du polling dans un
hook dédié dans un futur refactor, non actionnable maintenant.

## PR #200 — fix: fetch d'offres à l'heure française (DST-safe) + copy bibliothèque

**Date :** 2026-07-16
**Branche :** `feature/library-refresh-schedule-copy` → `dev`

### Contexte

Deux sujets indépendants, demandés directement par l'utilisateur, atterris sur cette branche.

Le premier : s'assurer que le Container App Job de fetch d'offres tourne bien à 12h et 20h heure
française (Europe/Paris), pas UTC. Le `cron_expression` Terraform existant (`"0 12,20 * * *"`)
déclenchait en réalité à 12h/20h UTC — confirmé qu'Azure Container Apps ne supporte aucun
paramètre timezone/DST sur son trigger planifié (ni sur `azurerm_container_app_job`, ni sur l'API
ARM sous-jacente).

Le second, sans lien avec le premier : changement de texte sur la vue bibliothèque, pour informer
les utilisateurs de la cadence de rafraîchissement fixée par le premier sujet.

### Ce qui a été fait

- **`JobFinder/Terraform/envs/dev/container_apps.tf`** : `cron_expression` de
  `job_offer_fetching` passe à `"0 10,11,18,19 * * *"` — couvre toutes les heures UTC pouvant
  correspondre à 12h/20h heure de Paris, sous CET (UTC+1 : 11h, 19h) comme sous CEST (UTC+2 :
  10h, 18h). Commentaires mis à jour (résumé « Agent 3 » en tête de fichier et bloc au-dessus du
  module) pour expliquer la contrainte UTC-only et le couplage avec le garde-fou côté Python
  ci-dessous.
- **`JobFinder/python/agents/offer_fetching/main.py`** : nouvelles constantes `PARIS_TZ`
  (`zoneinfo.ZoneInfo("Europe/Paris")`) et `SCHEDULED_LOCAL_HOURS = (12, 20)`, nouvelle fonction
  `_is_scheduled_local_hour(now_utc: datetime) -> bool` qui convertit `now_utc` en heure locale
  parisienne et vérifie l'heure. `main()` calcule désormais `now_utc` en tout début d'exécution et
  retourne sans exécuter `run_migrations()` (après un `logger.info("offer_fetch_skipped_outside_local_window", ...)`)
  si le garde-fou renvoie `False`. Docstring de module mise à jour en conséquence.
- **`JobFinder/python/agents/cleanup/main.py`** : une ligne de docstring corrigée (« 12:00 and
  20:00 UTC » → « 12:00 and 20:00 Europe/Paris local time »), pur wording — ce fichier référence la
  cadence de fetch pour justifier sa propre logique de période de grâce, aucun changement de
  logique.
- **`JobFinder/python/requirements.txt`** : ajout de `tzdata`, avec un commentaire expliquant que
  `zoneinfo` (stdlib) a besoin de la base IANA pour résoudre `"Europe/Paris"`, absente de l'image
  `python:3.12-slim` utilisée par ces agents — confirmée absente en local et sur l'image de
  déploiement, ce qui aurait levé `ZoneInfoNotFoundError` à l'import en production sans ce paquet.
- **`JobFinder/python/tests/test_offer_fetching.py`** : nouvelles `TestIsScheduledLocalHour`
  (paramétrée sur une date en juillet/CEST et une date en janvier/CET, couvrant les 4 heures UTC
  déclenchées côté Terraform) et `TestMainSchedulingGuard` (vérifie que `main()` s'arrête avant
  `run_migrations()`/`_get_active_rome_codes()` quand le garde-fou renvoie `False`, et poursuit
  quand il renvoie `True`).
- **`JobFinder/frontend/app/_components/LibrarySection.tsx`** : le sous-titre sous le titre
  « Bibliothèque » passe de « Sélectionnez un CV pour visualiser ses correspondances. » à
  « De nouvelles offres sont recherchées chaque jour à 12h et 20h pour chacun de vos CVs. » —
  informe les utilisateurs de la cadence de rafraîchissement fixée ci-dessus, remplace une ligne
  purement instructionnelle.

### Décisions techniques

- **Déclenchement Terraform 4×/jour, exécution effective 2×/jour** : en l'absence de support
  timezone/DST côté Azure Container Apps, le seul moyen d'obtenir un comportement correct toute
  l'année sans intervention manuelle à chaque changement d'heure est de déclencher le job à toutes
  les heures UTC candidates et de laisser le code Python trancher dynamiquement laquelle
  correspond réellement à l'heure française courante. Alternative rejetée : ajuster
  `cron_expression` deux fois par an au changement d'heure — écartée pour ne pas dépendre d'une
  intervention manuelle récurrente.

**Vérification :** Les trois reviewers sont passés : `reviewer-infra` sur `container_apps.tf`
(APPROUVÉ, une remarque non-bloquante : le passage de 2×/jour à 4×/jour de déclenchement
augmente marginalement le coût de cold-start, à surveiller, non corrigé), `reviewer-backend` sur
les 4 fichiers Python (APPROUVÉ, une remarque non-bloquante : les nouvelles méthodes de test
n'ont pas d'annotation de retour `-> None`, mais c'est un motif préexistant sur la majorité de la
suite de tests, pas une régression), `reviewer-frontend` sur `LibrarySection.tsx` (APPROUVÉ, une
remarque cosmétique non-bloquante sur « 12h »/« 20h » vs espace insécable selon la typographie
française formelle — non traitée, aucune convention établie dans le code sur ce point). Suite
Python complète verte (248/248, `python -m pytest`), `terraform fmt -check`/`terraform validate`
propres sur `envs/dev`. Côté frontend : `tsc --noEmit` propre, ESLint propre, suite Jest complète
verte (124 tests).

---

## PR #201 — refactor: remplacer les badges de compétences France Travail par une extraction IA cachée

**Date :** 2026-07-12
**Branche :** `feature/badges-competences-ia` → `dev`

### Contexte

Les badges de compétences affichés sur chaque offre venaient de `Offer.skills`, le champ brut
`libelle` de l'API France Travail — le plus souvent vide ou hors-sujet par rapport au poste réel.
Spec détaillée dans `docs/prompts/prompt-badges-competences-ia.md` : remplacer cet affichage par
une extraction IA des compétences techniques essentielles, mise en cache une fois par offre plutôt
que recalculée à chaque analyse, puis comparée au CV de chaque candidat par l'agent `match_analysis`
existant (pas de nouvel agent).

### Ce qui a été fait

**Migration 029 + `shared/models.py` :** nouvelle colonne `Offer.key_skills` (`ARRAY(String)`,
nullable). `NULL` = pas encore extrait, `[]` = extrait sans compétence essentielle identifiée —
distinction volontaire pour ne jamais confondre « en attente » et « rien à afficher ».

**`agents/offer_fetching/main.py` :** `_upsert_offers` étend l'invalidation existante basée sur
`ft_updated_at` — la condition `offer_changed` (déjà utilisée pour remettre `embedding` à `NULL`
quand France Travail modifie une offre déjà stockée) est désormais partagée par `key_skills`, via
un second `case()` sur la même condition plutôt qu'un mécanisme parallèle.

**`agents/match_analysis/main.py` (rework significatif) :** deux variantes du bloc « compétences
clés » du prompt système, sélectionnées par `_build_system_prompt` selon que `Offer.key_skills` est
déjà en cache ou non — `KEY_SKILLS_INSTRUCTIONS_EXTRACT` (le modèle invente jusqu'à
`MAX_KEY_SKILLS = 10` noms à partir du titre/de la description) ou
`KEY_SKILLS_INSTRUCTIONS_MATCH_ONLY` (le modèle réutilise une liste déjà figée, fournie dans le
message utilisateur, sans la modifier). Le champ `matched_skills` a disparu du schéma JSON attendu
du modèle — il est désormais dérivé en code par `_parse_key_skills` à partir des entrées
`key_skills` marquées `matched: true`, avec rejet défensif des noms hors liste sur la branche
« match-only » (traité comme une hallucination, loggé, jamais persisté). `_analyze_match` et
`_parse_analysis_payload` retournent maintenant un tuple `(analysis_fields, new_offer_key_skills)` ;
`new_offer_key_skills` n'est non-`None` que sur la branche extraction, et
`_persist_offer_key_skills` l'écrit une seule fois sur l'offre, gardé par `Offer.key_skills.is_(None)`
pour rester sûr même si deux analyses de la même offre partent en parallèle (répliques concurrentes
du Container App Job). `_get_match_context` remonte désormais `offer_id` et `offer_key_skills` (au
lieu de `offer_skills`, qui n'est plus lu par cet agent).

**Backend — API webapp :** `OfferOut.key_skills: list[str] | None = None` (`agents/webapp/schemas.py`).

**Frontend :** `types.ts` reflète `key_skills: string[] | null`. `MatchItem.tsx` : le bloc de badges
bruts France Travail et la ligne de prose « Compétences requises » sont retirés ; le bloc de badges
IA itère désormais `offer.key_skills` (aucun plafond côté frontend — déjà borné à 10 côté serveur),
vert si le nom figure dans `match.analysis.matched_skills`, gris sinon. `MatchAnalysisPanel.tsx` :
bloc de badges dupliqué (`offerSkills`) et prop associée retirés entièrement.

**Tests :** `test_match_analysis.py` largement réécrit (les deux branches de `_parse_key_skills`,
clamp à `MAX_KEY_SKILLS`, rejet des noms hors liste cachée, items malformés ignorés,
`_persist_offer_key_skills` gardé par `is_(None)`, choix du prompt selon `offer_key_skills`).
`test_offer_fetching.py` : nouveau test vérifiant que `embedding` et `key_skills` partagent la même
condition SQL `ft_updated_at` plutôt qu'un mécanisme dupliqué. Côté frontend, `MatchItem.test.tsx`
couvre l'absence de plafond sur `offer.key_skills`, l'absence de badge quand `key_skills` est `null`
(offre jamais analysée) et quand aucune analyse n'existe encore malgré un cache déjà rempli ;
`CVDetailSection.test.tsx`, `CorrespondancesPanel.test.tsx` et `MatchList.test.tsx` ont chacun reçu
le champ `key_skills: null` dans leurs fixtures d'offre.

### Décisions techniques

- **`Offer.skills` (champ brut France Travail) et sa colonne DB conservés tels quels** : seuls son
  affichage et son usage dans le prompt de `match_analysis` sont retirés, conformément à la spec —
  pas de suppression de colonne, pas de migration de nettoyage.
- **Extraction bornée aux 4000 premiers caractères de la description** (`OFFER_TEXT_MAX_CHARS`,
  plafond préexistant, inchangé) : une compétence mentionnée seulement au-delà de cette limite est
  invisible pour le modèle et ne peut jamais être extraite — ce n'était qu'un compromis de qualité
  de synthèse avant l'existence de `key_skills`, c'est désormais une contrainte dure sur ce que
  l'extraction peut voir. Un commentaire a été ajouté sur la constante dans `main.py` pour rendre ce
  risque explicite plutôt que de le laisser implicite dans le code.
- **Pas de recalcul rétroactif des analyses existantes** : `MatchAnalysis` n'est jamais recalculée
  pour une paire CV↔offre déjà analysée (règle métier préexistante, inchangée). Conséquence pour
  cette PR : une offre dont `key_skills` se peuple via l'analyse d'un premier CV garde, pour les
  analyses plus anciennes de cette même offre, un `matched_skills` calculé sous l'ancien schéma
  libre — ces analyses peuvent afficher moins de badges verts qu'une analyse fraîche, jusqu'à ce que
  l'utilisateur en redéclenche une. Ce n'est pas un bug, c'est la conséquence assumée de la règle
  « jamais de recalcul automatique » déjà en place.

**Vérification :** suite Python complète verte (260/260, `pytest` sur l'ensemble de
`JobFinder/python/tests/`, pas seulement les fichiers touchés par cette PR), suite Jest complète
verte (127/127, l'ensemble de `JobFinder/frontend/__tests__/`), `tsc --noEmit` propre côté
frontend. `reviewer-infra` sur la migration 029 (APPROUVÉ, aucune
remarque), `reviewer-frontend` sur `MatchItem.tsx`/`MatchAnalysisPanel.tsx`/`types.ts` (APPROUVÉ,
une remarque non-bloquante sur la comparaison par égalité de chaîne entre `offer.key_skills` et
`match.analysis.matched_skills` — déjà couverte défensivement par le rejet des noms hors liste dans
`_parse_key_skills`, aucune action requise), `reviewer-backend` sur les 4 fichiers Python — un
premier passage a retourné CHANGEMENTS REQUIS (`_build_upsert_statement` sans annotation de type de
retour, seule fonction introduite par cette PR à en manquer), corrigé et re-vérifié APPROUVÉ. Le
numéro de PR de cette entrée a également été corrigé de #200 à #201 après vérification via
`gh pr list` — #200 était déjà pris par une autre branche mergée entretemps.

---

## PR #202 — fix(frontend): traiter le statut "pending" d'une analyse comme en cours

**Date :** 2026-07-17
**Branche :** `fix/analysis-pending-status-indicator` → `dev`

### Contexte

Bug remonté après le merge du PR #201. Une offre auto-enfilée pour analyse côté serveur
(auto top-N à la création des matchs) reçoit une ligne `match_analyses` au statut `pending`
avant qu'un worker ne la prenne en charge et bascule son statut à `processing`. Le frontend
ne traitait que `processing` comme « en cours » : ces lignes `pending` n'affichaient donc
aucun spinner et le bouton « Analyser » restait cliquable, ce qui permettait à l'utilisateur
de relancer une analyse déjà en file et de brûler un second crédit pour rien.

### Ce qui a été fait

**`MatchItem.tsx` et `MatchAnalysisPanel.tsx` :** le calcul local `inProgress` de chacun des
deux composants inclut désormais `match.analysis?.status === "pending"` en plus de
`"processing"` (et de `analysisPending`, l'état optimiste côté client). Un commentaire WHY a
été ajouté à chaque site pour que le contrat reste explicite si quelqu'un retouche cette
condition plus tard — le bug initial venait précisément de l'hypothèse implicite que
`processing` seul suffisait.

**`CorrespondancesPanel.tsx` :** nouvel effet qui amorce `analysisPending` (le Set client
d'offres suivies par le polling de résultat) avec toute offre déjà `pending` ou `processing`
dès le chargement de `matches`. Avant ce fix, `analysisPending` n'était alimenté que par un
clic utilisateur sur « Analyser » (`requestAnalysis`) — corriger uniquement l'affichage
`inProgress` dans `MatchItem`/`MatchAnalysisPanel` n'aurait donc pas suffi : une offre
auto-enfilée aurait bien montré le spinner au premier rendu (déduit directement de
`match.analysis.status`), mais rien n'aurait jamais interrogé le serveur pour la faire
basculer à `done` — elle serait restée bloquée « en cours » jusqu'à ce que le parent
refetch `matches` pour une autre raison. C'est ce nouvel effet qui referme la boucle.

**Tests :** `MatchItem.test.tsx` — nouveau cas couvrant le statut `pending` (spinner affiché,
bouton « Analyser » absent), avec le contrat métier explicité en commentaire dans le test
lui-même. `CorrespondancesPanel.test.tsx` — nouvelle section dédiée couvrant une offre dont
l'analyse est déjà `pending` au premier chargement de `matches` sans aucun clic utilisateur :
affichage immédiat de l'état « en cours », et complétion correcte via le polling existant une
fois l'analyse passée à `done`.

### Décisions techniques

- **Pas de changement de type ni de schéma** : `MatchAnalysisOut.status` incluait déjà
  `"pending"` dans `lib/api/types.ts` avant cette PR — seule la logique de dérivation
  `inProgress` dans les deux composants d'affichage était incomplète.

**Vérification :** suite Jest complète verte (130/130, l'ensemble de
`JobFinder/frontend/__tests__/`, y compris les deux nouveaux cas de régression sur le statut
`pending`), `tsc --noEmit` propre. `reviewer-frontend` sur les trois fichiers modifiés —
APPROUVÉ, aucune remarque. Numéro de PR `#202` confirmé via `gh pr list` avant l'ouverture de
la PR (prochain numéro disponible après #201).

---

## PR #203 — feat(frontend): responsive mobile/tablette + picker communes tactile

**Date :** 2026-07-17
**Branche :** `feature/responsive-mobile` → `dev`

### Contexte

Le frontend était pensé desktop-only : aucune classe responsive (`sm:`/`md:`/`lg:`) dans tout
le code, plusieurs largeurs fixes en pixels (`w-[38%]` du détail CV, colonnes de 180px de la
bibliothèque, colonne score 70px des matchs), et des interactions dépendantes de la souris —
survol pour révéler la corbeille d'un CV, molette pour basculer CV ↔ carte sur le hero, et
surtout le dessin de la zone de recherche 100 % MouseEvent (clic gauche = peindre, clic
droit = gommer, clic milieu = déplacer). Objectif : rendre le site utilisable sur mobile et
tablette (375px / 768px / 1280px) sans aucune régression visuelle desktop.

### Ce qui a été fait

**Commit 1 — page d'accueil.** Approche mobile-first inversée : les valeurs mobiles sont la
base et les valeurs desktop d'origine sont restaurées à l'identique derrière `md:`/`lg:`,
ce qui garantit mécaniquement le non-changement du rendu ≥ 1024px. `CVDetailSection` passe
en colonne sous `lg` (vignette PDF masquée, zone d'analyse plafonnée à `38dvh` avec scroll
interne, boutons de navigation CV à 44px) ; `LibrarySection` resserre la grille sous `md`
(minimum 130px par colonne — calculé pour que 375px de viewport moins `px-4` et les deux
gouttières de scrollbar donnent deux colonnes — lignes de 300px) ; `MatchItem` compacte la
colonne score (56px), agrandit le bookmark en cible 44px et dégage le titre du bouton
flottant (`pr-10`) ; `CorrespondancesPanel` et les panneaux d'analyse réduisent leurs
paddings. Deux affordances tactiles : le switch CV ↔ carte, uniquement pilotable à la
molette, gagne des pilules « Carte » / « Terminé » visibles sur pointeurs grossiers
(`@media (any-pointer: coarse)`) — le hint décoratif « CARTE » d'`UploadSection` est masqué
sur ces mêmes écrans pour ne pas doubler ; et la corbeille de `CVCard`, révélée au survol,
devient visible en permanence via le nouveau hook `lib/useCoarsePointer.ts` (matchMedia,
inerte sous jsdom donc sans effet sur les tests hover existants).

**Commit 2 — page profil.** Paddings mobiles (`px-4`/`p-4` sous `sm`), `ExperienceToggle`
empilé verticalement sous `sm` (trois colonnes trop étroites à 375px), et `InfoTooltip`
recentré sur l'icône et réduit à `w-48` sous `md` — le placement desktop `left-full` de la
bulle de 224px débordait du viewport téléphone et créait un scroll horizontal.

**Commit 3 — picker communes tactile.** `CommunePaintLayer` : les helpers `stamp` et
`positionBrush` sont refactorés pour travailler en coordonnées client (partagées entre
MouseEvent et Touch), et des listeners `touchstart/touchmove/touchend/touchcancel` non
passifs gèrent le geste à un doigt selon un nouveau type `TouchTool` (`paint` / `erase` /
`pan`) exposé en prop. Un second doigt interrompt le geste en cours et laisse la main au
pinch-zoom natif de Leaflet (`touchZoom`, qui déplace aussi la carte avec le point médian) :
la navigation à deux doigts reste donc disponible quel que soit le mode actif.
`preventDefault()` sur le chemin un doigt supprime les événements souris simulés du
navigateur (sans quoi un tap repeindrait via `onMouseDown` quel que soit le mode) et
`touch-action: none` empêche le navigateur de scroller la page. `CommuneZonePicker` porte
l'état du mode et une barre d'outils flottante en bas de carte (pointeurs grossiers
uniquement, cibles 44px, mode actif marqué par `aria-pressed` + fond accent) dans l'ordre
Peinture → Gomme → Déplacement, mode Peinture par défaut sur la vue France entière.

### Décisions techniques

- **`any-pointer: coarse` plutôt que `pointer: coarse`** pour toutes les affordances
  tactiles : un portable à écran tactile dont le pointeur principal est le trackpad doit
  quand même exposer la toolbar et les pilules ; un desktop souris-seul ne les voit jamais.
- **Trois boutons visibles plutôt qu'un bouton unique qui cycle** pour le toggle du picker :
  un mode est atteignable en un tap au lieu de deux, et l'état actif est non ambigu
  (`aria-pressed` + fond accent), ce qui reste dans l'esprit « cycler Peinture → Gomme →
  Déplacement » du besoin exprimé.
- **Fin de trait sur le second doigt plutôt qu'annulation** : les communes déjà peintes par
  le premier doigt restent (annulables via Annuler) — distinguer un « vrai » début de trait
  d'un début de pinch demanderait un délai artificiel sur le premier stamp, au prix d'un
  tap-pour-peindre moins réactif.
- **Interactions souris strictement inchangées** : les handlers mouse existants ne lisent
  jamais `TouchTool` ; la répartition gauche/droit/milieu/molette du desktop est intacte.

**Vérification :** suite Jest complète verte (131/131, dont un nouveau cas `CVCard` simulant
un pointeur grossier via mock de `matchMedia`), `tsc --noEmit` et `next lint` propres.
Vérification visuelle en dev server via Chrome : 1280px (hero, bibliothèque 5 colonnes,
détail côte à côte, peinture/annulation/sortie molette de la carte — inchangés), ~768px
(layout empilé, paddings `md:`), et 375px exactement via une iframe à largeur contrôlée
(Chrome ne descend pas sous ~657px de fenêtre) : bibliothèque 2 colonnes, détail empilé,
profil empilé avec tooltip contenu dans le viewport, `scrollWidth === clientWidth` (aucun
scroll horizontal) mesuré sur les trois pages. Limite : le comportement tactile réel
(toolbar visible, gestes un/deux doigts) n'est pas émulable dans une session Chrome
desktop — validé par revue de code et test unitaire du hook, à confirmer sur appareil réel.

---

## PR #204 — refactor picker, fix pinch tactile, navigation mobile par menu épinglé

**Date :** 2026-07-17
**Branche :** `feature/mobile-nav-picker-refactor` → `dev`

### Contexte

Retours d'usage mobile après le merge du PR #203 : (1) `CommunePaintLayer.tsx` avait
atteint ~800 lignes (dette signalée en review du #203), (2) un geste à deux doigts sur la
carte (pincer pour zoomer) laissait un coup de pinceau parasite sous le premier doigt posé,
et (3) la navigation entre les sections plein écran de l'accueil restait au swipe, peu
adaptée au mobile — remplacée par un menu de navigation épinglé.

### Ce qui a été fait

**Commit 1 — refactor.** `CommunePaintLayer.tsx` découpé par responsabilité, sans
changement de comportement : `communeMapStyles.ts` (lecture des tokens de thème → styles
Leaflet), `communeMapDetail.ts` (contours haute-zoom et labels de villes/communes avec
placement anti-collision, derrière une factory `createDetailLayers()`), `communeBrush.ts`
(toutes les interactions pointeur — souris et tactile — derrière
`attachBrushInteractions(map, opts)` qui retourne son cleanup, et propriétaire du type
`TouchTool`), le composant conservant fond de carte, chargement des données et synchro de
la sélection contrôlée (~360 lignes).

**Commit 2 — fix pinch.** Le trait tactile démarrait au `touchstart` : le premier doigt
d'un pincement peignait donc toujours avant que Leaflet ne prenne le geste. Les traits
peinture/gomme passent par une fenêtre de grâce de 120 ms : le chemin est accumulé et le
curseur pinceau affiché, mais rien n'est peint ; un second doigt qui arrive pendant la
grâce annule le trait en attente (pincement pur, zéro peinture) ; l'expiration de la grâce
committe le trait en rejouant le chemin accumulé (pas de trou au départ) ; un tap relâché
avant la grâce committe au `touchend` (le tap-pour-peindre reste immédiat). Couvert par
`communeBrush.test.ts` (pinch sans peinture, commit à l'expiration, commit du tap, outil
déplacement).

**Commit 3 — navigation mobile.** Sous `md` : le conteneur scroll-snap passe en
`overflow-hidden` (plus de swipe entre sections — le scroll programmatique fonctionne
toujours), et les pills flottants Crédits/Compte du layout deviennent le côté droit d'une
barre épinglée pleine largeur, opaque (`bg-surface`, `z-50`, `border-b`) — le contenu passe
derrière elle, jamais dessus. Nouveau `MobileNavMenu` (burger en haut à gauche, cible
44px) : panneau opaque listant Accueil / Bibliothèque / Correspondances / Mon profil,
entrées de section désactivées quand la section n'existe pas (bibliothèque vide, aucun CV
sélectionné — disponibilité échantillonnée à l'ouverture via `checkVisibility`), et depuis
une autre route elles ramènent d'abord sur l'accueil. Les hints de scroll ⌃/⌄ sont masqués
sous `md`, `CVDetailSection` prend `pt-14` sous la barre, les pilules Carte/Terminé passent
sous la barre (Terminé en bas à droite), et /profile masque sa propre barre « ← Accueil »
sous `md` (une seule barre fixe à la fois). Au-dessus de `md`, rien ne change : mêmes
éléments repositionnés en CSS pur (un seul montage de CreditsBadge/AuthButton — une seconde
instance dupliquerait le GET /profile).

### Décisions techniques

- **Saut instantané pour la navigation par menu** : `scrollIntoView({behavior:"smooth"})`
  cale à mi-course sur un conteneur `overflow-hidden` quand des scrollers imbriqués sont en
  jeu (constaté dans Chrome, reproductible hors interaction) — et une navigation « de page
  en page » se prête de toute façon mieux à un saut. Les flux de scroll internes de
  `HomeClient` choisissent smooth/instantané par breakpoint (`sectionScrollBehavior()`,
  gardé contre l'absence de `matchMedia` sous jsdom).
- **Grâce temporelle plutôt que rollback** pour le fix pinch : annuler un trait déjà commité
  aurait pollué la pile d'annulation (le snapshot part au premier stamp effectif) ; 120 ms
  couvrent largement le délai entre les deux doigts d'un pincement réel tout en restant
  imperceptibles au dessin.
- **Barre mobile sous `md`** (largeur) et non `any-pointer: coarse` : c'est un changement de
  layout, pas d'input — une tablette ≥ 768px garde le comportement actuel, les affordances
  purement tactiles (toolbar du picker, pilules Carte/Terminé) restent quant à elles pilotées
  par `any-pointer: coarse`.

**Vérification :** suite Jest complète verte (139/139 dont 4 nouveaux cas `communeBrush` et
4 `MobileNavMenu`), `tsc --noEmit` et `next lint` propres. Vérification visuelle en dev
server (iframe 390px, la fenêtre Chrome ne descendant pas sous ~660px) : barre épinglée
opaque avec burger + Crédits + Compte, menu ouvert/fermé, navigation vers Bibliothèque /
Correspondances / Mon profil (une seule barre sur /profile), contenu passant derrière la
barre sans jamais la recouvrir ; desktop ≥ md inchangé (pills flottants, snap-scroll,
souris sur la carte). Limite : gestes tactiles réels (pinch) non émulables en session
Chrome desktop — le fix pinch est couvert par les tests unitaires de `communeBrush`, à
confirmer sur appareil réel.

---

## PR #205 — brancher structlog sur `logging` standard pour peupler AppTraces

**Date :** 2026-07-18
**Branche :** `feature/structlog-stdlib-logging-bridge` → `dev`

### Contexte

Diagnostic établi avec Vincent (Claude Cowork) : la table `AppTraces` du workspace
`log-jf-dev-frc` restait vide malgré des exécutions récentes des Container App Jobs, alors
que `ContainerAppConsoleLogs_CL` se remplissait normalement (pipeline infra indépendant,
`envs/dev/monitoring.tf:146-158`). Cause : `shared/telemetry.py::configure_telemetry()`
appelle bien `configure_azure_monitor(...)`, mais `structlog.configure(...)` n'était jamais
appelé nulle part dans le repo — par défaut, `structlog.get_logger()` écrit sur stdout sans
jamais passer par le module `logging` standard, seul module instrumenté par le SDK Azure
Monitor. Aucun `logger.info(...)` structlog n'atteignait donc jamais Application Insights.

### Ce qui a été fait

**Commit 1 — implémentation.** `_configure_structlog()` (appelée en tête de
`configure_telemetry()`, inconditionnellement — présence ou non de
`APPLICATIONINSIGHTS_CONNECTION_STRING`) bascule structlog sur le backend stdlib
(`logger_factory=structlog.stdlib.LoggerFactory()`, `wrapper_class=structlog.stdlib.BoundLogger`),
ajoute un `logging.StreamHandler` avec un formatter dédié (`_ConsoleFormatter`) pour garder
une sortie console lisible en dev, et force le root logger à `INFO` (WARNING par défaut,
ce qui aurait fait disparaître la majorité des logs métier même après le branchement) tout
en repinnant les loggers tiers bruyants (`azure`, `urllib3`) à `WARNING`.

**Commit 2 — test.** Nouveau `tests/test_telemetry.py` : vérifie que les champs custom d'un
événement structlog (`total`, `rome_code`) atterrissent comme attributs individuels du
`LogRecord` stdlib — pas seulement qu'un record est émis — puisque c'est exactement ce que
lit Application Insights pour peupler `customDimensions`.

**Commit 3 — fix collision de nom réservé.** `render_to_log_kwargs` pousse tout champ
custom via `extra=`, et `logging.Logger.makeRecord` lève un `KeyError` si une clé de
`extra` existe déjà sur `LogRecord` (`filename`, `name`, `module`, ...) — un crash à
l'appel du log, avant même qu'un handler ne s'exécute. Un grep de tous les appels
`logger.info/warning/error(...)` sous `JobFinder/python/` a trouvé une collision réelle :
`agents/webapp/routers/cv.py:222` loguait `filename=file.filename` sur le flux d'upload de
CV — un crash en production dès la mise en ligne de ce bridge. Renommé en `cv_filename=`
sur ce site d'appel, et ajouté `_rename_reserved_keys()` comme processor juste avant
`render_to_log_kwargs` dans `_configure_structlog()` : préfixe toute clé collisionnante en
`event_<clé>` plutôt que de laisser planter l'appel, pour qu'un futur site d'appel ne
puisse pas réintroduire ce crash silencieusement. Nouveau cas de test dédié dans
`test_telemetry.py`.

**Commit 4 — fix régression sur `exc_info`.** `exc_info` et `stack_info` sont deux vrais
attributs de `LogRecord` : le premier jet de `_rename_reserved_keys()` (commit 3) les
incluait donc dans l'ensemble des clés réservées à préfixer, alors que
`render_to_log_kwargs` les extrait lui-même de l'event dict pour les repasser en vrais
kwargs stdlib — c'est ce mécanisme qui fait fonctionner `logger.error(..., exc_info=True)`,
obligatoire sur tout log d'erreur selon `conventions-python` et utilisé dans tout le repo
(cleanup, auth, bus). Résultat non détecté par les tests existants (aucun n'exerçait
`exc_info` à travers le bridge) : la clé `exc_info` se retrouvait renommée en
`event_exc_info` avant d'atteindre `render_to_log_kwargs`, qui ne la trouvait plus — la
traceback ne partait donc plus du tout, silencieusement, ni en console ni vers Application
Insights. Repéré par vérification empirique avant ouverture de la PR, corrigé en excluant
`exc_info` et `stack_info` de l'ensemble réservé — `stacklevel` (consommé par
`render_to_log_kwargs` de la même façon, mais qui n'est pas un attribut de `LogRecord` et
n'a donc jamais fait partie de l'ensemble réservé ni été renommé par le commit 3) exclu par
la même expression, par précaution plutôt que pour corriger une régression réelle sur cette
clé. Nouveau cas de test dédié (`test_exc_info_still_captures_traceback`).

**Commit 5 — retours `reviewer-backend`.** Premier passage : `CHANGEMENTS REQUIS` sur 3
points. (1) `logger = structlog.get_logger()` était déclaré avant les nouvelles constantes
de la branche (`_NOISY_THIRD_PARTY_LOGGERS`, `_RESERVED_LOG_RECORD_KEYS`) — réordonné pour
que toutes les constantes précèdent le logger, comme l'exige `conventions-python`. (2) La
fixture `_reset_logging_state` de `test_telemetry.py` n'avait ni docstring ni annotation de
retour — ajoutées. (3) La sortie console dev n'était pas colorée (règle Logging : "JSON en
prod, coloré en dev") — colorée par niveau via des codes ANSI minimalistes (`_LEVEL_COLORS`),
sans introduire de lecture de `LOG_LEVEL` (absente de tout le reste du repo, hors périmètre
de cette branche). Remarques non-bloquantes également traitées : commentaires ajoutés sur
`_RESERVED_LOG_RECORD_KEYS` et `_ConsoleFormatter._RESERVED` expliquant pourquoi ces deux
ensembles ne doivent pas être fusionnés (`exc_info` doit être exclu du premier, inclus dans
le second), et la docstring de `_configure_structlog` raccourcie — le raisonnement déplacé
dans la docstring du module — pour rester sous la limite de 40 lignes de lecture.

**Commit 6 — fix fuite de couleur en prod + remarques non-bloquantes du 2e passage.**
`reviewer-backend` a approuvé le commit 5, mais une vérification manuelle du chemin
« connection string présente » (donc prod-like) faite juste après a montré que
`_ConsoleFormatter` colorait aussi cette sortie : le `logging.StreamHandler` qu'il porte
tourne sans distinction dev/prod sur le root logger, et `envs/dev/monitoring.tf` capture le
stdout/stderr brut du conteneur dans `ContainerAppConsoleLogs_CL` — des codes ANSI y
seraient apparus comme du texte brut (`\x1b[36m...`) au lieu d'être rendus. Ajouté un
paramètre `use_color` à `_ConsoleFormatter.__init__`, réglé sur
`not APPLICATIONINSIGHTS_CONNECTION_STRING` au point d'appel (même proxy dev/prod que le
reste du fichier) ; vérifié empiriquement dans les deux sens (dev coloré, prod-like sans
codes ANSI). A aussi corrigé deux remarques non-bloquantes du 2e passage de
`reviewer-backend` : annotation de retour de `_reset_logging_state` passée de `-> None` à
`-> Iterator[None]` (fonction génératrice, `None` était syntaxiquement accepté mais
incorrect), et ajout de `TestConsoleFormatterColor` (2 cas) testant directement
`_ConsoleFormatter.format` avec `use_color=True`/`False`.

### Écarts avec la tâche d'origine

Deux points de la tâche écrite par Cowork ne correspondaient pas au comportement réel du
SDK installé (`azure-monitor-opentelemetry==1.8.8`), vérifiés empiriquement avant
d'adapter :

- **`configure_azure_monitor(..., logging_level=logging.INFO)`** n'est pas un paramètre
  reconnu par cette version du SDK (`**kwargs` avale silencieusement toute clé inconnue) —
  aucun effet, ni erreur. Le vrai verrou est le niveau du root logger lui-même (WARNING par
  défaut), fixé directement à `INFO` dans `_configure_structlog()`.
- **`structlog.stdlib.ProcessorFormatter.wrap_for_formatter`** (le pattern documenté par
  défaut pour l'intégration stdlib) regroupe tout l'event dict dans `record.msg` — les
  champs custom n'existent alors jamais comme attributs individuels du `LogRecord`.
  Application Insights construit `customDimensions` à partir de `vars(record)`
  (`LoggingHandler._get_attributes` du package `opentelemetry-instrumentation-logging`) :
  avec `wrap_for_formatter`, `customDimensions` serait resté vide malgré le fix. Utilisé
  `structlog.stdlib.render_to_log_kwargs` à la place, qui pousse les champs custom via
  `extra=` — vérifié par exécution locale avant et après (voir docstring de
  `_configure_structlog`).

**Vérification :** `pytest` complet vert (267/267 sur `JobFinder/python/tests/` + 4/4 sur
`agents/cleanup/tests/`, dont les 7 cas de `tests/test_telemetry.py` — champs custom
présents comme attributs individuels du `LogRecord`, root logger à INFO, loggers tiers
bruyants repinnés à WARNING, collision de nom réservé préfixée sans crash, traceback
toujours capturé via `exc_info`, coloration console gatée sur `use_color` dans les deux
sens). Vérifié manuellement en local : sortie console lisible sans
`APPLICATIONINSIGHTS_CONNECTION_STRING`, et avec une connection string factice,
confirmation que le `LoggingHandler` OpenTelemetry produit bien des `attributes` contenant
`total`/`rome_code` (donc `customDimensions` non vide) avant translation vers l'exporteur
Azure Monitor. Limite : test manuel contre un vrai workspace Application Insights
(`AppTraces | take 50` dans le portail) non exécuté depuis cette session — à confirmer par
Vincent lors d'un run réel d'un agent.

## PR #206 — feat(cleanup): snapshot quotidien exact des totaux offres/CV

**Date :** 2026-07-19
**Branche :** `feature/cleanup-daily-snapshot-log` → `dev`

### Contexte

Le pont structlog→logging du PR #205 fait que `AppTraces` ne contient que des événements
delta (offres/matchs supprimés à chaque purge) — aucun historique n'existe avant ce pont, et
même après, il est impossible de reconstruire un total exact d'offres ou de CV en cours à un
instant donné à partir de ces seuls deltas. Le workbook/KQL de monitoring a besoin d'un total
exact, pas d'une somme de deltas potentiellement incomplète.

### Ce qui a été fait

`agents/cleanup/main.py` gagne une seconde responsabilité, en plus de la purge quotidienne
des offres/matchs obsolètes existante : `_snapshot_totals(session)` exécute un
`SELECT count(*)` sur les tables `Offer` et `CV` et retourne `(total_offers, total_cvs)`.
Câblée dans `main()` juste après le log `cleanup_completed` existant, dans une session DB
distincte de celle utilisée par la purge, avec log `logger.info("daily_snapshot",
total_offers=..., total_cvs=...)`.

Cette étape est best-effort : encadrée par un `try/except SQLAlchemyError` qui logue
`daily_snapshot_failed` avec `exc_info=True` et ne relance pas, pour qu'un échec du comptage
ne fasse jamais échouer le Container App Job ni ne masque le succès déjà acquis de la purge.
Docstring de module étendue pour mentionner cette seconde responsabilité.

Tests dans `agents/cleanup/tests/test_cleanup.py` : la fixture SQLite en mémoire crée
désormais aussi une table `cvs` minimale (id seul), avec un helper `_add_cv`. Quatre
nouveaux tests couvrent `_snapshot_totals` (base vide, offres seules, CV seules, les deux
combinés), et une classe `TestMainDailySnapshot` (3 tests) couvre que `main()` logue bien
`daily_snapshot` avec les bons champs, qu'un échec de `_snapshot_totals` est avalé (logue
`daily_snapshot_failed`, ne relance pas), et que `cleanup_completed` continue de se loguer
normalement à côté de la nouvelle étape.

**Retours `reviewer-backend`.** Premier passage : `CHANGEMENTS REQUIS` sur 3 points, tous
corrigés dans le commit `806cfa1`. (1) `_snapshot_totals` n'avait pas de log d'entrée,
contrairement à `_cleanup` qui logue `cleanup_started` dès le début — ajouté
`logger.info("daily_snapshot_started")` en tête de fonction, par cohérence. (2) La classe
`TestMainDailySnapshot` et ses 4 méthodes n'avaient ni docstring ni annotation `mocker:
MockerFixture` — ajoutées. (3) Le commentaire au-dessus du `except SQLAlchemyError` best-effort
de `main()` (~ligne 118-121) a été renforcé pour dire explicitement que l'absence de `raise`
est un choix délibéré — c'est le premier endroit du repo qui avale une exception DB sans la
relancer, et le reviewer voulait que ça se lise comme une décision assumée plutôt qu'un oubli.

### Décisions techniques

- **Nom de l'événement et des champs figés.** `daily_snapshot` / `total_offers` /
  `total_cvs` ont été pré-convenus avec le consommateur workbook/KQL — ne pas renommer sans
  prévenir en aval.
- **Session DB séparée pour le snapshot.** Ouvrir une nouvelle session plutôt que de
  réutiliser celle de `_cleanup` garde le comptage découplé de la transaction de purge
  (déjà commit et fermée à ce stade) : un échec du comptage ne peut pas interférer avec la
  transaction de suppression déjà validée.
- **`_snapshot_totals` documente désormais `Raises: SQLAlchemyError`** (comme `_cleanup`),
  pour rester cohérent avec le fait que c'est précisément cette exception que `main()`
  attrape autour de l'appel.

**Vérification :** revue statique des docstrings (`_snapshot_totals`, docstring de module,
`main()`) contre `conventions-python` — Google style, complètes, `Raises:` ajouté sur
`_snapshot_totals` par cohérence avec `_cleanup`. 7 nouveaux tests (4 `_snapshot_totals` +
3 `TestMainDailySnapshot`) portent le total de `agents/cleanup/tests/test_cleanup.py` à 11
(en plus des 4 tests `_cleanup` déjà existants) — non ré-exécutés dans cette session de
documentation, à valider par `pytest` avant ouverture de la PR.

## PR #207 — fix(cleanup): supprimer les match_analyses avant les matches obsolètes (FK violation en prod)

**Date :** 2026-07-19
**Branche :** `fix/cleanup-match-analysis-fk-violation` → `dev`

### Contexte

Le Container App Job `job-jf-dev-frc-cleanup` échouait à chaque exécution en dev (backoff
limit atteint, toutes les exécutions en erreur) avec
`sqlalchemy.exc.IntegrityError: ForeignKeyViolation on fk_match_analyses_match_id_ref_matches`.
Cause racine : `_cleanup()` (`agents/cleanup/main.py`) supprimait les `Match` obsolètes sans
supprimer au préalable les `MatchAnalysis` qui les référencent, alors que
`MatchAnalysis.match_id` est une FK NOT NULL vers `matches.id` sans `ondelete="CASCADE"` —
PostgreSQL refuse la suppression d'un match encore référencé. Effet de bord silencieux :
`_cleanup()` levait avant que le code du `daily_snapshot` (PR #206) n'ait la moindre chance
de s'exécuter, donc cette seconde fonctionnalité était elle aussi bloquée sans qu'aucune
erreur ne le signale directement.

### Ce qui a été fait

`_cleanup()` supprime maintenant les `MatchAnalysis` (via une sous-requête sur les matches
obsolètes) avant de supprimer les `Match` obsolètes, dans le même ordre que le
`_delete_cv` existant de `agents/webapp/routers/cv.py` (lignes 817-825), qui gère déjà la
FK identique correctement. Le type de retour de `_cleanup()` passe de `tuple[int, int]`
à `tuple[int, int, int]` (ajout de `deleted_analyses`), et `main()` logue désormais
`deleted_analyses` aux côtés de `deleted_offers`/`deleted_matches` dans l'événement
`cleanup_completed`. Les tests existants de `_cleanup` dans
`agents/cleanup/tests/test_cleanup.py` ont été mis à jour pour dépaqueter le 3-tuple.

Un nouveau test de régression, `test_stale_offer_with_analyzed_match_deleted_without_fk_violation`,
reproduit le scénario réel : offre obsolète → match → match_analysis, et vérifie que les
trois sont supprimés sans erreur. La fixture `db_session` active désormais
`PRAGMA foreign_keys=ON` (désactivé par défaut sous SQLite) pour que la FK
`match_analyses → matches` soit réellement contrainte, comme sous PostgreSQL — sans ce
pragma le test passerait même sans le fix, ce qui en ferait un faux test de régression.
Vérifié en revertant temporairement le fix en local : le test échoue alors avec exactement
la même `IntegrityError` que celle observée en prod.

Docstrings de `_cleanup` (ordre des 3 étapes, raisonnement FK) déjà à jour dans le commit
de fix — relues contre `conventions-python`, aucune correction nécessaire. Docstring de
module et docstring de `main()` légèrement complétées pour mentionner explicitement les
match analyses, pas seulement les matches.

### Décisions techniques

- **Pas de migration `ondelete="CASCADE"` dans cette PR.** Option évaluée puis
  délibérément écartée du périmètre de ce hotfix urgent : une migration DB nécessiterait
  l'aval de `reviewer-infra` et touche un schéma destiné à la prod — plus de portée qu'un
  hotfix urgent ne le justifie. Vérifié par grep que `match_analyses` est la seule FK
  non-cascade vers `matches.id` et que rien ne référence `match_analyses.id` : le fix
  applicatif seul suffit, sans laisser d'autre point d'appel non protégé.

**Vérification :** revue statique de la docstring `_cleanup` contre `conventions-python`
(Google style, complète, déjà à jour dans le commit de fix). Nouveau test de régression
confirmé par reversion locale du fix (échoue avec l'`IntegrityError` exacte de prod, sans
le fix). `agents/cleanup/tests/test_cleanup.py` passe de 11 à 12 tests.

## PR #208 — fix(telemetry): AppRoleName toujours "unknown_service" dans AppTraces

**Date :** 2026-07-19
**Branche :** `fix/apptraces-approlename-unknown-service` → `dev`

### Contexte

Depuis que le pont structlog→`logging` (PR #205) a commencé à peupler AppTraces,
chaque événement y apparaît avec `AppRoleName == "unknown_service"` au lieu du nom réel
de l'agent (`"cleanup"`, `"matching"`, etc.), alors que `Properties.service` — logué
explicitement par `configure_telemetry` via `logger.info("telemetry_configured",
service=service_name)` — est correct. Tâche menée en investigation d'abord : la cause a
été confirmée en lisant le code réellement installé de `azure-monitor-opentelemetry==1.8.8`
(`_configure.py` / `_utils/configurations.py`), pas supposée. `configure_azure_monitor(**kwargs)`
dans cette version n'accepte pas du tout de mot-clé `service_name` — sa signature réelle
ne reconnaît qu'un `resource=<opentelemetry.sdk.resources.Resource>`. Le kwarg
`service_name` non reconnu était absorbé silencieusement, sans erreur : `_get_configurations`
copie chaque kwarg dans un dict interne mais ne relit que les clés qu'elle reconnaît.
`resource` n'était donc jamais renseigné, et l'appel retombait sur `Resource.create()` sans
attributs, dont le `service.name` par défaut est exactement `"unknown_service"` — vérifié
empiriquement dans un shell Python (`Resource.create().attributes[SERVICE_NAME] ==
"unknown_service"`, `Resource.create({SERVICE_NAME: "cleanup"}).attributes[SERVICE_NAME]
== "cleanup"`).

Point important : ce bug est indépendant de la PR #205. Vérifié via
`git log --oneline -S "service_name" -- JobFinder/python/shared/telemetry.py`, qui montre
que le kwarg `service_name` a été introduit dans un commit antérieur, `58e4d9d` ("feat:
inject Application Insights into all Container App Jobs"), trois commits avant le début
des travaux de la PR #205. Il n'était simplement pas observable avant #205, puisqu'AppTraces
ne recevait aucun événement tant que ce pont n'existait pas. Les 6 agents sont affectés de
façon identique, puisqu'ils passent tous par cette même fonction partagée
`configure_telemetry()` (confirmé en grepant chaque site d'appel de `configure_telemetry(...)`).

### Ce qui a été fait

`configure_telemetry` (`shared/telemetry.py`) construit désormais explicitement la
`resource` attendue par `configure_azure_monitor` :
`resource=Resource.create({SERVICE_NAME: service_name})`, à la place du kwarg
`service_name=service_name` invalide. Une nouvelle classe de tests,
`TestAzureMonitorResourceServiceName` (`tests/test_telemetry.py`), mocke
`configure_azure_monitor` à son emplacement d'import réel
(`azure.monitor.opentelemetry.configure_azure_monitor`, importé localement dans la
fonction) et vérifie que la `resource` passée porte le bon `service.name`, et qu'aucun
kwarg `service_name` n'est transmis. Les deux tests ont été vérifiés en échec contre le
code pré-fix (appel exact avec le mauvais kwarg).

Le paragraphe de docstring de module documentant ce piège `unknown_service` (déjà ajouté
dans un commit précédent de cette branche) et la docstring mise à jour de
`configure_telemetry` (Args: `service_name`, note sur `resource=` vs `service_name=`) ont
été relus contre `conventions-python` — Google style, complets, reformulation mineure
appliquée (référence interne non vérifiable retirée, comportement observable conservé).

**Vérification :** revue statique des docstrings de `shared/telemetry.py` contre
`conventions-python` (reformulation mineure, voir ci-dessus). Les deux nouveaux tests de
`TestAzureMonitorResourceServiceName` ont été confirmés en échec contre le code pré-fix.

## PR #209 — docs: déplacer le contexte personnel de CLAUDE.md, anonymiser une entrée JOURNAL.md

**Date :** 2026-07-20
**Branche :** `docs/move-personal-context-to-local` → `dev`

### Contexte

Suite à une fouille complète de l'historique git avant passage du repo en public,
l'utilisateur a repéré qu'une courte section personnelle de `CLAUDE.md` était committée
depuis le tout premier commit. Un contenu équivalent figure déjà dans `README.md`
(destiné à être public), mais l'utilisateur ne connaissait pas encore `CLAUDE.local.md` /
`~/.claude/CLAUDE.md` au moment où il l'a écrit dans `CLAUDE.md`, et préfère désormais
garder ce fichier purement technique.

En vérifiant que `docs/JOURNAL.md` lui-même ne recontenait rien de comparable, une entrée
(PR #187) nommait explicitement une entreprise dans le contexte d'un test réel de matching
sur le profil personnel de l'utilisateur — plus identifiant qu'un simple prénom déjà
implicite via le compte GitHub, donc anonymisé. Deux autres entrées (PR #166 et PR #170) reprenaient le même récit de
reconversion que celui retiré de `CLAUDE.md`, l'une comme exemple de prompt few-shot,
l'autre en référence à un test manuel sur le CV réel de l'utilisateur — génériciées pour
la même raison. Une passe de vérification supplémentaire a trouvé une cinquième occurrence
(PR #185) : un exemple diagnostique citait un domaine professionnel antérieur de
l'utilisateur comme cause d'un faux positif lexical — également généricisé.

### Ce qui a été fait

La section personnelle a été retirée de `CLAUDE.md` et déplacée dans un nouveau
`CLAUDE.local.md`, ajouté au `.gitignore`. `README.md` n'a pas été modifié. Le nom
d'entreprise de l'entrée PR #187 dans `JOURNAL.md` a été remplacé par une référence
anonyme, le reste de l'entrée (score, `ft_id`, diagnostic technique) inchangé. Dans
l'entrée PR #166, l'exemple de prompt cité — qui reprenait le même récit personnel que
celui retiré de `CLAUDE.md` — a été généricisé aux deux endroits où il apparaissait, sans
changer le point technique expliqué (exemple entrée→sortie complet du few-shot). Dans
l'entrée PR #170, la référence à un CV réel portant ce même récit a été généricisée en
« un CV réel ». Dans l'entrée PR #185, l'exemple diagnostique nommant ce même domaine
professionnel antérieur a été reformulé sans en changer le point technique (un terme rare
mais hors-sujet cause un faux positif lexical). Pas de réécriture d'historique : décision
explicite de l'utilisateur, seuls les fichiers actuels sont modifiés.

**Vérification :** relecture du diff — seule la section personnelle disparaît de
`CLAUDE.md`, aucune autre section touchée ; `CLAUDE.local.md` bien ignoré par `git status`
après `git add` ; dans `JOURNAL.md`, seules l'occurrence du nom d'entreprise (PR #187), les
trois occurrences du récit de reconversion (PR #166 ×2, PR #170 ×1) et l'exemple
diagnostique (PR #185) sont modifiées, aucun autre contenu de ces entrées touché ; grep
final sur les termes identifiants (nom du domaine antérieur, certification, nom
d'entreprise) ne renvoie plus aucune occurrence hors du mot générique « reconversion »
seul.

## PR #210 — chore(terraform): min_replicas = 1 (frontend/webapp) + budget alert sur rg_app

**Date :** 2026-07-21
**Branche :** `feature/min-replicas-frontend-backend` → `dev`

### Contexte

Le frontend Next.js (`envs/dev/frontend.tf`) et le backend FastAPI (`envs/dev/webapp.tf`)
tournaient avec `min_replicas = 0` : scale-to-zero, donc un cold start (démarrage complet
du conteneur) sur la première requête après une période d'inactivité. L'utilisateur a
demandé une réplique minimum sur les deux pour éliminer ce cold start, en échange d'un
coût récurrent à connaître avant de merger.

### Ce qui a été fait

`min_replicas` passé de `0` à `1` dans `module.frontend` et `module.webapp`
(`max_replicas` inchangé à `1`). Aucun autre paramètre touché — les deux apps restent à
0.5 vCPU / 1Gi. Suite à la remarque non-bloquante de `reviewer-infra` (absence de
justification locale pour un écart volontaire par rapport à la valeur par défaut du
module, documentée comme scale-to-zero dans `variables.tf`), un commentaire WHY de deux
lignes a été ajouté au-dessus de `min_replicas = 1` dans les deux fichiers, renvoyant vers
cette entrée de journal pour le détail du calcul.

### Estimation de coût

Tarification Consumption plan Azure Container Apps : $0.000024/vCPU-s et $0.000003/GiB-s
en actif, $0.000008/vCPU-s et $0.000001/GiB-s en idle (~1/3 du tarif actif) ; franchise
gratuite mensuelle de 180 000 vCPU-s / 360 000 GiB-s / 2M requêtes, **par abonnement**
(déjà partiellement consommée par les Container App Jobs existants).

Avec `min_replicas = 1`, une réplique quasi inactive (peu de trafic, un projet portfolio)
est facturée au tarif idle plutôt qu'au tarif actif — écart d'un facteur ~3 par rapport à
une estimation qui ignorerait ce détail. Pour les deux apps (0.5 vCPU / 1Gi chacune,
730h/mois, quasi 100% idle) :
- vCPU-s idle : 2 × 0,5 × 2 628 000 = 2 628 000 vCPU-s/mois → ≈ 21 $
- GiB-s idle : 2 × 1 × 2 628 000 = 5 256 000 GiB-s/mois → ≈ 5,3 $

Soit **≈ 24 à 26 $/mois (≈ 22-24 €/mois) pour les deux apps combinées**, franchise
gratuite non déduite par prudence (elle est probablement déjà consommée par les jobs
existants). Estimation basse : trafic réel occasionnel facturé au tarif actif sur de
courtes fenêtres, négligeable à ce volume de requêtes. Coût uniquement effectif après
merge vers `dev` (déclenche l'apply CI).

**Vérification :** relecture du diff sur `envs/dev/frontend.tf` et `envs/dev/webapp.tf` —
seul `min_replicas` change (`0` → `1`) dans `module.frontend` et `module.webapp`,
`max_replicas` reste à `1`, aucun autre argument (cpu, memory, secrets, env_vars, identity)
touché. Aucun commentaire préexistant des deux fichiers ne référençait le scale-to-zero ou
`min_replicas = 0` : rien n'était devenu obsolète suite au changement. `terraform fmt -check`
et `terraform validate` passent après ajout du commentaire WHY et réalignement des blocs.

### Budget alert sur rg_app (ajout à la même PR)

**Contexte :** suite à l'estimation ci-dessus, l'utilisateur a demandé une alerte de
budget Azure sur `rg-jf-dev-frc-app` (le resource group qui porte le frontend et le
webapp) avec un seuil à ~40 $/mois, pour détecter une dérive de coût sans surveillance
manuelle.

**Ce qui a été fait :** ajout de `azurerm_consumption_budget_resource_group.app`
(`envs/dev/monitoring.tf`, nouvelle section « Cost Alerting ») ciblant
`data.azurerm_resource_group.rg_app.id`, `time_grain = "Monthly"`, deux notifications
(`operator = "GreaterThanOrEqualTo"`, `threshold_type = "Actual"`) à 80% et 100% du
montant, routées vers `azurerm_monitor_action_group.owner` déjà utilisé par les autres
alertes (pas de duplication d'email). Le montant est exposé via une nouvelle variable
`budget_amount` (`envs/dev/variables.tf`, défaut `40`, validation `> 0`) plutôt que
codé en dur, pour rester ajustable par environnement. `time_period.start_date` est fixé
au premier jour du mois courant (`2026-07-01T00:00:00Z`) ; cet attribut n'est pas
force-new, donc il n'a pas besoin d'être maintenu à jour à chaque mois.

Suite à la remarque non-bloquante de `reviewer-infra` (un seuil unique à 100% Actual ne
déclenche qu'une fois le budget déjà entièrement consommé, ce qui contredit l'objectif de
détection précoce affiché en commentaire de section), un second seuil à 80% Actual a été
ajouté comme alerte précoce, en plus du seuil à 100% qui confirme le dépassement réel.

**Point d'attention signalé à l'utilisateur :** Azure facture dans la devise de
l'abonnement (souvent EUR pour un abonnement basé en France), pas nécessairement en USD.
Le montant `40` est un nombre brut dans cette devise-là, sans conversion — un commentaire
WHY dans `variables.tf` documente cette nuance pour éviter une confusion future entre
l'estimation en $ de la section précédente et le seuil réel appliqué en €.

**Vérification :** `terraform fmt -check` et `terraform validate` passent. Ce type de
ressource (`azurerm_consumption_budget_resource_group`) ne figure pas dans la liste des
ressources critiques du skill `conventions-terraform` (pas de tags supportés par le
provider sur ce type, donc pas de bloc `tags` ni de `prevent_destroy`/`protect` requis).

## PR #211 — fix(matching): filtre dur par code ROME + purge des matches obsolètes

**Date :** 2026-07-21
**Branche :** `feature/matching-rome-code-hard-filter` → `dev`

### Contexte

Un testeur externe (CV bâtiment) a vu apparaître des annonces développeur / analyste
financier dans ses correspondances. Diagnostic : aucun filtre de métier/domaine
n'existait dans le pipeline de matching — `_get_all_matches`
(`agents/matching/main.py`) comparait chaque CV à **toutes** les offres du pool
partagé via cosinus (`o.embedding <=> c.embedding`), sans jointure ni clause sur
`offers.rome_code`. Le seul filtre appliqué à l'affichage était géographique
(`routers/matches.py::commune_zone_condition`). Le bonus lexical qui aurait pu
partiellement rattraper ça avait déjà été retiré le 2026-07-10 sans filtre de
remplacement (`prompt-matching-remove-lexical-bonus.md`).

### Ce qui a été fait

`_get_all_matches` restreint désormais les offres candidates, pour chaque CV, à
celles dont `rome_code` appartient à l'ensemble des codes ROME de ce CV précis —
via une nouvelle CTE `cv_rome_codes` qui teste, pour chaque code du profil
(`user_profiles.rome_codes`, JSONB `{code: {"cv_ids": [...], "label": ...}}`),
que le `cv_id` figure dans `cv_ids` (`jsonb_each` + opérateur `?` de containment
JSONB). Portée volontairement **par CV, pas par utilisateur** : un compte avec un
CV dev et un CV bâtiment (cas explicitement supporté, cf. commentaire
`routers/cv.py:263-265`) ne doit jamais voir le CV bâtiment matcher sur les offres
dev de l'autre CV du même compte.

Nouvelle fonction `_purge_stale_matches` : supprime les `matches` (et leurs
`match_analyses`, même ordre que `_delete_cv` dans `routers/cv.py` — FK sans
CASCADE) qui ne respectent plus ce filtre, pour nettoyer les faux positifs déjà en
base (dont ceux vus par le testeur), pas seulement empêcher les nouveaux. Branchée
dans `main()` après `_upsert_matches` mais avant `_enqueue_top_n_analyses` — sinon
un match obsolète pourrait être enqueue pour analyse GPT-4o-mini juste avant d'être
supprimé. Le compte purgé est logué dans `matching_run_completed`
(`purged_matches`).

Un CV dont l'extraction ROME a échoué après épuisement des tentatives
(`CV.status = "error"`, déjà géré par `agents/cv_analysis/main.py:583-594`) n'a par
construction aucune entrée `cv_ids` le référençant : il est naturellement exclu de
tout match par le nouveau filtre, sans code supplémentaire — vérifié.

Docstring de `_get_all_matches` complétée avec l'invariant du filtre (quel CV voit
quelle offre, et pourquoi).

### Décisions techniques

- **Limite acceptée, pas corrigée ici :** `offers.rome_code` est une colonne
  simple (pas un tableau), et `_build_offer_values`/`_build_upsert_statement`
  (`agents/offer_fetching/main.py:127-206`) écrasent sans condition `rome_code` à
  chaque upsert avec le code de la dernière recherche qui a retourné l'offre. Une
  offre réellement pertinente pour plusieurs codes ROME mais dont le dernier
  upsert ne l'a taguée qu'avec un seul reste invisible aux CV dont c'est un des
  *autres* codes pertinents. Documenté en commentaire SQL dans `cv_rome_codes` ;
  corriger nécessiterait de passer `rome_code` en tableau, hors scope de ce fix.
- **Pas de migration Alembic** : le filtre s'appuie uniquement sur des colonnes
  déjà existantes (`user_profiles.rome_codes` JSONB, `offers.rome_code`).
- **Pas de refund de crédit d'analyse** pour une `match_analysis` purgée
  déclenchée manuellement — l'analyse a été réellement livrée contre un match qui
  existait à l'époque, même trade-off que l'ordre blob-puis-commit de
  `routers/cv.py::_delete_cv`.

### Tests

`_get_all_matches` et `_purge_stale_matches` reposent sur du SQL PostgreSQL
spécifique (`jsonb_each`, `CROSS JOIN LATERAL`, opérateur `?`) incompatible
SQLite — même exclusion documentée que le reste de `_get_all_matches`
(`tests/README.md`, section "Intentionally excluded"). Un test unitaire minimal
(`test_matching.py::TestPurgeStaleMatches`) vérifie, avec une session mockée,
l'ordre des deux `DELETE` (match_analyses avant matches) et que le compte retourné
correspond aux lignes mockées — pas la logique SQL elle-même.

**Vérification :** contre un throwaway Postgres 16 + pgvector (conteneur Docker
local, `run_migrations()` exécuté dessus) : deux profils/CV distincts (codes
M1805 et F1106), une offre par code, un faux positif inséré manuellement
(offre M1805 associée au CV F1106) pour simuler l'état bogué observé par le
testeur. Après exécution de `_get_all_matches` + `_purge_stale_matches` : (a) le
CV F1106 ne matche que sur l'offre F1106, jamais sur M1805 même si le cosinus
dépasserait le seuil ; (b) le faux positif pré-existant est supprimé
(`purged_matches == 1`) ; (c) un CV sans entrée `cv_ids` (extraction ROME
échouée) n'obtient toujours aucun match. `pytest tests/test_matching.py -v`
(6/6) et la suite complète (279/279) passent.

## PR #212 — fix(offer-fetching): retrait du fallback ROME 100% dev

**Date :** 2026-07-21
**Branche :** `fix/offer-fetching-remove-dev-fallback-rome-codes` → `dev`

### Contexte

Suite du diagnostic matching (`prompt-matching-rome-code-hard-filter.md`,
`prompt-cv-analysis-rome-code-determinism-and-precision.md`) : `FALLBACK_ROME_CODES`
(`agents/offer_fetching/main.py`, `["M1805", "M1802", "M1806", "M1810", "M1811"]`) était
utilisé par `_get_active_rome_codes` quand aucun profil n'a de `rome_codes` non vide —
et il était 100% développement/informatique. Ça allait à l'encontre du principe déjà
acté à plusieurs reprises sur ce projet (retrait du bonus lexical `term_stats`, retrait
de `tech_keywords` — voir `prompt-matching-remove-lexical-bonus.md`) : un mécanisme de
matching générique, valable pour tous les métiers, pas biaisé tech par construction.
Décision actée avec Vincent (21/07) : retirer `FALLBACK_ROME_CODES` entièrement, sans
le remplacer par un autre jeu de codes codé en dur — un fallback « équilibré »
réintroduirait le même biais sous une autre forme.

### Ce qui a été fait

`FALLBACK_ROME_CODES` supprimé. `_get_active_rome_codes` retourne désormais une liste
vide quand aucun profil n'a de code ROME actif (log `rome_codes_none_active` au lieu de
`rome_codes_using_fallback`), documenté en docstring comme un état normal — en attendant
qu'un premier profil réel ait des codes — pas une erreur. Dans `main()`, l'appel à
`get_access_token()` et la boucle de fetch France Travail sont maintenant sautés quand
`rome_codes` est vide (évite un aller-retour OAuth inutile), sans court-circuiter
`_embed_pending_offers()` qui doit continuer à traiter les offres déjà en base
indépendamment du cycle de fetch courant. Suite à une remarque non-bloquante de
`reviewer-backend` (le nouveau garde faisait grandir `main()`), le token +
cutoff + boucle de fetch/upsert ont été extraits dans une nouvelle fonction
`_fetch_and_upsert_new_offers(rome_codes) -> int`, appelée depuis `main()`
uniquement quand `rome_codes` est non vide.

Suite à un verdict `CHANGEMENTS REQUIS` de `reviewer-backend` sur un `except
Exception:` nu pré-existant autour de `run_migrations()` (ligne 397 avant fix,
règle "jamais de `except Exception` nu" du skill `conventions-python`, sans
exception documentée y compris pour un commentaire justificatif) : remplacé par
`except (SQLAlchemyError, CommandError):`, qui correspond exactement au
`Raises:` documenté par `run_migrations()` (`shared/db.py`). Comportement
inchangé (`raise` nu identique), simple resserrement du type capturé.

Même passe, second `CHANGEMENTS REQUIS` de `reviewer-backend` : `_upsert_offers`
(pré-existante, non touchée par ce fix jusque-là) exécute un appel DB direct
sans logger son entrée avant le `try` — manquant vis-à-vis de la règle
"Logging" du skill (`conventions-python`, ligne 31 : toute fonction avec appel
externe DB/API/réseau direct doit logger son entrée). Ajout d'un
`logger.info("offers_upsert_started", rome_code=rome_code, count=...)` juste
avant le `try`, cohérent avec le pattern déjà en place pour
`_get_active_rome_codes` dans ce même fichier.

Référence stale mise à jour dans `docs/BACKLOG.md` (section corpus mono-sectoriel) :
la cause n'est plus le fallback dev mais l'absence de fetch tant qu'aucun profil n'a de
code actif.

### Tests

`_get_active_rome_codes` mocke systématiquement son retour dans `test_offer_fetching.py`
— aucun test n'exerçait le comportement SQL/fallback réel, donc aucun test n'asserte sur
la valeur du fallback lui-même. Le test existant avec `_get_active_rome_codes` mocké à
`[]` (`TestMainSchedulingGuard::test_proceeds_when_within_scheduled_local_hour`) reste
valide tel quel — il ne vérifie pas l'appel à `get_access_token`. Entrée ajoutée dans
`tests/README.md` (« Intentionally excluded ») pour `_get_active_rome_codes`
(`jsonb_object_keys`, PostgreSQL-spécifique, incompatible SQLite), même absence
d'exclusion documentée jusqu'ici.

**Vérification :** `pytest tests/test_offer_fetching.py -v` (29/29 passent). Grep
`FALLBACK_ROME_CODES` sur tout le repo : plus aucune occurrence dans le code source
(seule cette entrée de journal nomme encore la constante retirée, à titre descriptif).

## PR #213 — fix(cv-analysis): déterminisme + précision de l'extraction ROME depuis le CV

**Date :** 2026-07-21
**Branche :** `feature/cv-analysis-rome-determinism-and-precision` → `dev`

### Contexte

Suite du diagnostic ROME (`prompt-cv-analysis-rome-code-determinism-and-precision.md`,
même série que `prompt-matching-rome-code-hard-filter.md` et
`prompt-offer-fetching-remove-dev-fallback-rome-codes.md`, PR #211/#212) : un même CV
uploadé deux fois de suite produisait deux jeux de codes ROME totalement disjoints dans
`_extract_rome_codes` (`agents/cv_analysis/main.py`). Deux causes cumulées identifiées :
(1) aucun `temperature`/`seed` fixé sur l'appel OpenAI de cette fonction — contrairement
à `_analyze_cv_quality` dans le même fichier et `_analyze_match` de
`agents/match_analysis/main.py`, qui pinnaient déjà `ANALYSIS_TEMPERATURE`/`ANALYSIS_SEED` ;
(2) le prompt système ne distinguait pas le métier propre du candidat du
secteur/produits/outils qu'il mentionne, et imposait un plancher de 3 codes minimum qui
poussait le modèle à ajouter du bruit sur des CV mono-métier.

### Ce qui a été fait

Dans `_extract_rome_codes` : ajout de `temperature=ANALYSIS_TEMPERATURE,
seed=ANALYSIS_SEED` à l'appel `_openai_client.chat.completions.create(...)`, alignant
cette fonction sur le reste du fichier. Prompt système réécrit : "3 à 5 codes ROME
pertinents" devient "1 à 5 codes ROME pertinents", avec deux règles explicites ajoutées —
le code doit refléter le métier ou la fonction réellement exercée par le candidat
lui-même, jamais le secteur d'activité, les produits/outils vendus ou utilisés, ou le
métier des personnes/clients mentionnés dans le CV (exemple fourni : un commercial qui
vend des solutions informatiques reste un métier commercial, pas un métier de
développeur) ; et la liste n'est plus jamais complétée artificiellement pour atteindre un
minimum — un CV clairement mono-métier peut n'avoir qu'un seul code pertinent. Docstring
de `_extract_rome_codes` mise à jour en conséquence : section dédiée aux deux invariants
(déterminisme, précision occupation-candidat) avec renvoi vers le prompt pour le
diagnostic complet, et `Returns:` corrigé de "3–5 dicts" à "1–5 dicts".

`tests/test_cv_analysis.py` : nouveau test
`test_pins_temperature_and_seed_for_determinism` dans `TestExtractRomeCodes`, calqué sur
le test du même nom déjà présent dans `TestAnalyzeCvQuality` — vérifie que `temperature`
et `seed` sont bien passés en kwargs à l'appel `chat.completions.create`.

Suite à une remarque non-bloquante de `reviewer-backend` (le prompt système allongé
faisait dépasser `_extract_rome_codes` du seuil de 40 lignes recommandé par le skill),
le prompt système a été extrait en constante de module `ROME_EXTRACTION_SYSTEM_PROMPT`,
sur le modèle de `CV_QUALITY_SYSTEM_PROMPT` déjà présent dans ce même fichier.

### Décisions techniques

Limite connue et volontairement hors scope : `_merge_rome_codes` ne fait qu'une union des
codes ROME dans `user_profiles.rome_codes` (ajout de `cv_id` aux `cv_ids` existants,
rafraîchissement du label) — il ne retire jamais rétroactivement un code qui aurait été
extrait par erreur avant ce fix. Un profil déjà contaminé par du bruit ROME issu de
l'ancien comportement (plancher à 3, absence de déterminisme) le reste tant que ce CV
n'est pas ré-analysé ; ce fix corrige l'extraction pour les nouvelles analyses, pas les
profils existants.

### Tests

Grep de "3 à 5 codes"/"3-5" sur `agents/cv_analysis/main.py` : plus aucune occurrence
liée au prompt d'extraction ROME (la seule mention restante de "3 à 5" dans le fichier
est "3 à 5 phrases" dans `CV_QUALITY_SYSTEM_PROMPT`, qui borne la longueur de la
`synthese` — sans rapport avec le nombre de codes ROME). `docs/BACKLOG.md` conserve à la
ligne 37 la formulation historique "3 à 5 codes ROME" dans la section `[M4 — PR 1]` —
c'est la spec de planification d'origine de PR #86 (déjà mergée), non une doc vivante du
comportement actuel ; laissée telle quelle par cohérence avec les autres sections
`[M4 — PR N]` non annotées de ce fichier.

**Vérification :** `pytest tests/test_cv_analysis.py -v` (35/35 passent) et la suite
complète (280/280) passent.

## PR #214 — fix(cv-analysis): deepcopy + flag_modified sur la fusion JSONB des codes ROME

**Date :** 2026-07-21
**Branche :** `fix/cv-analysis-rome-merge-shallow-copy` → `dev`

### Contexte

Suite du prompt local `prompt-cv-analysis-rome-merge-shallow-copy-bug.md` (non versionné
dans `docs/prompts/`) : `_merge_rome_codes` (`agents/cv_analysis/main.py`) perdait
silencieusement le `cv_id` d'un CV pour tout code ROME déjà présent dans le profil. Cause :
`current: dict = dict(profile.rome_codes or {})` (l.259 avant fix) ne fait qu'une copie
superficielle — les dicts imbriqués par code ROME restent le même objet que celui déjà
tracké par SQLAlchemy sur `profile.rome_codes`. Muter `current[code]["cv_ids"]` pour un
code existant mutait donc aussi la valeur trackée, ce qui faisait échouer la détection de
changement JSONB de SQLAlchemy au flush : l'écriture était perdue sans aucune erreur, et le
log `rome_merge_done` apparaissait normalement malgré tout. Seul le tout premier CV créant
des codes inédits pour un profil fonctionnait ; tout CV suivant retombant sur un code déjà
créé perdait silencieusement son `cv_id`.

### Ce qui a été fait

Dans `_merge_rome_codes` : `dict(profile.rome_codes or {})` remplacé par
`copy.deepcopy(profile.rome_codes or {})` (copie réellement indépendante des dicts
imbriqués), et ajout de `flag_modified(profile, "rome_codes")` juste après
`profile.rome_codes = current`, avant `profile.updated_at = ...` — marquage explicite de la
colonne comme modifiée, indépendant de la détection automatique de SQLAlchemy. Import
`copy` ajouté en tête de fichier, `flag_modified` importé depuis
`sqlalchemy.orm.attributes` à côté des autres imports SQLAlchemy. Docstring de
`_merge_rome_codes` complétée d'un paragraphe dédié expliquant l'invariant : colonne JSONB
mutable en place, `deepcopy` est le correctif réel (il restaure une copie dont le contenu
diffère effectivement de la valeur trackée, ce qui permet à SQLAlchemy de détecter le
changement normalement au flush) ; `flag_modified` est un garde défensif, pas strictement
requis vu le `deepcopy`, contre un refactor futur qui réintroduirait un partage de
références imbriquées. Un commentaire WHY dans ce sens a été ajouté au site d'appel de
`flag_modified` (l.280-282) : c'est l'endroit qu'un futur éditeur serait le plus
susceptible de retirer en le croyant redondant avec le `deepcopy`.

`tests/test_cv_analysis.py`, `TestMergeRomeCodes` : nouveau test
`test_calls_flag_modified_for_jsonb_dirty_tracking`, qui mocke `_mod.flag_modified` et
vérifie `assert_called_once_with(mock_profile, "rome_codes")`. Suite à une remarque de
`reviewer-backend` (ce test ne prouvait que la moitié `flag_modified` du fix — un
`dict()` superficiel aurait laissé passer ce même test, puisque le sous-dict partagé
n'aurait jamais été distingué par une simple réassignation d'attribut sur un
`MagicMock`), second test ajouté :
`test_deep_copies_so_original_nested_dict_is_left_untouched` — conserve une référence au
dict imbriqué d'origine avant l'appel, puis vérifie qu'il n'a pas été muté en place.
Vérifié manuellement que ce nouveau test échoue bien si `copy.deepcopy` est remplacé par
`dict()` (`AssertionError: ['cv-uuid-1', 'cv-uuid-2'] == ['cv-uuid-1']`), avant de
restaurer le fix — preuve qu'il attrape réellement une régression vers la copie
superficielle, contrairement au premier test.

### Décisions techniques

Limite connue, non corrigée par ce fix : la fusion reste additive (elle n'ajoute que le
`cv_id` du CV en cours d'analyse, jamais de retrait). Un profil qui a déjà silencieusement
perdu un `cv_id` sous l'ancien bug ne se répare pas rétroactivement — la paire (CV, code)
manquante le reste tant que ce CV précis n'est pas ré-analysé. Conséquence concrète en
aval via le filtre dur par code ROME de PR #211 : un CV dont le `cv_id` manque sous un code
donné ne matchera aucune offre de ce code tant qu'il n'a pas été ré-analysé, même après ce
fix — même limite de non-réparation rétroactive que celle déjà documentée en PR #213 pour
le bruit ROME issu de l'ancien comportement d'extraction.

### Tests

Ce nouveau test est un garde-fou de régression sur l'appel lui-même (que
`flag_modified(profile, "rome_codes")` soit bien invoqué), pas une preuve que la
persistance fonctionne réellement : sous `MagicMock`, `profile.rome_codes` est un simple
attribut sans instrumentation SQLAlchemy — ni le bug de copie superficielle ni son fix ne
changent l'issue d'un test mocké de cette façon. Même limite déjà documentée pour d'autres
chemins dépendant du comportement réel de SQLAlchemy/PostgreSQL (par exemple les tests de
`_get_active_rome_codes`, qui n'assertent que sur une valeur de retour mockée, jamais sur
le comportement SQL réel — voir PR #212). La vérification décisive pour ce bug précis ne
peut se faire qu'en interrogeant directement `user_profiles.rome_codes` en base après un
second upload de CV partageant un code ROME déjà présent sur le profil — le log
`rome_merge_done` seul ne suffit pas : il apparaissait déjà normalement avant le fix,
c'est précisément ce qui a masqué le bug en premier lieu.

**Vérification :** `pytest tests/test_cv_analysis.py -v` (37/37) et la suite complète
(282/282) passent, incluant les deux nouveaux tests de `TestMergeRomeCodes`. Rappel (voir
Décisions techniques) : ces tests ne remplacent pas la vérification décisive contre une
vraie base PostgreSQL (requête `user_profiles.rome_codes` après un second upload
partageant un code ROME).

## PR #215 — feat(offer-fetching): passage en purement événementiel + fetch immédiat sur nouveau code ROME

**Date :** 2026-07-22
**Branche :** `feature/offer-fetching-event-driven-new-code-fetch` → `dev`

### Contexte

Suite du prompt local `prompt-offer-fetching-event-driven-and-new-code-fetch.md` (non
versionné dans `docs/prompts/`). `offer_fetching` ne tournait jusqu'ici que sur un timer fixe
12:00/20:00 Europe/Paris : un profil qui gagnait un nouveau code ROME entre deux exécutions
planifiées attendait jusqu'à ~16h avant qu'une offre pertinente ne soit fetchée. Un "Run now"
manuel en dehors de la fenêtre horaire exacte était par ailleurs un no-op silencieux, puisque
l'agent lui-même vérifiait l'heure locale avant de faire quoi que ce soit.

### Ce qui a été fait

`offer_fetching` devient un Container App Job purement événementiel (trigger `queue`, plus
`timer`). Un nouvel agent minimal `offer_fetch_scheduler` reprend l'ancien cron UTC DST-safe
12:00/20:00 Europe/Paris (`_is_scheduled_local_hour`, déplacé tel quel depuis
`offer_fetching`) et se contente de publier un message de refresh complet — il ne parle jamais
à France Travail, OpenAI ni à la base. `cv_analysis` publie désormais en plus un message ciblé
(avec des `rome_codes` explicites) chaque fois qu'un CV apporte au moins un code ROME
réellement nouveau au profil (`_merge_rome_codes` retourne maintenant `list[str]` au lieu de
`None` — les codes qui n'étaient pas déjà des clés du profil avant l'appel).

Les deux types de déclenchement partagent une seule queue (`offer-fetch-request`, nouvelle
dans `servicebus.tf`) et un seul consommateur (`_handle_fetch_request`, nouveau dans
`offer_fetching/main.py`). L'ancien corps de `main()` devient `_run_fetch_cycle(requested_codes:
list[str] | None)` : `None` déclenche un passage complet (recalcul de tous les codes ROME
actifs via `_get_active_rome_codes`), une liste déclenche un passage ciblé sur exactement ces
codes.

Terraform (`container_apps.tf`) : `job_offer_fetching` passe de `trigger_type = "timer"` à
`"queue"` (ajout `queue_name`, `servicebus_namespace`, secret de connexion Service Bus ;
suppression de `cron_expression`) ; nouveau module `job_offer_fetch_scheduler`, déclenché par
timer, avec un jeu d'env/secrets minimal (il n'appelle jamais que `send_message`).
`buildAgents.yml` : nouvelle étape build/push pour l'image `agents/offer-fetch-scheduler`,
ligne de résumé, étape `az containerapp job update` pour `job-jf-dev-frc-fetch-sched`.

Nouvel agent `agents/offer_fetch_scheduler/main.py` + `Dockerfile`, sur le modèle du
`Dockerfile` minimal d'`agents/cleanup` (partage le `requirements.txt` racine, pas de fichier
dédié).

Migration `030_add_offer_fetch_coordination.py` : deux nouvelles tables de coordination,
`offer_fetch_signal` (ligne unique `id=1`, flag `full_refresh_pending`) et
`offer_fetch_pending_codes` (une ligne par code ROME en attente), plus les classes ORM
`OfferFetchSignal`/`OfferFetchPendingCode` dans `shared/models.py` (import de `Boolean`,
`CheckConstraint`, `SmallInteger` ajoutés à l'en-tête).

### Décisions techniques

**Lock advisory Postgres.** `_handle_fetch_request` sérialise les cycles de fetch via
`pg_try_advisory_lock` (clé `OFFER_FETCH_LOCK_ID = 592034871`, distincte de
`shared.db.ALEMBIC_MIGRATION_LOCK_ID`). Ce lock n'est **pas redondant** avec
`max_executions = 1` (valeur par défaut du module `container_app_job`, qui sérialise
effectivement les runs en dev aujourd'hui) : la description de cette variable Terraform dit
explicitement "Increase for prod under load" — dès que cette valeur est relevée en prod, des
instances peuvent tourner en parallèle, et deux upserts complets touchant les mêmes lignes
`ft_id` dans un ordre de verrou différent peuvent deadlocker. Le lock doit être conservé même
si "un seul run a lieu aujourd'hui" ne semble pas le justifier dans l'état actuel de la config
dev.

**Pourquoi deux tables plutôt qu'une.** `offer_fetch_signal` porte un simple flag booléen (un
refresh complet est en attente ou non) ; `offer_fetch_pending_codes` porte une liste de valeurs
(quels codes ROME précis sont en attente). Un cycle qui ne peut pas acquérir le lock enregistre
ce dont il avait besoin (`_mark_full_refresh_pending` / `_mark_rome_codes_pending`) au lieu de
laisser tomber silencieusement le déclenchement ; le cycle qui détient le lock draine et
rejoue exactement ce qui a été accumulé (`_drain_pending_signal`, en boucle jusqu'à ce qu'un
passage revienne vide) avant de relâcher le lock — aucune perte sous contention.

**Clés primaires — deux versions.** Une première version donnait aux deux tables une clé
primaire non-UUID (`offer_fetch_signal` sur `id=1` fixe, `offer_fetch_pending_codes` sur le
code ROME lui-même). `reviewer-infra` a rejeté cette version : l'exception cache/stats de
`conventions-sql` est explicitement bornée à une table "recalculée et remplacée en bloc, pas
d'`ON CONFLICT`" — exactement l'inverse d'`offer_fetch_pending_codes` (dédupliquée
incrémentalement via `ON CONFLICT DO NOTHING`), et `offer_fetch_signal` est mise à jour en
place, jamais remplacée. Le reviewer a aussi montré que le codebase a déjà le pattern qu'il faut
pour ce cas précis : `Offer.id` (UUID) + `uq_offers_ft_id` (contrainte d'unicité séparée sur la
clé naturelle) — `on_conflict_do_update(constraint="uq_offers_ft_id")` cible déjà cette
contrainte, pas la PK. Les deux tables suivent maintenant ce même pattern : `id` UUID v4
standard sur les deux, `offer_fetch_pending_codes.rome_code` unique via
`uq_offer_fetch_pending_codes_rome_code` (la déduplication `ON CONFLICT DO NOTHING` cible cette
contrainte, comportement inchangé), `offer_fetch_signal` garde sa garantie de ligne unique via
une colonne séparée `singleton_key` (`UniqueConstraint` + `CHECK singleton_key = 1`) plutôt que
sur la PK elle-même. `agents/offer_fetching/main.py` mis à jour en conséquence
(`OfferFetchSignal.id == 1` → `OfferFetchSignal.singleton_key == 1` dans
`_mark_full_refresh_pending`/`_drain_pending_signal`). Les deux tables ont aussi gagné une
colonne `created_at` NOT NULL (`reviewer-infra` : règle inconditionnelle de `conventions-sql`,
indépendante de l'exception de clé primaire — `term_stats`, l'exemple même de cette exception,
garde un `created_at` malgré sa PK naturelle).

**Logs d'entrée manquants sur les nouvelles fonctions DB.** `reviewer-backend` a bloqué une
première passe : `_mark_full_refresh_pending`, `_mark_rome_codes_pending`, `_drain_pending_signal`
et la section lock/unlock de `_handle_fetch_request` appelaient `get_session()`/
`get_engine().connect()` sans logger leur entrée ni encadrer l'appel d'un `try/except
SQLAlchemyError` — contrairement à toutes les autres fonctions DB de ce même fichier
(`_upsert_offers`, `_get_active_rome_codes`, `_embed_pending_offers`) et au précédent quasi
identique de `shared/db.py::run_migrations` (même connexion AUTOCOMMIT, même paire lock/unlock).
Corrigé en reprenant ce même patron sur les quatre points.

**Compromis best-effort assumé.** Le dispatch de `cv_analysis` vers `offer-fetch-request` est
volontairement "best-effort" (loggé sur `ServiceBusError`, jamais relancé), contrairement au
dispatch `start-matching` juste au-dessus dans le même `main()` qui, lui, relance. Raison : sur
une redelivery du message `cv-analysis`, `_merge_rome_codes` retrouverait ces codes déjà
fusionnés par la première tentative réussie et retournerait `new_rome_codes=[]` — relancer ici
déclencherait un retry qui ne pourrait jamais renvoyer ce message précis. Le prochain refresh
planifié d'`offer_fetching` couvre de toute façon ces codes, indépendamment de l'issue de cet
envoi.

### Tests

`test_offer_fetching.py` perd `TestIsScheduledLocalHour`/`TestMainSchedulingGuard` (déplacées
telles quelles vers le nouveau `test_offer_fetch_scheduler.py`, qui couvre aussi `main()` du
nouvel agent) et gagne `TestMarkFullRefreshPending`, `TestMarkRomeCodesPending`,
`TestDrainPendingSignal`, `TestHandleFetchRequest`. `test_cv_analysis.py::TestMergeRomeCodes`
mis à jour pour asserter la nouvelle valeur de retour, plus un nouveau
`test_returns_new_codes_only` ; nouvelle classe `TestMainOfferFetchDispatch` (envoi quand des
codes nouveaux sont présents, pas d'envoi si vide, loggé-et-non-relancé sur `ServiceBusError`).
`tests/README.md` : nouvelle entrée "Intentionally excluded" pour la coordination par lock
advisory (comportement réel de `pg_try_advisory_lock` non simulable avec une session
mockée/SQLite) ; table "Modules covered" mise à jour (nouvelle ligne
`test_offer_fetch_scheduler.py`, fonctions de coordination ajoutées à la ligne
`test_offer_fetching.py`, dispatch offer-fetch-request ajouté à la ligne `test_cv_analysis.py`)
— corrigé pendant cette revue de documentation, ce n'était pas encore fait au moment de la
revue.

Deux dernières remarques non-bloquantes de `reviewer-infra` sur la même relecture, corrigées
avant merge puisque la migration n'a encore jamais été appliquée nulle part (renommage sans
risque) : la table `offer_fetch_signal` renommée `offer_fetch_signals` (seule table du schéma
qui aurait été au singulier — `uq_offer_fetch_signal_singleton_key`/
`ck_offer_fetch_signal_single_row` renommées en conséquence) ; `on_conflict_do_nothing` dans
`_mark_rome_codes_pending` cible désormais nommément `constraint=
"uq_offer_fetch_pending_codes_rome_code"` plutôt que `index_elements=["rome_code"]`, par
cohérence avec le précédent `on_conflict_do_update(constraint="uq_offers_ft_id")` déjà cité dans
le docstring de la migration.

**Découpage de `cv_analysis::main()` (`reviewer-backend`, bloquant).** Une relecture ciblée
`cv_analysis/main.py` a d'abord classé trois points préexistants (`except Exception` nu dans
`main()`, `main()` largement au-dessus de 40 lignes, `_upsert_cv_analysis` sans log d'entrée) en
remarque non-bloquante hors scope, puis — sur ma propre demande de reconsidération, calquée sur
un précédent posé plus tôt dans cette série sur des branches sœurs — a explicitement refusé de
les déclasser : le mandat du reviewer interdit de reclasser une règle "jamais/toujours" du skill
en remarque simplement parce qu'elle est ancienne, et son périmètre de revue est le *fichier*
modifié, pas seulement le hunk du diff (`main()` avait d'ailleurs été concrètement allongée par
le nouveau bloc de dispatch de cette feature). Verdict remonté à `CHANGEMENTS REQUIS`. Les trois
points ont été corrigés plutôt que de rouvrir la discussion une troisième fois :
- `except Exception:` autour de `run_migrations()` resserré en `except (SQLAlchemyError,
  CommandError):`, même correction et même import ajouté que sur `offer_fetching/main.py` en
  PR #212.
- `_upsert_cv_analysis` : `logger.info("cv_analysis_upsert_started", cv_id=cv_id,
  status=status)` ajouté avant son `try`, même pattern que `_get_cv_text`/`_set_cv_status`.
- `main()` découpée en quatre fonctions dédiées : `_handle_retry_quality_only` (branche retry),
  `_dispatch_start_matching`/`_dispatch_offer_fetch_request` (les deux envois Service Bus, avec
  chacune leur propre `Raises:` documentant le contraste relance/best-effort), et
  `_handle_new_cv_analysis` (flux nominal complet). `main()` ne fait plus qu'orchestrer
  `run_migrations()` + `receive_message` + délégation à l'une des deux poignées ; corps
  d'exécution ramené à ~20 lignes, `_handle_new_cv_analysis` à ~24.

**Vérification :** `pytest JobFinder/python` (295/295, découpage de `main()` inclus — les tests
existants mockent par nom de fonction sur le module, donc restent verts sans modification) et
`python -m alembic -c migrations/alembic.ini heads` (un seul head, `030`) repassés après toutes
les corrections de revue ci-dessus (clés primaires, logs d'entrée, renommage de table,
découpage de `main()`) ; `terraform fmt -check`/`terraform validate` propres sur `envs/dev`
(aucun changement Terraform dans cette dernière passe). `reviewer-infra` et `reviewer-backend`
tous deux APPROUVÉ (aucune remarque non-bloquante restante) sur leurs relectures finales
respectives. Limite
connue, identique à celle déjà documentée pour `_handle_fetch_request` dans `tests/README.md` :
la sérialisation réelle par `pg_try_advisory_lock` sous contention n'est validée que manuellement
contre un Postgres 16 jetable, jamais par la suite de tests automatisée. Un `terraform plan`
authentifié (nécessite le backend state + auth Azure, indisponible dans cette session) reste
recommandé avant merge pour confirmer que la conversion `job_offer_fetching` de `timer` à
`queue` ne déclenche pas un destroy/replace plutôt qu'une mise à jour en place.

### Suivi post-review : ligne singleton manquante

Question posée par l'utilisateur après la revue initiale : que se passe-t-il si la ligne unique
d'`offer_fetch_signals` (`singleton_key=1`, seedée une fois par la migration) disparaît hors
bande ? Réponse : un `UPDATE ... WHERE singleton_key = 1` sur une ligne absente ne lève aucune
erreur SQL — il touche simplement 0 ligne et "réussit" silencieusement. `_mark_full_refresh_pending`
aurait donc perdu un refresh planifié sans aucun signal ; `_drain_pending_signal` ne pouvait déjà
pas distinguer "rien en attente" (0 ligne touchée par l'`UPDATE` gardé, cas normal) de "ligne
disparue" (même symptôme).

Corrigé : `_mark_full_refresh_pending` vérifie désormais `result.rowcount == 0` sur son `UPDATE`
inconditionnel (sans ambiguïté possible) et lève `ValueError` avant tout `commit` si la ligne
manque. `_drain_pending_signal`, dont l'`UPDATE` est conditionné sur `full_refresh_pending = true`
et ne peut donc pas servir de test d'existence, fait d'abord une requête d'existence séparée
(`SELECT ... WHERE singleton_key = 1`) et lève la même erreur le cas échéant, avant tout
`UPDATE`/`DELETE`. Message d'erreur factorisé dans une constante module
`_OFFER_FETCH_SIGNAL_ROW_MISSING_MESSAGE` (remarque non-bloquante de `reviewer-backend` — le
message était dupliqué mot pour mot entre les deux fonctions). `_handle_fetch_request`'s
docstring mise à jour pour documenter que ce `ValueError` peut désormais la traverser.

`reviewer-backend` a vérifié que `ValueError` n'est jamais catché par le `except SQLAlchemyError`
englobant (remonte donc bien à travers `get_session()`, qui rollback puis relance), et que le
`finally` de `_handle_fetch_request` relâche toujours le verrou même si l'erreur survient au
milieu de la boucle de drain. Deux tests ajoutés (`test_raises_value_error_when_signal_row_missing`
sur chacune des deux fonctions) ; les deux tests existants de `TestDrainPendingSignal` adaptés
pour la nouvelle requête d'existence en tête (`side_effect` à trois éléments au lieu de deux).

**Vérification :** `pytest JobFinder/python` (297/297, +2 tests) ; `reviewer-backend` APPROUVÉ
sur ce suivi, aucune remarque non-bloquante restante après la factorisation du message d'erreur.
Limite acceptée, signalée par le reviewer et non corrigée (hors du scope réaliste du problème) :
la vérification d'existence et l'`UPDATE` gardé dans `_drain_pending_signal` sont deux requêtes
séparées sans `FOR UPDATE` — une suppression concurrente de la ligne singleton atterrissant
exactement entre les deux resterait un angle mort théorique.

## PR #216 — feat(cv-analysis): extraction ROME sensible à l'intention déclarée + bouton de ré-analyse manuel

**Date :** 2026-07-22
**Branche :** `feature/cv-analysis-rome-intent-aware-and-reanalysis` → `dev`

### Contexte

Suite d'un échange avec Vincent (22/07, `prompt-cv-analysis-rome-reanalysis-button.md`) sur un
cas concret : un CV mêlant plusieurs expériences clairement disjointes (formation/objectif
développeur, plus des jobs alimentaires/saisonniers sans lien — serveur, manutention, coaching
sportif). Deux lacunes réelles dans `_extract_rome_codes`, distinctes du travail déjà fait en
PR #213 : (1) le prompt système interdisait la confusion secteur/métier mais ne disait rien sur
la priorisation quand plusieurs métiers réellement exercés cohabitent dans le même CV — serveur/
manutention/coaching sont de vrais métiers exercés, la règle existante ne les exclut donc pas ;
(2) la fonction ne recevait jamais `UserProfile.candidate_description` (l'intention déclarée sur
la plateforme), déjà utilisée ailleurs (`_analyze_cv_quality`, l'embedding d'intention côté
matching) mais jamais pour guider l'extraction ROME elle-même.

### Ce qui a été fait

`ROME_EXTRACTION_SYSTEM_PROMPT` : nouvelle règle de priorisation — un objectif de poste explicite
(intitulé en tête de CV ou intention transmise séparément) l'emporte sur des expériences annexes
disjointes ; un job alimentaire/saisonnier sans lien avec la direction de carrière ne doit plus
être représenté à égalité avec l'objectif réel. `_extract_rome_codes` accepte désormais
`candidate_description: str | None = None` et l'ajoute au message utilisateur quand elle est non
vide (même garde que `_build_intent_text`/`intent_text` ailleurs dans ce fichier).

`_merge_rome_codes` corrigé d'une limite documentée deux fois auparavant (JOURNAL, PR #213, fix
du shallow copy) : elle ne faisait qu'ajouter, jamais retirer un code devenu obsolète pour un
`cv_id` donné. Elle réconcilie maintenant — retire ce `cv_id` de tout code que l'extraction
fraîche ne produit plus, purge le code entièrement si sa liste de `cv_ids` devient vide — sur le
modèle de l'idiome déjà utilisé par `routers/cv.py::_remove_cv_from_rome_codes` à la suppression
d'un CV.

Nouvelle colonne `cvs.rome_analyzed_at` (migration `031_add_rome_reanalysis_tracking.py`),
stampée par la nouvelle fonction `_mark_rome_analyzed` (calquée sur `_set_cv_status`) chaque fois
qu'une extraction ROME complète — chemin d'upload normal et nouveau chemin de retry. Nouvelle
colonne `user_profiles.description_updated_at`, stampée dans `routers/profile.py::put_profile`
uniquement quand `candidate_description` change réellement (pas sur un PUT qui ne touche que
`experience_level`, ni sur une valeur identique) — distincte de `updated_at`, que
`_merge_rome_codes` touche aussi sur chaque analyse CV et qui est donc inutilisable comme signal
de "la description a-t-elle changé".

Gestion du changement d'intention après coup : bouton de ré-analyse manuel par CV plutôt qu'une
ré-analyse automatique en masse (coût de contrôle, transparence) ou un statu quo silencieux.
`GET /cv/` expose `rome_reanalysis_available` (calculé depuis `profile.description_updated_at` vs
`cv.rome_analyzed_at`, `profile` déjà chargé pour `zone_condition` — pas de requête
supplémentaire). Nouvel endpoint `POST /cv/{id}/rome/retry`, sur le modèle de
`POST /cv/{id}/analysis/retry`, qui publie `{"cv_id": ..., "retry_rome_only": True}` sur
`cv-analysis`. Nouvelle branche `main()` + fonction `_handle_retry_rome_only` (sur le modèle de
`_handle_retry_quality_only`, refactorée en PR #215) : ré-extrait les codes ROME avec l'intention
courante, réconcilie, stampe `rome_analyzed_at`, puis redispatche `start-matching` (trigger
`cv_analysis_rome_retry`, pour distinguer ce déclencheur en télémétrie) et `offer-fetch-request`
best-effort sur les codes réellement nouveaux — `_dispatch_start_matching` prend maintenant un
paramètre `trigger` pour ça. Contrairement au chemin d'upload normal, un échec de ré-extraction
ne fait pas basculer le CV en `status="error"` : le CV a déjà terminé son analyse initiale avec
succès, et le repasser en erreur masquerait le CV fonctionnel et ses correspondances existantes
derrière un état d'erreur au lieu de simplement laisser le bouton disponible pour un nouvel essai.

Frontend : nouveau composant `RomeReanalysisButton.tsx` (bulle d'explication au survol du bouton
lui-même, demandée explicitement par Vincent — pas un icône "?" séparé comme `InfoTooltip`), sur
le modèle du bouton de retry de `CvAnalysisCard.tsx`. Rendu dans `CVDetailSection.tsx`,
conditionné sur `currentCv?.rome_reanalysis_available`, avec un nouveau prop `onRomeReanalyzed`
branché dans `HomeClient.tsx` sur le même mécanisme de refetch (`libraryRefreshTrigger`) que
`onMatchSeen` — pas de nouveau mécanisme de rafraîchissement inventé.

### Décisions techniques

Pas de backfill sur la migration : les deux colonnes démarrent à `NULL` pour tous les
profils/CV existants, ce qui désactive naturellement le bouton pour tout le monde jusqu'au
premier changement de `candidate_description` après ce déploiement — comportement correct par
construction.

Pas d'index sur `description_updated_at` ni `rome_analyzed_at` : les deux colonnes ne sont
jamais lues que comme comparaison sur une ligne déjà chargée par clé primaire (`GET /cv/`, sur
un profil/CV déjà récupéré pour `zone_condition`) — jamais filtrées ni jointes en SQL — un
index apporterait un coût d'écriture sans requête à accélérer.

Ripples de test repérés en cours de relecture, au-delà de la liste du prompt d'origine (qui ne
couvrait que les nouveaux tests) : `TestListCvs` construisait des `CV`/`UserProfile` mockés sans
`rome_analyzed_at`/`description_updated_at` explicites — deux `MagicMock` par défaut comparés par
`>` lèvent `TypeError` (`__gt__` renvoie `NotImplemented` des deux côtés), ce qui aurait fait
planter ces quatre tests existants en 500 dès l'ajout de la comparaison dans `list_cvs`. Corrigé
en fixant `cv.rome_analyzed_at = None` sur chacun. `TestMainOfferFetchDispatch` ne mockait ni
`_get_profile_intent` ni `_mark_rome_analyzed`, désormais appelées par `_handle_new_cv_analysis`
— les trois tests auraient tenté une vraie connexion DB. Et `CVData.rome_reanalysis_available`
étant un champ obligatoire (pas de `?`), chaque littéral `CVData` existant dans les tests
frontend (`CVCard.test.tsx`, `CVDetailSection.test.tsx`, `LibrarySection.test.tsx`) devait le
recevoir pour rester valide au typecheck.

### Tests

Backend : `TestExtractRomeCodes` (présence/absence de l'intention dans le message utilisateur,
y compris chaîne vide/espaces) ; `TestMergeRomeCodes` (retrait d'un code devenu obsolète pour ce
`cv_id`, non-retrait quand un autre `cv_id` partage encore le code) ; `TestMarkRomeAnalyzed` ;
`TestMainRetryRomeOnly` (branche `retry_rome_only` isolée de la branche qualité, trigger
`cv_analysis_rome_retry` sur `start-matching`, dispatch conditionnel d'`offer-fetch-request`) ;
`TestListCvsRomeReanalysisAvailable` (les trois cas — pas de profil, `description_updated_at`
`None`, avant/après `rome_analyzed_at`) ; `TestRetryRomeAnalysis` (dispatch, 404, 500). Profile :
trois tests sur le stamping conditionnel de `description_updated_at`. Frontend :
`RomeReanalysisButton.test.tsx` (rendu, tooltip au survol **et** au focus clavier, association
`aria-describedby`, appel POST, état d'erreur) et deux tests ajoutés à `CVDetailSection.test.tsx`
(rendu conditionnel, branchement `onRomeReanalyzed`).

**Vérification :** `pytest JobFinder/python` (321/321) ; `npm test` (15 suites, 147 tests) et
`npx tsc --noEmit` propres côté frontend. Test manuel décisif (CV multi-métiers avec/sans
intention déclarée, disparition du bouton après ré-analyse réussie) non exécuté dans cette
session — nécessite l'infra Azure/OpenAI/DB réelle, indisponible ici ; à faire avant merge.

### Limites connues (acceptées, non corrigées dans cette PR)

`_merge_rome_codes` et `_mark_rome_analyzed` (comme, déjà avant cette PR, `_merge_rome_codes` et
`_set_cv_status`) s'exécutent dans deux transactions/sessions DB séparées — remarque non-bloquante
de `reviewer-backend`. Un crash exactement entre les deux laisserait `rome_analyzed_at` non
rafraîchi alors que la fusion des codes a déjà eu lieu, ce qui garderait
`rome_reanalysis_available` à `True` alors que ce n'est plus nécessaire. Effet borné à un bouton
qui reste affiché à tort jusqu'au prochain déclenchement réussi — pas de corruption de données, le
comportement est auto-cicatrisant. Accepté tel quel : c'est un pattern préexistant que cette PR
étend plutôt qu'elle n'introduit, et unifier les deux écritures dans une seule session toucherait
aussi le chemin d'upload normal — hors périmètre de cette PR.

## PR #217 — fix(cv-analysis): référentiel ROME dans le prompt, extraction PDF par colonnes, gpt-5-mini

**Date :** 2026-07-22
**Branche :** `feat/cv-analysis-referentiel-model-upgrade-column-parsing` → `dev`

### Contexte

Signalement d'un CV réel (Nicolas Pasqualini, dessinateur-projeteur BTP) classé sous des codes
ROME informatique (`M1802`/`M1805`), puis, une fois le modèle changé, sous des codes tout aussi
faux (taxidermiste `B1701`/`B1702`). Diagnostic mené en amont de cette session (voir
`prompt-cv-analysis-referentiel-model-upgrade-column-parsing.md`, non versionné dans ce repo —
même convention que les autres `docs/prompts/*.md` déjà référencés dans le code) : l'ordre du
texte n'était pas la cause (un texte reconstitué à la main donnait des résultats tout aussi faux) ;
la cause racine était que `_extract_rome_codes` demandait un code ROME de mémoire, sans jamais
montrer au modèle les ~1911 entrées valides — un pur exercice de rappel fermé sur un espace
arbitraire. Injecter le référentiel complet dans le prompt système fait retomber `gpt-4o-mini` sur
`F1104` (le bon code) de façon stable. Cause secondaire distincte : `pdfplumber.extract_text()` ne
gère pas la mise en page à deux colonnes de ce CV (bandeau latéral + bloc principal), entrelaçant
les deux blocs dans `raw_text` — corrigé séparément par une extraction consciente des colonnes.

### Ce qui a été fait

**Référentiel dans le prompt ROME.** `ROME_EXTRACTION_SYSTEM_PROMPT` (`agents/cv_analysis/main.py`)
construit désormais dynamiquement à partir de `ROME_REFERENTIEL` (`code: label` par ligne, ~1911
entrées) — le référentiel guide maintenant la génération, plus seulement le filtrage anti-
hallucination a posteriori. Toujours dans le prompt système (pas le message utilisateur), pour
rester éligible au cache de prompt. Nouvelle RÈGLE — niveau de qualification (n'jamais retourner un
code d'un niveau de responsabilité supérieur à l'expérience réellement démontrée), en défense en
profondeur du défaut de sur-génération observé sur `gpt-4o-mini` pendant le diagnostic.

**Date du jour dans les deux prompts.** `_extract_rome_codes` et `_analyze_cv_quality` préfixent
maintenant leur message utilisateur de `Date du jour : {isoformat}` (jamais le prompt système, même
rationale de cache) — corrige un bug constaté en diagnostic où l'analyse qualité qualifiait une
date de 08/2024 de "futuriste" faute d'ancrage réel sur le jour présent.

**Extraction PDF consciente des colonnes** (`agents/webapp/routers/cv.py`). Nouvelles fonctions
`_group_words_into_rows`, `_words_to_lines`, `_gap_row_coverage`, `_detect_column_gap`,
`_extract_page_text` : détecte une bande verticale vide séparant deux colonnes (largeur minimale
`_MIN_COLUMN_GAP_WIDTH=14pt`, couverture minimale `_MIN_GAP_ROW_COVERAGE=0.6` des lignes de texte —
pas de la hauteur totale de page, pour tolérer un en-tête pleine largeur sans perdre la détection,
et pour rejeter une simple liste à puces indentée qui ne dégage cette bande que sur une minorité de
lignes). Repli strict sur `page.extract_text()` (comportement inchangé, byte-identique) dès qu'aucun
mot n'est trouvé ou qu'aucune bande candidate ne satisfait les deux seuils — cas dominant (CV à une
seule colonne). `upload_cv` appelle `_extract_page_text` par page, agrège `raw_text` (join `"\n"`,
inchangé) et le nombre max de colonnes détecté sur le document ; loggé dans
`cv_upload_text_extracted` (`columns_detected=<n>`) et persisté sur `cvs.layout_columns_detected`
(migration `032`, `SmallInteger` nullable — `NULL` = non calculé, pas de backfill, même rationale
que `rome_analyzed_at` en migration `031`). 3+ colonnes / mise en page en grille explicitement hors
périmètre : repli sur le comportement à une colonne plutôt qu'un résultat faux silencieux.

**Signal colonnes → analyse qualité.** `_get_cv_text` sélectionne désormais aussi
`CV.layout_columns_detected` (retourne un 3-tuple — tous les appelants mis à jour) et le transmet
via `_run_quality_analysis` jusqu'à `_analyze_cv_quality`, qui préfixe le message utilisateur de
`Mise en page détectée : {n} colonnes.` si `n >= 2`. Nouvelle RÈGLE dans
`CV_QUALITY_SYSTEM_PROMPT` : ce signal ne doit jamais servir à inventer une désorganisation de
contenu (le texte reçu est déjà remis en ordre de lecture) mais doit être mentionné comme un vrai
risque ATS dans `points_faibles`/`suggestions` — décision actée avec Vincent en amont : un score
ATS bas à cause d'une mise en page à colonnes n'est pas injuste en soi (de vrais logiciels ATS
gèrent mal les CV à colonnes), le problème était seulement que les critiques de contenu générées à
partir d'un texte désordonné étaient fausses une fois le texte bien extrait.

**Changement de modèle : gpt-4o-mini → gpt-5-mini, avec gestion conditionnelle temperature/seed.**
`gpt-5-mini` rejette `temperature`/`seed` fixés (`400 Bad Request` direct, confirmé en diagnostic) —
`MODELS_WITHOUT_TEMPERATURE_SEED` (frozenset) + `_sampling_kwargs()` (nouveau helper,
`agents/cv_analysis/main.py`) retournent un dict vide pour ces déploiements plutôt que d'envoyer
`temperature=0.0` et casser l'appel. `AZURE_OPENAI_CV_ANALYSIS_DEPLOYMENT` bascule par défaut sur
`"gpt-5-mini"`. Le déploiement Azure `gpt-5-mini` existait déjà (créé manuellement dans le portail
par Vincent pour les tests) — importé dans l'état Terraform plutôt que laissé à `apply` pour le
recréer (`terraform import` exécuté en session, resource address
`module.openai.azurerm_cognitive_deployment.this["gpt-5-mini"]`, confirmé absent de l'état avant
import). Nouvelle entrée dans la map `deployments` de `Terraform/envs/dev/openai.tf`
(`model_version = "2025-08-07"`, `sku_name = "GlobalStandard"`, `capacity_tpm` sur la variable
partagée `var.openai_capacity_tpm` — pas de quota dédié, confirmé avec Vincent). `container_apps.tf`
ligne 386 (`AZURE_OPENAI_CV_ANALYSIS_DEPLOYMENT`) bascule sur `"gpt-5-mini"` ; ligne 456
(`AZURE_OPENAI_MATCH_ANALYSIS_DEPLOYMENT`, agent différent) volontairement inchangée.

### Décisions techniques

Le déploiement manuel existant avait `sku.capacity = 100`, pas `1000` (la valeur de
`var.openai_capacity_tpm`) — `terraform plan` après import montre donc un vrai changement de quota
(100k → 1M TPM) sur ce déploiement au prochain `apply`, pas seulement une prise en compte passive
de l'existant. Confirmé volontairement avec Vincent plutôt que découvert silencieusement en CI.
Vérifié via `az cognitiveservices usage list --location francecentral` : le quota souscription pour
`OpenAI.GlobalStandard.gpt-5-mini` est de 2000 (2M TPM), usage courant 100 — la hausse à 1000 reste
largement sous le plafond, pas de risque d'échec d'`apply` par dépassement de quota.

État Terraform et configuration divergent tant que cette PR n'est pas mergée : le `terraform
import` exécuté en session a déjà ajouté `module.openai.azurerm_cognitive_deployment.this["gpt-5-
mini"]` à l'état distant partagé, mais seule cette branche déclare la ressource correspondante dans
`openai.tf`. Un `apply` sur `dev` déclenché par une autre PR avant que #217 ne merge planifierait la
destruction de ce déploiement (l'état le connaît, la config sur `dev` ne le déclare pas encore) —
contrainte d'ordre de merge : #217 doit être la prochaine PR appliquée sur `dev` touchant cette
zone, ou l'import doit être annulé (`terraform state rm`) si cette PR est abandonnée.

`_get_cv_text` retourne désormais `(raw_text, user_id, layout_columns_detected)` — un 3-tuple, pas
un `None` par défaut sur `columns_detected` dans `_analyze_cv_quality` : un défaut silencieux
aurait masqué une rupture du fil de transmission (upload → DB → `_get_cv_text` →
`_run_quality_analysis` → `_analyze_cv_quality`) au lieu de la faire échouer bruyamment à l'appel.

Pas de fixture PDF réelle pour les tests de détection de colonnes : aucune bibliothèque de
génération PDF n'existe dans ce repo (confirmé par recherche), et le chemin heureux de
`POST /cv/upload` est déjà explicitement exclu des tests unitaires dans ce fichier de tests (trop
de mocks simultanés — pdfplumber, `embed()`, blob, `send_message` — testé manuellement en
intégration à la place). Les fonctions pures (`_detect_column_gap`, `_words_to_lines`,
`_extract_page_text`) sont testées directement contre des dicts `pdfplumber`-compatibles construits
à la main. Ces tests valident l'algorithme de séparation/reconstitution contre un schéma de
coordonnées connu — ils ne prouvent rien sur le fait qu'un vrai PDF à deux colonnes produise des
coordonnées que les seuils (`_MIN_COLUMN_GAP_WIDTH=14`, `_MIN_GAP_ROW_COVERAGE=0.6`) séparent
correctement. Ces deux constantes sont documentées comme provisoires dans le code — à recalibrer
via le champ `columns_detected` loggé, observé sur un échantillon réel après déploiement.

### Tests

`test_cv_analysis.py` : `TestSamplingKwargs` (dict vide vs `{temperature, seed}` selon le
déploiement configuré) ; `TestRomeExtractionSystemPrompt` (`"F1104:"` présent dans le prompt
construit, interdiction d'inventer un code) ; date du jour dans le message utilisateur
(`_extract_rome_codes` et `_analyze_cv_quality`) ; `layout_note` présent seulement si
`columns_detected >= 2` (paramétré sur `None`/`0`/`1` vs `2`/`3`) ; `TestGetCvText` étendu au
3-tuple, y compris le cas `layout_columns_detected IS NULL` (CV pré-migration) ;
`TestRunQualityAnalysis` vérifie explicitement que `columns_detected` est transmis inchangé
jusqu'à `_analyze_cv_quality` (pas seulement que l'appel a lieu). `tests/conftest.py` fixe
`AZURE_OPENAI_CV_ANALYSIS_DEPLOYMENT=gpt-4o-mini` pour que les assertions de déterminisme
existantes restent valables sans que chaque test doive patcher la variable — le nouveau défaut du
module est `gpt-5-mini`, pour lequel `_sampling_kwargs()` renvoie volontairement un dict vide.

`test_webapp_cv.py` : nouvelle section dédiée (`TestGroupWordsIntoRows`, `TestWordsToLines`,
`TestDetectColumnGap`, `TestExtractPageText`) — non-régression stricte (byte-identique) sur le cas
à une seule colonne ; rejet d'un faux positif (liste à puces indentée sur une minorité de lignes) ;
détection correcte sur un vrai cas à deux colonnes avec un en-tête pleine largeur qui ne doit pas
empêcher la détection ; le mot pleine largeur est assigné à un seul côté sans être perdu ni dupliqué
(`test_full_width_word_lands_on_one_side_without_being_dropped_or_duplicated`, exerce
explicitement la branche `straddling` de `_extract_page_text`, pas seulement `_detect_column_gap`).

Migration `032` : `alembic history` confirme la chaîne `031 → 032` sans exécuter d'`upgrade`/
`downgrade` réel (pas de Postgres local disponible en session — voir Vérification).

**Vérification :** `pytest JobFinder/python` (348/348, suite complète y compris
`agents/cleanup/tests`, pour couvrir le changement global sur `conftest.py`) ; `terraform fmt
-check`, `terraform validate`, et un `terraform plan` ciblé confirmant exactement les deux diffs
attendus (env var du job `cv-analysis`, capacité du déploiement `gpt-5-mini`) sans effet de bord
sur le reste de l'état. **Non exécuté dans cette session, à faire avant merge** : `alembic upgrade
head` / `downgrade -1` sur une vraie base (pas de Postgres local ici) ; ré-exécution sur le CV réel
de Nicolas Pasqualini pour confirmer la convergence stable sur `F1104` ; observation du champ
`columns_detected` sur un échantillon d'uploads réels variés pour ajuster les seuils si des faux
positifs apparaissent en production.

### Limites connues (acceptées, non corrigées dans cette PR)

Le référentiel complet (~22-24k tokens) plus le CV (jusqu'à 8000 caractères) sont envoyés à chaque
appel `_extract_rome_codes` — bien en dessous de toute fenêtre de contexte de déploiement Azure
OpenAI moderne, mais la fenêtre exacte du déploiement `gpt-5-mini` n'a pas été vérifiée dans cette
session (pas d'accès à la documentation Azure à jour) ; à confirmer avant merge plutôt qu'affirmée
sans preuve.

`_MIN_COLUMN_GAP_WIDTH` et `_MIN_GAP_ROW_COVERAGE` sont des valeurs provisoires calibrées contre
des layouts synthétiques, pas contre de vrais CV à colonnes — voir Décisions techniques.

## PR #218 — fix: trois bugs indépendants post-#217 — colonnes CV, verrou Service Bus, chargement matchs

**Date :** 2026-07-23
**Branche :** `fix/cv-column-detection-servicebus-lock-loading-feedback` → `dev`

### Contexte

Trois bugs distincts, sans lien de cause entre eux, découverts après le déploiement de #217 (extraction
PDF par colonnes + gpt-5-mini). Regroupés sur une seule branche parce qu'ils ont été corrigés dans la même
session, pas parce qu'ils partagent une racine commune — chaque section ci-dessous est un correctif à part
entière.

### Ce qui a été fait

**Bug 1 — faux positif de colonne sur un CV mono-colonne à lignes inégales**
(`agents/webapp/routers/cv.py`). Un CV à une seule colonne dont les lignes ont des longueurs très inégales
(courtes lignes de badges de compétences à côté de longues puces d'expérience) pouvait laisser une marge
blanche large d'un seul côté qu'aucune ligne ne traverse jamais — `_detect_column_gap` la prenait alors
pour une véritable gouttière de colonnes, déchirant un mot isolé (bannière pleine largeur) en une fausse
deuxième colonne. Nouvelle constante `_MIN_GAP_BILATERAL_ROWS = 0.3` et nouvelle fonction
`_gap_has_bilateral_content()` : exige qu'une fraction minimale des lignes aient du contenu réel des deux
côtés du gap candidat (pas seulement l'absence de mot qui le traverse, ce que `_gap_row_coverage` vérifiait
déjà) — troisième condition ajoutée dans la boucle de `_detect_column_gap`, en plus de la largeur minimale
et de la couverture par ligne existantes. Docstrings de `_detect_column_gap` et des deux constantes mises à
jour pour documenter ce troisième critère.

**Bug 2 — perte de verrou Service Bus sur un traitement long** (`shared/bus.py`). Aucun renouvellement de
verrou n'était en place : tout traitement plus lent que le `lock_duration` par défaut de la queue
(~60s, jamais surchargé) faisait échouer `complete_message`/`abandon_message` avec `MessageLockLostError`
alors que le travail métier avait déjà été validé (commit DB, etc.) — devenu courant depuis #217 avec
gpt-5-mini et le référentiel ROME complet injecté dans le prompt de `cv-analysis`. `receive_message()`
enregistre désormais un `AutoLockRenewer` (nouvelle constante `MAX_LOCK_RENEWAL_DURATION_SECONDS = 900`,
15 min, généreuse par rapport à la durée réelle observée) sur le message reçu, et ferme le renewer dans un
bloc `finally`. `MessageLockLostError` est capturée séparément autour de `complete_message` (loggée en
`warning`, jamais re-levée — le travail a déjà réussi, ce n'est qu'une perte de bookkeeping côté
accusé-réception) et autour de `abandon_message` dans le chemin d'exception (loggée de la même façon), mais
l'exception métier d'origine est toujours re-levée dans ce second cas — une vraie erreur de traitement doit
toujours remonter comme échec de job. Docstring de `receive_message` étendue pour documenter les deux
chemins de tolérance et le `finally`.

**Bug 3 — état de chargement des matchs découplé du statut réel de traitement du CV**
(`app/_components/CVDetailSection.tsx`). La liste de correspondances affichait « Aucune offre ne
correspond » alors que l'analyse/le matching du CV était encore en cours côté serveur, parce que le
booléen `loading` transmis à `CorrespondancesPanel`/`MatchList` ne reflétait que « la requête HTTP est en
vol », jamais « le back-end a fini son travail ». Nouveau booléen dérivé `isAnalysisInProgress`
(`currentCv.status !== "matched" && currentCv.status !== "error"`), combiné par `||` avec
`loadingMatches` existant avant transmission à `CorrespondancesPanel`. Calculé au rendu (pas dans un effet
séparé) pour se recalculer à chaque changement de `currentCv.status` sans déclencher le hard reset du
`useEffect` de fetch des matchs (qui ne réagit qu'à `selectedCvId`/`zoneVersion`, volontairement inchangé).

### Décisions techniques

`_MIN_GAP_BILATERAL_ROWS = 0.3` est, comme `_MIN_COLUMN_GAP_WIDTH` et `_MIN_GAP_ROW_COVERAGE` avant lui, une
valeur provisoire calibrée contre des layouts synthétiques construits à la main, pas contre un corpus de
vrais CV — même réserve que celle déjà actée dans #217, à recalibrer via `columns_detected` une fois
observé en production.

`MAX_LOCK_RENEWAL_DURATION_SECONDS = 900` a été choisie généreuse plutôt qu'ajustée au plus près de la
durée réelle observée d'un traitement `cv-analysis` : le but explicite est que le verrou ne soit jamais le
facteur limitant en usage normal, pas d'optimiser la valeur.

**`lib/api/types.ts` n'a volontairement pas été modifié**, alors que le prompt d'origine le demandait.
`CVStatus` (ligne 1) inclut déjà `"matched"` et `"error"` — c'est bien ce champ que lit
`isAnalysisInProgress` sur `currentCv.status`. Les deux unions littérales qui ne les incluent pas,
`CvAnalysisOut.status` (~ligne 62) et `MatchAnalysisOut.status` (~ligne 78), sont un champ différent et
sans rapport (progression d'une analyse individuelle CV ou paire CV↔offre, pas le statut du CV lui-même) —
confirmé en relisant `agents/webapp/routers/cv.py` et `agents/matching/main.py` : le back-end n'écrit
jamais `"matched"` sur ces colonnes, seulement sur `CV.status` (`agents/matching/main.py`, la fonction qui
fait avancer les CV de `"done"` à `"matched"` une fois qu'au moins un cycle de matching les a considérés).
Ajouter `"matched"` à ces deux unions inventerait un état inatteignable ; ne pas « corriger » ce fichier
dans une passe ultérieure sans revérifier ce raisonnement.

**Vérification :** Suite de tests non ré-exécutée dans cette session de revue documentaire (accès limité
en lecture/écriture de fichiers, pas d'exécution shell). Couverture attendue par les tests déjà présents
sur la branche : `test_webapp_cv.py` — `TestGapHasBilateralContent` (4 cas : tout bilatéral, tout d'un seul
côté — régression bug 1 —, rows vides, seuil exact 0.3) et non-régression bout-en-bout dans
`TestDetectColumnGap`/`TestExtractPageText` (`test_rejects_gap_from_uneven_line_lengths_in_single_column_cv`,
`test_falls_back_to_single_column_for_uneven_line_lengths`) ; `test_bus.py` — nouvelle classe
`TestReceiveMessage` (enregistrement de l'`AutoLockRenewer`, complétion + fermeture du renewer au succès,
tolérance à `MessageLockLostError` sur `complete_message` et sur `abandon_message`, ré-lèvement systématique
de l'exception métier d'origine, non-enregistrement du renewer quand la queue est vide) ;
`CVDetailSection.test.tsx` — nouveau describe « état de chargement du matching (bug 3) » (skeleton maintenu
pour `pending`/`processing`/`done` même liste vide reçue, affichage de l'état vide dès `matched` ou
`error`, transition sans remount via `rerender`). À ré-exécuter (`pytest`, `jest`) avant merge.

---

## PR #219 — feat(infra): raise max_executions for cv-analysis and match-analysis jobs

**Date :** 2026-07-23
**Branche :** `feature/tune-cv-match-analysis-max-executions` → `dev`

### Contexte

Réglage de parallélisme pur, sans lien de cause avec #218 (qui a corrigé un bug de verrou Service Bus sur
`cv-analysis`, entre autres) — les deux touchent le même job par coïncidence de calendrier, pas par
dépendance. `job_cv_analysis` et `job_match_analysis` tournaient tous deux avec le défaut du module
`container_app_job` (`max_executions = 1`, aucun parallélisme). `cv-analysis` est devenu nettement plus
lent par message depuis #217 (gpt-5-mini + référentiel ROME complet injecté dans le prompt) ; `match-analysis`
a des caractéristiques de queue qui bénéficient d'un plus grand nombre de réplicas en parallèle.

### Ce qui a été fait

- `envs/dev/container_apps.tf` : `module.job_cv_analysis` → `max_executions = 2`.
- `envs/dev/container_apps.tf` : `module.job_match_analysis` → `max_executions = 8`.

Aucune autre ligne touchée — changement volontairement minimal et scopé.

### Décisions techniques

`max_executions = 2` pour cv-analysis compense le ralentissement par message observé depuis #217
(gpt-5-mini + référentiel ROME complet injecté dans le prompt) par un parallélisme modeste — un premier
palier au-dessus du défaut de 1, pas une valeur recalculée à partir d'une charge cible précise.
`max_executions = 8` pour match-analysis est plus généreux, cohérent avec les caractéristiques de sa queue.
Les deux valeurs restent des réglages empiriques (comme `MATCHING_SCORE_THRESHOLD` en #122) — à ajuster à
l'usage réel plutôt que recalculées analytiquement.

**Vérification :** `terraform plan` non exécuté dans cette session de revue documentaire (pas d'accès Bash) ;
passera par le plan CI standard (`terraformPlan.yml`) sur la PR — diff attendu : deux valeurs modifiées
uniquement (`max_executions` sur `job_cv_analysis` et `job_match_analysis`), aucune ressource recréée.

---

## PR #220 — feat(cv-analysis,match-analysis): logging des tokens consommés par appel Azure OpenAI

**Date :** 2026-07-24
**Branche :** `feature/openai-cost-instrumentation` → `dev`

### Contexte

Prépare une section « Coûts » dans le dashboard Grafana produit (Offres / CV / Utilisateurs / Coûts).
Aucun appel `chat.completions.create` ne capturait `response.usage` jusqu'ici — impossible de savoir
combien coûte une analyse CV ou une analyse de matching. Cette PR ajoute uniquement le logging des tokens
consommés ; le calcul du coût en euros se fera côté requête KQL dans Grafana (prix au token en variable de
dashboard, pas en dur dans le code — un changement de tarif Azure OpenAI ne doit pas nécessiter de
redéploiement). `cv_analysis` (extraction ROME + analyse qualité) tourne sur gpt-5-mini,
`match_analysis` sur gpt-4o-mini — deux modèles, deux prix au token distincts, d'où la présence du champ
`model` sur chaque event (pas seulement `agent`/`operation`), au cas où le déploiement change sans que le
nom d'`operation` change.

### Ce qui a été fait

Nouvel event structlog `openai_call_completed` sur les trois sites d'appel `chat.completions.create` +
le site d'appel `embeddings.create` du module partagé :

- `agents/cv_analysis/main.py` — `_extract_rome_codes` (`operation="rome_extraction"`) et
  `_analyze_cv_quality` (`operation="cv_quality_analysis"`), toutes deux sur
  `AZURE_OPENAI_CV_ANALYSIS_DEPLOYMENT`, `agent="cv-analysis"`.
- `agents/match_analysis/main.py` — `_analyze_match` (`operation="match_analysis"`), sur
  `AZURE_OPENAI_MATCH_ANALYSIS_DEPLOYMENT`, `agent="match-analysis"`.
- `shared/embedder.py` — `embed()` (`operation="embedding"`), sur `text-embedding-3-small`, une fois par
  batch de 100 textes (pas une seule fois agrégée en fin de fonction : chaque appel `embeddings.create` du
  batch consomme ses propres tokens).

Les trois sites `chat.completions.create` sont dans des boucles de retry (`MAX_ATTEMPTS`) : un
`JSONDecodeError`/`KeyError`/`ValueError` sur `response.choices[0].message.content` se produit **après**
que l'appel API a réussi et consommé des tokens. Le nouvel event est donc émis juste après l'appel
`create(...)`, avant `json.loads(...)` — sur chaque tentative qui a obtenu une réponse, pas seulement sur
le chemin de succès, pour ne pas sous-compter le coût des retries ratés au parsing.

Champs vérifiés contre le SDK `openai` réellement installé (2.44.0, non pinné dans `requirements.txt`) :
`response.usage.prompt_tokens` / `.completion_tokens` / `.total_tokens` (chat) et `.prompt_tokens` /
`.total_tokens` sans `.completion_tokens` (embeddings — absent du modèle Pydantic `Usage` du SDK, pas
seulement `None` en pratique) : le champ est donc omis de l'event plutôt que loggé comme `None`.

Tests étendus dans `tests/test_cv_analysis.py` et `tests/test_match_analysis.py` : usage mocké sur
`response.usage`, vérification que `openai_call_completed` est loggé avec les bons champs, y compris sur
la tentative dont le parsing JSON échoue avant le retry réussi (les deux appels doivent chacun logger leur
propre usage, avec le bon `attempt`).

### Décisions techniques

`shared/embedder.py` n'a volontairement pas reçu de champ `agent=` sur son event, à la différence des
trois sites `chat.completions.create`. Ce module est partagé par plusieurs services sans
`configure_telemetry()` propre (`agents/webapp/routers/profile.py`, `agents/webapp/routers/cv.py`,
`agents/offer_fetching/main.py` l'appellent tous), donc il n'existe pas une valeur `agent` unique à
coder en dur ici comme c'est le cas pour `cv-analysis`/`match-analysis`. Faire remonter l'appelant
réel aurait exigé de faire transiter un paramètre à travers ces trois call sites, hors du périmètre de
cette tâche (portée explicitement limitée à `agents/cv_analysis/`, `agents/match_analysis/`, et
`shared/embedder.py`). L'attribution par service reste disponible sans ce champ : `configure_telemetry()`
exporte déjà `service.name` comme attribut de ressource OpenTelemetry, exploitable côté Application
Insights via `cloud_RoleName` sur chaque ligne de log. Le champ `model` (`text-embedding-3-small`, un seul
modèle donc un seul prix au token quel que soit l'appelant) reste le champ discriminant utile pour la
requête KQL de coût côté Grafana.

Pas de fichier de test dédié créé pour `shared/embedder.py` — aucun test unitaire n'existait déjà pour ce
module (les tests de `agents/webapp` qui l'utilisent mockent `embed()` dans son ensemble, sans tester son
implémentation interne), et l'ajout du logging n'y change pas le contrat public de la fonction.

**Vérification :** `pytest` exécuté sur l'ensemble de la suite (366 tests, tous passants) après les
modifications, y compris les nouveaux tests d'assertion sur `openai_call_completed`.

---

## PR #221 — feat(frontend): instrumentation PostHog du funnel utilisateur

**Date :** 2026-07-24
**Branche :** `feature/posthog-integration` → `dev`

### Contexte

Suite au plan PostHog conçu avec Claude Cowork : les logs backend (AppTraces) ne loggent pas `user_id`
sur `cv_analysis_started`/`match_analysis_started`, alors que le contexte utilisateur est déjà disponible
côté frontend au moment du clic. Cette PR instrumente le frontend Next.js avec PostHog Cloud EU
(organisation `vbo-cloud`, projet 231604) pour obtenir le funnel utilisateur complet — upload CV → analyse
consultée → matches consultés → analyse de matching demandée → crédit consommé/épuisé → profil complété.

Portée entièrement frontend (`JobFinder/frontend/`) sauf la propagation des variables d'environnement
`NEXT_PUBLIC_POSTHOG_*` jusqu'au build de l'image Docker.

### Ce qui a été fait

- `npm install posthog-js` (1.407.2).
- `app/Providers.tsx` (nouveau — PascalCase, `reviewer-frontend` a bloqué un premier `providers.tsx` en
  minuscule) : `PostHogProvider`, `posthog.init()` dans un `useEffect`, `defaults: "2026-05-30"`. Pas de
  composant `PostHogPageView` manuel — vérifié dans le bundle installé
  (`node_modules/posthog-js/dist/module.js`) que ce preset fixe déjà `capture_pageview: "history_change"`,
  qui autocapture le `$pageview` sur navigation App Router ; un capture manuel en plus aurait doublé
  l'event à chaque changement de route.
- `app/layout.tsx` : `PostHogProvider` englobe `AuthProvider` (Server Component parent inchangé, le
  nouveau wrapper est lui-même un client component).
- 8 events instrumentés :
  - `user_logged_in` + `identify(homeAccountId)` — `lib/auth/AuthProvider.tsx`, dans le callback MSAL
    `LOGIN_SUCCESS` (identifiant `homeAccountId`, pas `username`/email, pour éviter le PII dans le
    `distinct_id`).
  - `cv_uploaded` — `app/_components/UploadSection.tsx`, `.then()` de l'upload.
  - `cv_analysis_viewed` — `app/_components/CvAnalysisCard.tsx`, une fois par montage quand `status`
    atteint `"done"` (`useRef` guard).
  - `matches_viewed` — `app/_components/CorrespondancesPanel.tsx`, une fois par montage quand
    `matches.length > 0 && !loading` (`useRef` guard).
  - `match_analysis_requested`, `credit_consumed` — même fichier, `requestAnalysis()`.
  - `credits_exhausted` — même fonction, uniquement dans la branche `catch` où `status === 402` (le bus
    de crédits appelle `notifyCreditsConsumed()` sur ce même chemin pour une autre raison — resync avec
    le solde serveur, pas une consommation réelle — donc l'event ne s'accroche pas à cet appel mais au
    `status` HTTP).
  - `profile_completed` + `setPersonProperties({ experience_level })` — `app/profile/page.tsx`, après le
    `PUT /profile` réussi.
- Propagation des variables d'environnement jusqu'au build Docker (pas de changement Terraform — voir
  Décisions techniques) : `.env.local`/`.env.local.example`, `ARG`/`ENV` dans `Dockerfile`, `build-args`
  dans `.github/workflows/buildAgents.yml` (`vars.NEXT_PUBLIC_POSTHOG_KEY`/`_HOST`).
- Mock `posthog-js` ajouté dans `__tests__/CvAnalysisCard.test.tsx` et
  `__tests__/CorrespondancesPanel.test.tsx` (seuls tests existants touchant les composants modifiés), plus
  un nouveau `__tests__/Providers.test.tsx` (voir Décisions techniques).

### Décisions techniques

Le prompt de tâche initial pointait vers `envs/dev/frontend.tf` pour propager les variables d'env —
vérifié faux avant d'implémenter : ce fichier documente explicitement qu'aucune variable `NEXT_PUBLIC_*`
n'est portée par la Container App (elles sont inlinées dans le bundle JS au build, pas lues au runtime).
Le mécanisme réel, déjà en place pour `NEXT_PUBLIC_ENTRA_*`, est `Dockerfile` (`ARG`/`ENV`) +
`buildAgents.yml` (`build-args` depuis les `vars` du repo GitHub) — reproduit à l'identique pour
`NEXT_PUBLIC_POSTHOG_KEY`/`NEXT_PUBLIC_POSTHOG_HOST`. Aucun fichier Terraform touché : cette PR ne
mélange donc pas couche plateforme et couche applicative.

**Action manuelle requise, hors du périmètre de cette PR :** les variables de repo GitHub
`vars.NEXT_PUBLIC_POSTHOG_KEY` et `vars.NEXT_PUBLIC_POSTHOG_HOST` doivent être créées manuellement
(Settings → Secrets and variables → Actions → Variables) avant le prochain déploiement en dev.

Ce point a failli être plus grave qu'un simple "PostHog silencieusement désactivé". La première version de
`Providers.tsx` utilisait le même `requireEnv()` fail-fast que `lib/auth/msalConfig.ts` (throw si la
variable est absente). Repéré après-coup (revue indépendante, hors des deux passes `reviewer-frontend`) :
`buildAgents.yml` déclenche `az containerapp update` sur `app-jf-dev-frc-frontend` immédiatement après tout
push sur `dev` touchant `JobFinder/frontend/**` — donc merger cette PR avant la création des variables
GitHub aurait redéployé en prod-dev un layout racine qui `throw` à l'évaluation du module. Vérifié qu'aucun
`global-error.tsx` n'existe dans ce projet (seul un `error.tsx` par segment, qui ne capture pas les erreurs
du root layout lui-même) : ce throw aurait fait tomber tout le site, pas juste désactivé les analytics.
Corrigé en déplaçant la lecture des deux variables à l'intérieur du `useEffect` (toujours une référence
statique `process.env.NEXT_PUBLIC_*`, requis pour l'inlining Next.js, mais plus au niveau module) et en
dégradant sur `console.warn` + `return` plutôt que de lancer une exception — l'appel `posthog.capture()`
avant tout `init()` ne fait de toute façon rien de pire qu'un warning silencieux (vérifié dans le bundle
installé : `posthog-js` renvoie tôt sur `!this.__loaded` pour `capture`/`identify`, jamais de throw).
`requireEnv()` reste approprié tel quel dans `msalConfig.ts` : sans MSAL l'app n'a pas d'auth et ne doit pas
le cacher — la distinction est la criticité de la feature, pas une règle générale à appliquer partout.
`PostHogProvider` gagne au passage la JSDoc qui lui manquait, même pattern que `AuthProvider`.
Nouveau test `__tests__/Providers.test.tsx` : vérifie que `posthog.init` est bien appelé quand les deux
variables sont présentes, et que le rendu ne lève rien et saute `init` quand elles sont absentes.

**Vérification :** `npx jest` (155 tests, tous passants), `npx tsc --noEmit` (aucune erreur), `npx eslint`
sur tous les fichiers touchés (aucun avertissement), deux passes `reviewer-frontend` (la première a bloqué
sur le nommage de fichier, corrigé puis re-soumis, `APPROUVÉ` sans remarque). QA manuelle des 8 events en
dev déployé non réalisée dans cette session (nécessite les variables de repo GitHub ci-dessus) — à faire
une fois celles-ci créées.

## PR #222 — feat: formulaire "Donner un avis / Signaler un bug"

**Date :** 2026-07-24
**Branche :** `feature/feedback-bug-form` → `dev`

### Contexte

Nouveau formulaire d'avis/signalement de bug pour les utilisateurs authentifiés de JobFinder, relayé par
email. Pas de nouvelle table en base, pas de nouvelle infra email dans ce repo : la fonctionnalité réutilise
la Function Azure anonyme `sendContactEmail`, déjà déployée par le repo portfolio (contrat générique
`{name, email, subject, message}` → relais SMTP Zoho vers `contact@vincentboutin.dev`). L'appel se fait
serveur-à-serveur depuis le backend Python, jamais depuis le frontend, pour deux raisons : éviter un
changement CORS côté portfolio, et garantir que `name`/`email` proviennent du JWT validé plutôt que d'un
champ contrôlé par le client.

### Ce qui a été fait

- `JobFinder/Terraform/envs/dev/variables.tf` : nouvelle variable `portfolio_contact_function_url`,
  défaut chaîne vide — même schéma non-fail-fast que `admin_user_ids` dans le même fichier, la valeur
  réelle n'étant connue qu'après provisionnement manuel de la Function côté portfolio.
- `JobFinder/Terraform/envs/dev/webapp.tf` : la variable est propagée dans `env_vars` du module `webapp`
  sous `PORTFOLIO_CONTACT_FUNCTION_URL`.
- `JobFinder/python/agents/webapp/routers/feedback.py` (nouveau) : `POST /feedback`, `APIRouter(prefix="/feedback")`.
  Utilise `Depends(get_current_identity)` (et non `get_current_user`) car l'email et le nom affiché sont
  nécessaires. `_resolve_sender()` fait retomber la résolution nom/email : claims du JWT → `UserProfile`
  stocké → email placeholder synthétisé (`{user_id}@jobfinder.local`), avec mention "email indisponible"
  injectée dans le message relayé dans ce dernier cas — la Function portfolio exige des champs `name`/
  `email` non vides et rejette sinon la requête. `PORTFOLIO_CONTACT_FUNCTION_URL` est lue via
  `os.environ.get(..., "")` au niveau module, **sans** le `raise` fail-fast habituel (contrairement à
  `ENTRA_EXTERNAL_TENANT_ID` dans `auth.py`) : la variable est légitimement absente tant que Vincent ne l'a
  pas provisionnée manuellement après déploiement, et un fail-fast ferait planter tout le webapp au
  démarrage (`main.py` importe tous les routers sans condition) pour une fonctionnalité annexe — une URL
  non configurée ne dégrade que cet unique endpoint (502). Utilise `requests` (déjà une dépendance du
  webapp, même schéma que `agents/offer_fetching/ft_client.py` et la récupération JWKS dans `auth.py`) avec
  un `try/except requests.RequestException` qui logue via structlog puis relance en `HTTPException(502)`.
  Le sujet relayé est préfixé `"JOBFINDER - BUG : <subject>"` / `"JOBFINDER - AVIS : <subject>"`, et le
  corps du message relayé s'ouvre toujours par une première ligne `"RESSENTI POSITIF/NEUTRE/NEGATIF/NON
  INDIQUE"` (dict `_SENTIMENT_LABELS`, `"NON INDIQUE"` par défaut quand `sentiment` est `None`), suivie
  d'une ligne vide puis du message réel — pour que Vincent puisse trier son inbox sans ouvrir chaque
  message.
- `JobFinder/python/agents/webapp/schemas.py` : nouveau schéma `FeedbackCreate`
  (`type: Literal["avis","bug"]`, `subject` max_length=200, `message` max_length=5000) — délibérément sans
  champ email/nom. `sentiment: Literal["positif","neutre","negatif"] | None = None` est le seul champ
  optionnel (le sélecteur smiley n'est pas obligatoire).
- `JobFinder/python/agents/webapp/main.py` : enregistre `feedback.router` aux côtés de `cv`/`matches`/`profile`.
- `JobFinder/python/tests/test_webapp_feedback.py` (nouveau) : 8 tests — préfixage du sujet bug/avis
  (`"JOBFINDER - BUG : ..."` / `"JOBFINDER - AVIS : ..."`), ligne `RESSENTI ...` (y compris le repli
  `"RESSENTI NON INDIQUE"` quand `sentiment` est omis), repli JWT → profil stocké, repli vers l'email
  placeholder synthétisé quand rien n'est disponible, 502 sur échec du relais, 502 quand l'URL n'est pas
  configurée, 500 sur échec de la lookup profil en DB. Suite complète (`pytest tests/`) : 362 passed.
- `JobFinder/frontend/app/feedback/page.tsx` (nouveau) : client component, même structure que
  `app/profile/page.tsx` (état local loading/error, barre de retour à l'accueil, tokens de thème
  `bg-profile-page`/`bg-profile-surface`). Sélecteur segmenté Avis/Bug (défaut Avis), champ sujet, textarea
  message, appelle `apiClient.post("/feedback", {...})`. Sous le message, sélecteur "Ressenti (facultatif)"
  — 3 boutons icônes (`Frown`/`Meh`/`Smile` de lucide-react, labels "Mécontent"/"Neutre"/"Content",
  `role="radiogroup"`/`role="radio"`/`aria-checked`, clic pour désélectionner puisque le champ est
  optionnel) — envoie `sentiment` (ou `null`) dans le corps de `POST /feedback`.
- `JobFinder/frontend/app/_components/AuthButton.tsx` et `MobileNavMenu.tsx` : nouvelle entrée "Donner un
  avis / Signaler un bug" (icône `MessageSquareWarning` de lucide-react, choisie après vérification par
  grep qu'aucune icône n'était déjà importée dans le repo pour cet usage). Dans `AuthButton.tsx`, l'entrée
  est placée après le bouton de bascule de thème (ordre : Mon profil → Thème → Donner un avis/Signaler un
  bug → séparateur → Se déconnecter). Dans `MobileNavMenu.tsx`, qui n'a pas de bascule de thème, elle reste
  juste après "Mon profil".

### Décisions techniques

Point ouvert à trancher par Vincent, non résolu par cette PR : il n'existe aujourd'hui aucun mécanisme de
tfvars ou de variable GitHub pour les variables Terraform non-secrètes de ce repo (confirmé via le
subagent `explorer` en amont de l'implémentation) — seul un `default` Terraform existe pour des variables
comme `admin_user_ids`/`frontend_custom_domain`. Provisionner en pratique `portfolio_contact_function_url`
signifie donc soit éditer directement le `default` dans `variables.tf`, soit introduire un mécanisme par
environnement qui n'existe pas encore. Cette PR ne tranche pas la question — elle documente la variable
avec un défaut vide et un endpoint qui dégrade proprement (502) tant qu'elle n'est pas renseignée.

**Suivi manuel requis de la part de Vincent, hors périmètre de cette PR :** (1) récupérer l'URL réelle de
la Function portfolio (`terraform output default_hostname` dans `portfolio/infra/terraform/`, ou le portail
Azure) ; (2) la renseigner comme `portfolio_contact_function_url` pour l'environnement dev — voir
l'ambiguïté sur le mécanisme de provisionnement ci-dessus ; (3) confirmer que le CORS de la Function
portfolio n'a pas besoin de changement (l'appel est serveur-à-serveur, donc a priori non) une fois testé en
conditions réelles.

**Suivi post-review (après ouverture de la PR #222) :** trois remarques non-bloquantes relevées par une
revue indépendante ont été corrigées :
1. `feedback/page.tsx` : le bouton d'envoi gardait le style/texte "Envoyé ✓" si l'utilisateur modifiait le
   formulaire après un envoi réussi, pour un brouillon pourtant pas encore soumis. Ajout d'un helper
   `clearOutcome()` (`setState((s) => (s === "loading" ? s : "idle"))`) câblé sur les cinq handlers éditables
   (type, sujet, message, ressenti) — même pattern que `handleExperienceChange`/`handleDescriptionChange`
   dans `app/profile/page.tsx`, qui remettent `saved` à `false` sur édition.
2. `schemas.py::FeedbackCreate` : `subject`/`message` n'avaient qu'un `max_length`, pas de `min_length` — une
   valeur uniquement composée d'espaces passait la validation côté API même si le bouton client la bloque.
   Ajout de `model_config = ConfigDict(str_strip_whitespace=True)` + `min_length=1` sur les deux champs, pour
   que "obligatoire" soit une vraie garantie serveur et pas seulement un bouton désactivé côté client.
3. Point relevé mais **non corrigé, délibérément** : l'appel `requests.post` dans `feedback.py` bloque le
   thread FastAPI jusqu'à `CONTACT_FUNCTION_TIMEOUT_SECONDS` (15s) — sans risque aujourd'hui vu le trafic,
   migrer vers `httpx.AsyncClient` réglerait le problème sous charge concurrente, mais introduirait une
   incohérence avec le pattern `requests` synchrone utilisé partout ailleurs côté serveur-à-serveur dans ce
   repo (`auth.py`, `ft_client.py`) pour un gain non justifié à ce stade.

`reviewer-backend` et `reviewer-frontend` ont re-validé chacun des deux premiers points (`APPROUVÉ`, aucune
remarque). 2 nouveaux tests ajoutés (`test_defaults_to_non_indique_when_sentiment_omitted` existait déjà ;
nouveau : `test_rejects_whitespace_only_required_field`, paramétré sujet/message).

**Vérification :** `pytest tests/` (`JobFinder/python`) : 364 passed. `npm run build` (`JobFinder/frontend`)
compile, route `/feedback` à 3.17 kB. `npm test` (`JobFinder/frontend`) : 155 passed, 16 suites (dont
`MobileNavMenu.test.tsx`, non affecté par le nouveau lien). `terraform fmt -check -diff` et
`terraform validate` (`JobFinder/Terraform/envs/dev`) : propre / valide — pas de `plan`/`apply` local
(CI-only, conforme au Git Flow de ce repo). Test manuel de `POST /feedback` contre la vraie Function
portfolio **non effectué** dans cette session (aucune URL de Function de test/dev disponible dans cet
environnement) — à faire avant merge, conforme à la checklist "Vérification avant PR" de ce repo. Confirmé
qu'aucun fichier du repo `portfolio` (séparé) n'a été touché.

## PR #223 — fix(ci): provision PORTFOLIO_CONTACT_FUNCTION_URL as a GitHub secret, mark Terraform var sensitive

**Date :** 2026-07-25
**Branche :** `fix/portfolio-contact-function-url-secret` → `dev`

### Contexte

Suite à la PR #222 : `POST /feedback` renvoie 502 en dev/prod parce que `portfolio_contact_function_url`
reste à son défaut vide (`""`) — comportement voulu et déjà documenté dans PR #222, rien à corriger côté
logique applicative. Ce qui manquait, c'est le câblage CI/CD pour faire passer la vraie valeur (désormais
connue de Vincent) jusqu'à `terraform apply`.

Décision actée avec Vincent (via Claude Cowork, `docs/prompts/prompt-portfolio-contact-function-url-github-var.md`) :
cette URL devient un **secret GitHub** (`secrets.*`), pas une **variable GitHub** (`vars.*`), bien qu'elle ne
soit pas elle-même confidentielle (Function déjà anonyme, appelée depuis le navigateur du visiteur sur le
site portfolio statique — voir PR #222). Le point décisif est que ce repo `job-finder` est **public** :
`terraform plan`/`apply` imprime la valeur d'une `vars.*` en clair dans son diff, donc dans des logs
GitHub Actions publics et indexés ; `secrets.*` la masque automatiquement (`***`) partout où elle apparaît
dans ces logs. Éviter cette valeur de reconnaissance pour un scraper reste utile même si l'information
existe déjà ailleurs publiquement (site portfolio).

### Ce qui a été fait

- `.github/workflows/terraformApply.yml` (job `apply-dev`) et `.github/workflows/terraformPlan.yml`
  (job `plan-app`) : ajout de `TF_VAR_portfolio_contact_function_url: ${{ secrets.PORTFOLIO_CONTACT_FUNCTION_URL }}`
  juste après `TF_VAR_alert_email`, même schéma déjà en place pour ce secret. Ajouté aux deux workflows
  (pas seulement `apply`) pour que le `terraform plan` des PR touchant `dev` reflète la vraie valeur plutôt
  que de planifier contre une valeur vide, qui aurait rendu les plans de PR trompeurs pour toute review
  future.
- `JobFinder/Terraform/envs/dev/variables.tf` : `sensitive = true` sur la variable
  `portfolio_contact_function_url`. Protection complémentaire au secret GitHub, pas redondante — le masquage
  GitHub agit sur le texte brut des logs, tandis que `sensitive = true` empêche Terraform lui-même
  d'imprimer la valeur dans le diff formaté de `terraform plan`.
- `CLAUDE.md` : `PORTFOLIO_CONTACT_FUNCTION_URL` ajouté à la liste "GitHub secrets (sensitive)".
- Aucun changement dans `terraform.tfvars` ni `webapp.tf` : la consommation de la variable côté Container
  App (`env_vars` classique, pas un secret Container-App-side) ne change pas, seul le câblage CI/Terraform
  devait être masqué.
- La valeur réelle de l'URL n'apparaît nulle part dans ce repo (fichiers, commits, message de PR) —
  uniquement le nom du secret `PORTFOLIO_CONTACT_FUNCTION_URL`.

### Suivi manuel requis de la part de Vincent, hors périmètre de cette PR

Créer le secret de repo GitHub `PORTFOLIO_CONTACT_FUNCTION_URL` (Settings → Secrets and variables → Actions
→ onglet Secrets, pas Variables) avec la valeur déjà connue. Peut être fait avant ou après le merge de cette
PR — tant que le secret n'existe pas, `terraform apply` continue d'appliquer la valeur vide par défaut, sans
régression. `/feedback` ne sera fonctionnel qu'une fois le secret créé ET cette PR mergée sur `dev`.

**Vérification :** `terraform fmt -check -diff` et `terraform validate` (`JobFinder/Terraform/envs/dev`) :
propre / valide, l'ajout de `sensitive = true` ne casse pas la validation. Relecture manuelle des deux
fichiers YAML modifiés (indentation cohérente avec les lignes voisines). Pas de `plan`/`apply` local
(CI-only, conforme au Git Flow de ce repo).

---

## PR #224 — fix(frontend): sérialiser acquireTokenRedirect entre appels concurrents de l'intercepteur

**Date :** 2026-07-25
**Branche :** `fix/msal-redirect-race` → `dev`

*Numéro provisoire — `gh` indisponible dans cette session pour vérifier le prochain numéro réel
(issues + PRs) ; dérivé du dernier numéro utilisé dans ce journal (#223) + 1. À corriger après coup si la
PR ouverte sur GitHub prend en fait un autre numéro.*

### Contexte

Bug diagnostiqué lors d'une session Cowork antérieure (non ré-investigué ici) : après une première
connexion réussie (« rester connecté »), fermer le navigateur puis le rouvrir plus tard fait
systématiquement échouer la reconnexion via Google/CIAM à la première tentative — une reconnexion manuelle
depuis l'écran d'accueil réussit toujours à la deuxième tentative.

Cause racine : l'intercepteur axios partagé (`lib/api/client.ts`) appelle
`msalInstance.acquireTokenSilent(...)` sur chaque requête API et retombe sur
`msalInstance.acquireTokenRedirect(apiTokenRequest)` (redirection pleine page vers la CIAM) dès que
l'acquisition silencieuse lève `InteractionRequiredAuthError`. Deux composants montés ensemble sur la page
d'accueil déclenchent chacun un appel API dès que `isAuthenticated` devient vrai : `CreditsBadge.tsx`
(`/profile`) et `LibrarySection.tsx` (liste des CV). Quand le navigateur est rouvert avec un compte MSAL en
cache dont le refresh token a en réalité expiré côté serveur, les deux fetchs échouent avec
`InteractionRequiredAuthError` quasiment au même tick, et appellent tous deux `acquireTokenRedirect` sur la
même instance MSAL en concurrence — chacun écrivant son propre `state`/`nonce` OAuth dans le même
`sessionStorage` avant que l'autre n'ait fini de naviguer. Au retour de Google vers la CIAM, le `state` de
l'URL ne correspond plus à ce qui reste en `sessionStorage` (écrasé par le second appel), donc la CIAM
rejette la réponse. Une reconnexion manuelle ultérieure est un unique appel `loginRedirect` propre, donc
elle réussit toujours.

### Ce qui a été fait

- `JobFinder/frontend/lib/api/client.ts` : la redirection est désormais « single-flight » — une variable
  module-level `redirectInFlight: Promise<void> | null` est posée au premier appel concurrent de
  `acquireTokenRedirect` et attendue (pas répétée) par tout autre appelant concurrent de l'intercepteur. Le
  flag ne se réinitialise à `null` que si `acquireTokenRedirect` lui-même est rejeté (pour qu'une redirection
  échouée ne bloque pas définitivement les tentatives de reconnexion suivantes) ; il ne se réinitialise
  volontairement pas au succès, puisqu'une redirection réussie quitte la page et recharge de toute façon le
  module JS. Docstring de module et commentaire WHY déjà en place sur le bloc single-flight, complétés pour
  que la description en tête de fichier mentionne explicitement la déduplication (elle ne parlait
  auparavant que du fallback redirect, pas de son sérialisation).
- Nouveau test `JobFinder/frontend/__tests__/client.test.ts` : mocke directement `@/lib/auth/msalInstance`
  et `@/lib/auth/msalConfig` (évite d'avoir besoin des vraies variables d'env `NEXT_PUBLIC_ENTRA_*`, absentes
  en CI). Deux cas : (1) deux requêtes concurrentes partagent un unique appel `acquireTokenRedirect` ; (2)
  une requête après une tentative de redirection précédente échouée relance correctement l'acquisition
  (couvre la branche reset-à-`null`-sur-échec).
- `JobFinder/frontend/__tests__/README.md` : ligne `client.test.ts` ajoutée à « Modules covered », puce
  « Design decisions » sur l'approche de mock choisie, et correction de la section « Intentionally
  excluded » qui affirmait à tort que `lib/api/client.ts` n'avait aucune couverture de test.

### Décisions techniques

Aucun autre appel direct à `acquireTokenRedirect`/`acquireTokenSilent` ailleurs dans le frontend (vérifié
par grep) — les appels `loginRedirect` de `AuthButton.tsx`/`UploadSection.tsx` sont déclenchés par un geste
utilisateur explicite et non concernés par cette race, donc non modifiés.

**Vérification :** le test (1) a été confirmé comme détectant réellement la régression — revert temporaire
de `client.ts` vers l'ancien code (via `git stash`, jamais laissé dans le diff final) fait échouer le test
avec « 2 appels » au lieu de « 1 ». Suite `jest` complète non ré-exécutée dans cette session de revue
documentaire (accès en lecture/écriture de fichiers uniquement, pas d'exécution shell) — à relancer
(`npm test` dans `JobFinder/frontend/`) avant merge.

**Suivi post-review (après ouverture de la PR #224) :** deux remarques non-bloquantes relevées par une
revue indépendante ont été traitées :
1. `client.ts` : le fait que `redirectInFlight` ne se réinitialise jamais à `null` en cas de succès (seulement
   en cas d'échec) reposait sur une hypothèse implicite non documentée — `acquireTokenRedirect` navigue
   toujours hors de la page en cas de succès, donc le module JS est de toute façon rechargé. Ajout d'un
   commentaire au-dessus de la déclaration du flag documentant cette hypothèse et le risque si un flow
   d'authentification non-navigant (ex. popup fallback) était introduit un jour.
2. `client.test.ts` : le test appelait `flushMicrotasks()` deux fois de suite avec un commentaire justifiant
   les deux appels comme nécessaires. Vérification empirique (5 exécutions locales) qu'un seul appel suffit
   et n'introduit aucune instabilité — le second appel était un reliquat du débogage initial du bug
   `instanceof`/registre de modules (voir plus haut), jamais nettoyé. Supprimé, et commentaire de
   `flushMicrotasks` réécrit pour expliquer correctement pourquoi un seul flush (macrotask via `setTimeout`)
   suffit à vider une chaîne de microtasks quelle que soit sa profondeur.

`reviewer-frontend` a re-validé les deux points (`APPROUVÉ`, aucune remarque). Suite `jest` complète (17
suites / 157 tests) et `npm run lint` relancés après chaque changement — propres.

---

## PR #225 — fix(cv-analysis): distinguish target-occupation sibling ROME codes from different-direction codes requiring proof

**Date :** 2026-07-25
**Branche :** `fix/cv-analysis-rome-code-family-coverage` → `dev`

### Contexte

Suite à `prompt-cv-analysis-rome-code-determinism-and-precision.md` (PR mergée, commit `128c298`) : le
pinning température/seed et la règle anti-confusion secteur/occupation avaient été ajoutés à
`_extract_rome_codes`. Trois jours plus tard, `5dc96aa` a changé le déploiement par défaut de
`gpt-4o-mini` vers `gpt-5-mini` pour corriger un autre bug réel (recall libre sur ~1911 codes sans
référentiel affiché) — mais `gpt-5-mini` rejette `temperature`/`seed` (erreur 400), donc
`MODELS_WITHOUT_TEMPERATURE_SEED` neutralise silencieusement le pinning pour le modèle réellement utilisé
en prod depuis le 22/07.

Preuve constatée par Vincent le 25/07 : un même CV publié 3 fois a produit 89 / 131 / 214 matches selon
l'upload, avec des domaines ciblés très différents (un upload penche devops sans aucune offre cloud
engineer, un autre ramène des compétences dev sans rapport avec le profil). Cause aval :
`_get_all_matches` (`agents/matching/main.py`) filtre les offres de façon binaire sur les codes ROME
extraits pour ce `cv_id` précis (PR #211) — un jeu de codes différent à chaque extraction produit un pool
d'offres éligibles entièrement différent.

Cette PR ne traite pas le non-déterminisme d'échantillonnage de `gpt-5-mini` lui-même (décision actée
avec Vincent le 25/07, hors périmètre). Elle corrige un problème distinct trouvé en creusant la logique
du prompt : la RÈGLE — niveau de qualification de `ROME_EXTRACTION_SYSTEM_PROMPT` confondait deux
situations sous une seule règle — l'escalade de responsabilité non démontrée (ex. dessinateur-projeteur
→ chef de chantier, usage prévu, à garder tel quel) et les fiches ROME sœurs qui décrivent ensemble un
seul objectif cible parce que le référentiel ROME n'a pas toujours une fiche unique par métier réel du
marché (ex. "Cloud Engineer/DevOps" éclaté, au même niveau de qualification, sur `M1801`
(administrateur systèmes), `M1876` (technicien cloud) et `M1879` (ingénieur cloud) — exactement
l'exemple donné dans `ROME_EXTRACTION_SYSTEM_PROMPT`). La règle exigeait une "preuve distincte"
pour chacune de ces fiches comme s'il s'agissait d'expériences séparées à justifier une par une, ce qui
aggrave l'instabilité pour les profils couvrant légitimement plusieurs fiches ROME voisines (dont Vincent
lui-même). Voir `docs/prompts/prompt-cv-analysis-rome-code-family-coverage.md` pour le diagnostic complet.

### Ce qui a été fait

- `agents/cv_analysis/main.py` — la fin de `ROME_EXTRACTION_SYSTEM_PROMPT` (RÈGLE — niveau de
  qualification) est réécrite en deux règles distinctes : l'exigence de preuve (expérience réelle et
  distincte, pas simple proximité de secteur) s'applique désormais uniquement à un code représentant une
  direction de carrière différente de l'objectif principal ; une nouvelle RÈGLE — famille de métiers
  cible demande d'inclure toutes les fiches ROME de la liste affichée qui décrivent la même direction au
  même niveau de qualification, même quand le référentiel la découpe en plusieurs fiches voisines.
- Docstring de `_extract_rome_codes` : cinquième invariant documenté (même style que les quatre
  existants — déterminisme, occupation propre au candidat, priorisation de l'objectif déclaré,
  référentiel affiché), renvoyant vers le fichier prompt ci-dessus pour le diagnostic complet.

### Décisions actées avec Vincent (25/07, non rouvertes dans cette PR)

- Ne pas ajouter de vote majoritaire multi-appels, ne pas toucher au filtre dur du matching
  (`matching/main.py`) — mesures complémentaires envisagées mais reportées à une tâche séparée si ce fix
  seul ne suffit pas.
- Ne pas revenir à `gpt-4o-mini` — risque de perdre la qualité de jugement sur le niveau de qualification
  que `5dc96aa` visait aussi à améliorer.

### Limite connue, héritée, toujours hors scope

`_merge_rome_codes` n'ajoute des codes que par union (sauf reconciliation par `cv_id`, déjà en place,
PR #213) — un profil déjà contaminé par une extraction passée imprécise garde ses codes erronés tant que
le CV concerné n'est pas supprimé puis ré-uploadé.

### Vérification

`pytest tests/test_cv_analysis.py -v` (`JobFinder/python`) : 69 passed. Aucun test n'asserte sur le texte
exact de la RÈGLE — niveau de qualification modifiée (recherche `ROME_EXTRACTION_SYSTEM_PROMPT` dans
`tests/` : deux assertions existantes portent sur `F1104:` et sur l'interdiction d'inventer un code hors
liste, ni l'une ni l'autre dans le bloc réécrit).

**Test manuel décisif non effectué dans cette session** (comparer 3-5 extractions avant/après sur un des
trois `cv_id` réels du 25/07 à 89/131/214 matches, sur le modèle de `test_rome_extraction_nicolas_no_temp.py`) :
nécessite un `cv_id` que Vincent n'a pas encore communiqué à cette session, plus un accès Key Vault et
probablement réseau au Postgres dev (vraisemblablement privé) pour lire `cvs.raw_text`, ainsi que des
appels OpenAI réels facturés — à faire par Vincent avant ou après merge, conformément à la checklist
"Vérification avant PR" du prompt source. Rappel : les profils déjà contaminés par une extraction
antérieure ne seront pas corrigés rétroactivement — observer l'effet sur un profil réel demande de
supprimer puis ré-uploader le CV concerné après déploiement.

## PR #226 — feat(frontend): rendre cliquables les indices de navigation scroll (Carte/Bibliothèque)

**Date :** 2026-07-25
**Branche :** `feature/clickable-nav-scroll-hints` → `dev`

### Contexte

Vincent a remarqué que sur la vue "Vos correspondances" (`CVDetailSection`), l'indice "BIBLIOTHÈQUE"
(texte + flèche qui rebondit) en haut de page est cliquable et déclenche un scroll smooth vers la
bibliothèque, alors que les indices visuellement identiques présents sur les autres pages — "CARTE" et
"BIBLIOTHÈQUE" sur l'écran d'import de CV, "ACCUEIL" et "OFFRES" sur la bibliothèque — étaient purement
décoratifs (`pointer-events-none`, aucun `onClick`). Demande : aligner le comportement de tous ces
indices sur celui déjà en place dans `CVDetailSection`, et ajouter un nouveau footer "ACCUEIL" (flèche
vers le bas) sur la page Carte, qui n'en avait aucun.

### Ce qui a été fait

- `UploadSection.tsx` — l'indice "CARTE" (haut) devient un bouton qui appelle `onEnterMap` (nouvelle
  prop) ; l'indice "BIBLIOTHÈQUE" (bas) devient un bouton qui appelle `onScrollToLibrary` (nouvelle
  prop). Les deux gardent leurs classes de visibilité existantes (`max-md:hidden`,
  `[@media(any-pointer:coarse)]:hidden` pour CARTE).
- `HomeMapSection.tsx` — passe `enterMap` (déjà utilisé par le pill tactile "Carte") à `UploadSection`
  via `onEnterMap`. Ajoute un nouveau bouton "ACCUEIL" (texte + flèche vers le bas, `animate-bounce`) en
  mode carte, appelant `exitMap` — équivalent souris du pill tactile "Terminé" déjà existant, avec les
  mêmes classes de visibilité inversées (`max-md:hidden [@media(any-pointer:coarse)]:hidden`) pour ne
  jamais s'afficher en même temps que lui.
- `HomeClient.tsx` — `handleCloseDetail` (déjà utilisé par `CVDetailSection`) est réutilisé tel quel comme
  `onScrollToLibrary` pour `UploadSection` (même destination, pas de duplication). Nouvelle fonction
  `handleScrollToDetail` pour l'indice "OFFRES" de `LibrarySection`, qui scrolle vers la section détail
  déjà montée (un CV y est auto-sélectionné dès que la bibliothèque en contient un).
- `LibrarySection.tsx` — l'indice "ACCUEIL" (haut) devient un bouton réutilisant la prop `onScrollToHome`
  existante (déjà utilisée par "Ajouter un CV" pour scroller avant d'ouvrir le sélecteur de fichier) ;
  l'indice "OFFRES" (bas) devient un bouton appelant la nouvelle prop `onScrollToOffers`.

**Bug trouvé et corrigé en testant "ACCUEIL" dans le navigateur :** le bloc d'en-tête de la bibliothèque
(titre + compteur de CVs), positionné en `absolute inset-x-0 top-0` avec un `padding-top` important
(`pt-24`/`md:pt-40`), arrive après le bouton "ACCUEIL" dans le DOM et — sans `pointer-events-none` —
capturait silencieusement les clics sur la zone du bouton malgré son contenu visuel décalé plus bas par
le padding. Rien à l'intérieur de ce bloc n'étant interactif, `pointer-events-none` lui a été ajouté.

### Vérification

`tsc --noEmit` et `eslint` propres sur les quatre fichiers touchés. Test manuel dans Chrome (session
Google existante, `npm run dev`) : les six comportements (CARTE → mode carte, ACCUEIL carte → sortie
carte, BIBLIOTHÈQUE upload → scroll bibliothèque, ACCUEIL bibliothèque → scroll accueil, OFFRES → scroll
détail, BIBLIOTHÈQUE détail → régression non cassée) vérifiés un par un via captures d'écran et lecture
de `main.scrollTop`.

**Suivi post-review (après ouverture de la PR #226) :** deux remarques de Vincent traitées.

1. **`LibrarySection.tsx` — OFFRES sans CV sélectionné.** `detailRef.current` est `null` tant que
   `HomeClient` n'a pas monté `CVDetailSection` (uniquement une fois `selectedCvId` non nul) — fenêtre réelle
   pendant un upload optimiste où la bibliothèque est déjà accessible mais le vrai CV n'est pas encore dans
   `cvs`. Le clic sur OFFRES ne plantait pas (`?.scrollIntoView` no-op silencieux) mais ne faisait rien
   d'observable. Le bouton est maintenant conditionné à `selectedCvId`, même garde que celle déjà utilisée
   par `HomeClient` pour monter `CVDetailSection`.
2. **Duplication du pattern [texte + flèche `animate-bounce`], répété six fois** dans `UploadSection.tsx`,
   `HomeMapSection.tsx`, `LibrarySection.tsx` et `CVDetailSection.tsx`. Extraction d'un composant partagé
   `ScrollHint.tsx` (`direction`, `label`, `ariaLabel`, `onClick`, `className` pour le positionnement propre à
   chaque appelant) — les six occurrences pointent maintenant vers la même implémentation, y compris le bouton
   déjà présent dans `CVDetailSection` (qui n'avait au passage jamais eu l'anneau de focus des cinq autres :
   uniformisé par la même occasion).

Note de vérification pour ce suivi : le scroll `smooth` déclenché par clic n'a pas pu être ré-observé
visuellement pendant le débogage (`document.visibilityState` de l'onglet Chrome de test est passé à
`"hidden"` en cours de session malgré `document.hasFocus() === true`, ce qui suspend l'avancement des
animations pilotées par `requestAnimationFrame` — reproduit même sur un `main.scrollTo({behavior:"smooth"})`
brut, indépendant de tout code de cette PR, et même dans un nouvel onglet fraîchement ouvert). Le
comportement de la fonction elle-même reste vérifié : un `console.log` temporaire dans `handleScrollToDetail`
a confirmé que le clic déclenche bien le handler avec `detailRef.current` pointant sur le bon nœud
`section#cv-detail`, et un `scrollIntoView({behavior:"auto"})` vers la même cible saute correctement au bon
offset — seule l'étape d'animation n'a pas pu être observée dans cette session.

`tsc --noEmit` et `eslint` propres après les deux correctifs.

**Second suivi post-review :** Vincent a demandé confirmation qu'il n'est possible ni de scroller sur la
carte, ni d'afficher le bouton/l'indice "CARTE" et sa flèche, tant que l'utilisateur n'est pas connecté.
Vérification live (déconnexion réelle via `instance.logoutRedirect()`, puis `WheelEvent` synthétique
`deltaY: -100` dispatché sur `#home`) : les deux étaient déjà correctement gardés — l'indice `ScrollHint`
"CARTE" dans `UploadSection.tsx` est conditionné à `isAuthenticated`, et le geste de scroll dans le
gestionnaire `wheel` de `HomeMapSection.tsx` vérifie `isAuthenticatedRef.current` avant de transitionner
vers le mode carte ; capture d'écran confirmant qu'on reste sur l'écran d'import de CV après le
`WheelEvent`.

Point durci à cette occasion : `enterMap()` elle-même n'avait pas de garde interne — elle ne restait
sûre que parce que ses trois appelants actuels (geste de scroll, pill tactile, indice desktop) la
gardaient chacun de leur côté. Ajout d'une garde `isAuthenticatedRef.current` interne à `enterMap()`
(en plus de celle déjà présente dans chacun des trois appelants, qui reste en place — garde redondante
par construction, notamment côté geste de scroll où elle conditionne aussi le `preventDefault()`) et
redirection du geste de scroll pour passer par cette même fonction plutôt que dupliquer
`startTransition("to-map", "map")` — un seul point de décision désormais pour l'action de transition
elle-même, pour qu'un futur appelant ne puisse pas accidentellement ouvrir la carte (zone géographique
liée au profil) sans être connecté. Aucun changement de comportement observable pour les trois
appelants existants (déjà tous correctement gardés) ; re-testé en live après coup (déconnexion +
`WheelEvent`, puis reconnexion + clic sur l'indice "CARTE") pour confirmer l'absence de régression
dans les deux sens.

---

## PR #227 — fix(frontend): brancher "Ajouter un CV" de la bibliothèque sur le pipeline d'upload de UploadSection

**Date :** 2026-07-25
**Branche :** `fix/library-cv-add-animation-timing` → `dev`

### Contexte

Bug signalé par Vincent : cliquer sur "Ajouter un CV" depuis la bibliothèque (`LibrarySection.tsx`) fait
bien défiler jusqu'à la section d'accueil et ouvre bien le sélecteur de fichier natif, mais l'animation
« fly-down » qui joue normalement après un upload (l'icône CV qui s'anime en vignette puis descend,
pilotée par `OrbitAnimation.tsx` via la machine à états `animState` de `UploadSection.tsx`) ne jouait
jamais pour cette entrée.

Cause racine : `LibrarySection.tsx` possédait son propre pipeline d'upload entièrement séparé (son propre
`<input type="file">` caché, son propre `handleFileChange`, son propre appel `apiClient.post("/cv/upload",
...)`, son propre état `uploading`/`uploadError`) qui ne touchait jamais à `animState`/`OrbitAnimation` de
`UploadSection`. Seul le chemin clic-sur-l'icône (`UploadSection.handleClick` → `handleFile`) déclenchait
l'animation.

Second signalement lié : le sélecteur de fichier natif ("popup") mettait du temps à apparaître depuis ce
bouton — l'ancien `handleScrollToHome` attendait un événement `scrollend` ou un `setTimeout` de repli de
900ms avant d'ouvrir le propre input de `LibrarySection`.

### Ce qui a été fait

- `UploadSection.tsx` : converti en `forwardRef`, expose un handle impératif (`UploadSectionHandle` avec
  `openPicker(): void`) via `useImperativeHandle`, gardé par la même condition `animState === "idle"` que
  le clic sur l'icône — no-op silencieux sinon. Contrairement au clic sur l'icône, un appel non
  authentifié est ici un simple no-op (pas de `loginRedirect` déclenché) : le slot d'ajout qui pilote
  `openPicker` ne s'affiche de toute façon que pour un utilisateur connecté. Ceci permet à un composant
  frère de déclencher le même sélecteur de fichier + upload + animation que le chemin clic-icône utilisait
  déjà. JSDoc de `openPicker` complétée pour documenter explicitement ces conditions de no-op silencieux
  (invisibles pour l'appelant) et cette différence avec le clic sur l'icône.
- `JobFinder/frontend/__tests__/README.md` : ligne `LibrarySection.test.tsx` ajoutée à « Modules covered »
  (le fichier de test existait déjà mais n'y avait jamais été référencé) — décrit le nouveau périmètre du
  test : `onAddCv`, propagation de la suppression à `onCvsChange`, masquage du slot d'ajout à quota
  atteint.
- `HomeMapSection.tsx` : nouvelle prop `uploadSectionRef?: Ref<UploadSectionHandle>`, transmise à
  `<UploadSection ref={uploadSectionRef} .../>`.
- `HomeClient.tsx` : `uploadSectionRef` créé et transmis à `HomeMapSection`. L'ancien `handleScrollToHome`
  (attente de `scrollend` ou du `setTimeout` de 900ms avant d'ouvrir l'input de `LibrarySection`) remplacé
  par `handleAddCv`, qui fait défiler jusqu'à `#home` ET appelle `uploadSectionRef.current?.openPicker()`
  de façon synchrone dans le même handler — plus d'attente artificielle. Corrige aussi le second
  signalement : le sélecteur de fichier s'ouvre désormais quasi instantanément au lieu d'attendre que le
  défilement se stabilise visuellement.
- `LibrarySection.tsx` : suppression complète de son pipeline d'upload autonome (`fileInputRef`,
  `handleFileChange`, `<input type="file">`, état `uploading`/`uploadError`, constante `MAX_PDF_BYTES`,
  effet de nettoyage `uploadErrorTimerRef`). Le bouton "Ajouter un CV" appelle désormais simplement la
  nouvelle prop `onAddCv` (remplace l'ancienne prop `onScrollToHome`). Le refetch après upload continue de
  fonctionner sans changement : `HomeClient.handleUploadComplete` incrémente déjà `libraryRefreshTrigger`,
  que l'effet `fetchCvs` existant de `LibrarySection` consomme déjà (déjà câblé pour le chemin
  clic-icône, et couvre maintenant aussi le chemin bibliothèque puisque les deux passent par le même
  `UploadSection.handleFile`).
- `OrbitAnimation.tsx` : taux de décroissance de l'onde de choc (click-ripple) dans `drawClickRipple()`
  doublé, de `flash - 0.055` à `flash - 0.11` par frame — c'est la demande « onde de choc 50 % plus
  rapide » (réduit sa durée d'environ 300ms à environ 150ms ; la formule de rayon `(1-flash)*65` s'ajuste
  automatiquement à la valeur de `flash`, aucun changement séparé nécessaire côté rayon). Commentaire WHY
  ajouté au-dessus de la ligne pour documenter ce lien entre le taux et la durée visée, afin qu'un futur
  réglage du rayon ne compense pas involontairement ce taux.
- `__tests__/LibrarySection.test.tsx` : les deux tests qui exerçaient l'ancien pipeline d'upload de
  `LibrarySection` (qui n'existe plus) sont réécrits en un seul test vérifiant que cliquer sur "Ajouter un
  CV" appelle la nouvelle prop `onAddCv` et n'appelle PAS directement l'endpoint d'upload (la
  validation/l'upload vivent désormais uniquement dans `UploadSection.handleFile`). Les deux tests non liés
  (propagation de la suppression d'un CV, masquage du slot d'ajout à quota atteint) sont inchangés.

### Suivi après rebase sur `dev` (PR #226 mergée entre-temps)

`dev` avait entre-temps reçu la PR #226 (indices de navigation cliquables), qui touchait les mêmes
fichiers via une prop `onScrollToHome?: (onLanded: () => void) => void` partagée par l'indice "ACCUEIL"
et (avant cette PR) le bouton "Ajouter un CV". Après rebase et résolution des conflits, `onScrollToHome`
ne sert plus qu'à l'indice "ACCUEIL" — qui l'appelait déjà avec un callback vide (`() => {}`), puisqu'un
simple scroll sans action de suivi. Le paramètre `onLanded` et le mécanisme `handleScrollToHome`
(listener `scrollend` + `setTimeout` de repli 900ms dans `HomeClient.tsx`) devenaient donc de la
complexité morte suite à cette PR — signalé en remarque non-bloquante par `reviewer-frontend` lors de la
review post-rebase. Simplifié : `onScrollToHome` est maintenant `() => void`, `handleScrollToHome` un
simple `scrollIntoView`, et `mainRef` (uniquement utilisée par l'ancien listener `scrollend`) supprimée
de `HomeClient.tsx`.

### Décisions techniques

**Régression de comportement assumée, non corrigée ici :** l'ancien pipeline `LibrarySection` affichait
un message d'erreur (état `uploadError`) quand le fichier choisi n'était pas un PDF ou dépassait la taille
max — ajouté suite à un retour de revue sur la PR #159 (`fix(frontend): apply PR #159 review feedback —
upload feedback, scrollend, a11y`). Le chemin unifié passe désormais entièrement par
`UploadSection.handleFile`, qui retourne silencieusement dans ces deux cas (`if (file.type !==
"application/pdf") return;` / `if (file.size > MAX_PDF_BYTES) return;`), sans aucun retour visuel, pour
les deux points d'entrée (icône ET bibliothèque). Le chemin icône n'a jamais eu ce retour d'erreur — ce
n'est donc pas une régression introduite par erreur — mais unifier les deux pipelines fait perdre au
chemin bibliothèque le comportement que la PR #159 avait spécifiquement ajouté à sa demande. À évaluer
séparément : soit accepter la perte, soit ajouter un retour d'erreur visible dans
`UploadSection.handleFile` lui-même pour les deux points d'entrée — non fait ici, hors périmètre du bug de
timing d'animation rapporté par Vincent.

### Vérification

- `npx jest` (`JobFinder/frontend`) : 17 suites / 156 tests passés (156 et non 157 comme sur la PR
  précédente : deux tests `LibrarySection` exerçant l'ancien pipeline d'upload ont été consolidés en un
  seul, voir ci-dessus — pas un test perdu).
- `npx tsc --noEmit` : propre (après un `npm install` ayant résolu une dépendance `posthog-js` manquante
  dans `node_modules`, sans rapport avec ce changement).
- `npx eslint` sur tous les fichiers touchés : propre.
- Vérification manuelle dans le navigateur : serveur de dev démarré sur un port alternatif (3010, pour ne
  pas entrer en conflit avec le serveur déjà lancé sur le port 3000 dans un autre worktree/session), la
  page d'accueil se charge correctement avec les changements en place, aucune erreur console sur la page
  non authentifiée.

**Non vérifié :** le flux complet d'upload de CV authentifié, de bout en bout, dans un vrai navigateur. La
redirection de connexion est câblée en dur vers `localhost:3000` via `NEXT_PUBLIC_REDIRECT_URI`, déjà
occupé par le serveur de dev d'un autre worktree — terminer cette connexion là-bas aurait signifié agir sur
le serveur d'une autre session, donc volontairement non poursuivi dans cette session. À faire avant merge :
se connecter réellement, cliquer "Ajouter un CV" depuis la bibliothèque, confirmer que l'animation
fly-down joue et que le sélecteur de fichier s'ouvre rapidement.

---

## PR #228 — feat(frontend): bouton "Marquer tout comme vu" sur la liste des offres

**Date :** 2026-07-25
**Branche :** `feature/mark-all-offers-seen` → `dev`

### Contexte

Vincent a demandé un bouton dans la barre de filtres de la page des offres (`CorrespondancesPanel`,
onglet "Offres"), aligné au bord droit, qui marque toutes les offres du CV courant comme "vues" en un
clic — pour pouvoir purger d'un coup les badges "Nouveau" une fois toutes les offres intéressantes
survolées, et ne voir aux prochaines connexions que les offres réellement nouvelles.

Exploration préalable (`explorer`) : le backend exposait déjà tout le nécessaire —
`PATCH /cv/{cv_id}/mark-all-seen` (`JobFinder/python/agents/webapp/routers/cv.py:959-994`), qui met
`seen_at = now()` sur tous les matchs non vus du CV. Aucune modification backend requise, la feature est
purement frontend.

### Ce qui a été fait

- Nouveau composant `MarkAllSeenButton.tsx` (`app/_components/`), calqué sur le pattern déjà en place
  dans `RomeReanalysisButton.tsx` (état `loading`/erreur local, `apiClient.patch` direct, bouton
  `disabled` pendant la requête). Style texte souligné, cohérent avec le bouton "Réafficher" de
  `MatchList.tsx`, plutôt que le style bordé de `RomeReanalysisButton` — action secondaire dans une barre
  déjà dense.
- `CorrespondancesPanel.tsx` : ajout du bouton dans la barre de filtres, positionné à droite via
  `ml-auto` sur le conteneur du bouton (le parent est déjà `flex`). Nouvelle fonction `markAllSeen()` qui
  ajoute tous les `offer.id` de `matches` à l'état local `seenIds`, persiste dans le cache localStorage
  `jf_seen_${cvId}` (réutilise `persistSeenId`, déjà utilisé par le marquage individuel dans
  `toggleExpand`), puis appelle `onMatchSeen?.()` pour rafraîchir le compteur `unseen_count` du parent —
  même pattern que le marquage individuel, appliqué en masse plutôt qu'à une seule offre, à ceci près
  que `markAllSeen` n'est déclenché qu'après confirmation serveur du PATCH (passé en callback
  `onMarkedAllSeen` à `MarkAllSeenButton`), contrairement au marquage individuel qui met à jour
  `seenIds` de façon optimiste avant même l'appel réseau. Le bouton est désactivé (`hasUnseen`) quand
  aucune offre "Nouvelle" n'est présente.

### Vérification

`tsc --noEmit` et `eslint` propres sur les deux fichiers touchés. Test manuel dans Chrome (session
Google existante, `npm run dev` pointant vers le backend dev déployé) sur un CV réel de test
(1003 correspondances, toutes "Nouveau" au départ) : clic sur "Marquer tout comme vu" → tous les badges
"Nouveau" disparaissent immédiatement, le bouton passe en état désactivé. Rechargement complet de la
page (nouvelle session, cache localStorage non réutilisé côté vérification serveur) : le badge
`unseen_count` de la carte CV dans la bibliothèque reste à zéro et aucune offre ne réaffiche "Nouveau" —
confirme que `seen_at` a bien été persisté côté serveur, pas seulement en local.

**Suivi (après ouverture de la PR #228) :** deux remarques traitées.

1. **Revue de code (`.then()` vs `async/await`, `hasUnseen` non mémoïsé, message d'erreur figé).**
   `hasUnseen` (`CorrespondancesPanel.tsx`) était recalculé à chaque rendu via un `matches.some(...)` en
   scope de rendu — `matches` pouvant monter à plusieurs milliers d'éléments, passé dans un `useMemo`
   (deps `[matches, seenIds]`), aligné avec le `useMemo` `filtered` juste en dessous. Dans
   `MarkAllSeenButton.tsx`, le message "Échec — réessayez" restait affiché si `disabled` passait à `true`
   entre-temps par un autre biais (ex. offres marquées vues depuis un autre onglet) — désormais masqué
   dans ce cas (`failed && !disabled`). En revanche, la suggestion de remplacer `.then()/.catch()/.finally()`
   par `async/await` dans `handleClick` n'a pas été suivie : vérification faite sur le codebase
   (`RomeReanalysisButton.tsx` — le modèle suivi pour ce bouton —, `toggleExpand`/`requestAnalysis` dans
   `CorrespondancesPanel.tsx`, `CVDetailSection.tsx`, `HomeMapSection.tsx`...), le pattern `.then()` est en
   fait dominant dans ce fichier et ses voisins ; seul `CVCard.tsx` utilise `await` sur un appel isolé.
   Garder `.then()` ici reste plus cohérent avec l'existant qu'un changement vers la minorité.
2. **Tiret affiché dans la bibliothèque quand un CV n'a aucune nouvelle offre.** Vincent a signalé que
   `CVCard.tsx` affichait un `—` (em dash, `text-label`) à la place du badge vert `+N` quand
   `unseen_count` vaut 0 — visible immédiatement après un "Marquer tout comme vu". Le badge entier
   (span + `title`) est désormais conditionné à `unseenCount > 0` : rien ne s'affiche à côté du compteur
   de matchs quand il n'y a aucune offre non vue, plutôt qu'un signe indéfini. Test existant
   `__tests__/CVCard.test.tsx` ("does not show unseen badge when unseen_count is 0") complété d'une
   assertion sur l'absence du `—`. Vérifié en live : la carte du CV déjà entièrement marqué vu
   (1003 matchs) n'affiche plus aucun signe à côté du compteur, contrairement à une carte voisine avec un
   badge `+377` intact.

---

## PR #229 — feat(frontend): ajouter une barre de navigation latérale (pilule) entre les 4 pages de la home

**Date :** 2026-07-25
**Branche :** `feature/left-nav-rail` → `dev`

### Contexte

Demande de Vincent : une barre de navigation en forme de pilule sur le bord gauche de l'écran, permettant
de sauter en un clic entre les « pages » de la home (import de CV, carte, bibliothèque, offres), chacune
symbolisée par une icône — carte en tête de pilule, l'icône de la page courante en bleu, les autres
grisées, blanches au survol. L'ajout de la barre nécessite de décaler l'interface des offres et de
l'affichage du CV pour ne rien superposer — Vincent proposait que la section des offres démarre à
mi-écran (coupée en deux de façon égale) et que la home laisse un peu plus de place pour se décaler.

Constat d'architecture fait avant d'implémenter (via l'agent `explorer`) : il n'existe pas 4 routes Next.js
distinctes. Tout vit dans une seule page `/` (`HomeClient.tsx`), organisée en 3 sections de scroll-snap
(`#home`, `#library`, `#cv-detail`) — et à l'intérieur même de `#home`, la carte et le CV sont deux
« layers » superposés pilotés par la machine à états `Mode` de `HomeMapSection.tsx` (`cv`/`to-map`/`map`/
`to-cv`), pas deux sections séparées. La nouvelle barre devait donc composer avec cette réalité plutôt
qu'avec 4 routes.

### Ce qui a été fait

- `HomeMapSection.tsx` : converti en `forwardRef`, expose un handle impératif (`HomeMapSectionHandle` avec
  `enterMap()`/`exitMap()`) via `useImperativeHandle` — même pattern que `UploadSectionHandle` (PR #227) —
  et une nouvelle prop `onModeChange?: (mode: Mode) => void` appelée à chaque changement de `mode`. `Mode`
  est maintenant exporté. Nécessaire car `LeftNavRail` vit en dehors de ce composant (monté depuis
  `HomeClient`) et ne peut pas atteindre `modeRef` directement ; lever entièrement l'état `Mode` dans
  `HomeClient` a été écarté — trop de refs/timers/listener wheel internes sont couplés à `mode` dans
  `HomeMapSection` pour le déplacer sans risque.
- `app/_components/LeftNavRail.tsx` (nouveau) : composant client, pilule fixe `hidden md:flex` (desktop
  uniquement — le menu burger `MobileNavMenu` existant couvre déjà le mobile), 4 boutons dans l'ordre
  Carte / Accueil / Bibliothèque / Offres : `FranceMapIcon`, une icône custom dont le tracé SVG (fourni
  par Vincent, `france-contour.svg`) est repris tel quel — recoloré en `currentColor` pour suivre les
  mêmes états idle/hover/actif que les autres icônes plutôt que le contour blanc d'origine, et avec une
  épaisseur de trait (`strokeWidth="14.67"` sur un viewBox `176`) calculée pour rendre le même trait
  physique que les icônes lucide (`strokeWidth="2"` sur viewBox `24` : `2/24 === 14.67/176`) ; `FileText`
  (lucide) pour l'accueil/CV ; `LayoutGrid` (lucide) pour la bibliothèque ; une icône custom « grand
  rectangle à gauche + 3 lignes à droite » pour les offres (mirroring la mise en page réelle de
  `CVDetailSection`). Couleurs via tokens du thème uniquement : idle `text-muted`, hover `text-strong`,
  actif `text-accent` (le hover reste blanc en dark et redevient noir-92% en light — volontaire, un blanc
  pur forcé casserait le thème clair). Fond de la pilule en `bg-scrim` (`rgba(0, 0, 0, 0.40)` dans les
  deux thèmes, token déjà existant) pour un rendu sombre et quasi transparent, pilule étroite et allongée
  (`px-1 py-6 gap-5`). Boutons `disabled` (pas seulement grisés) quand la page n'existe pas encore (carte
  hors connexion, bibliothèque/offres sans CV) — `disabled` supprime aussi tout effet `:hover`,
  comportement natif du navigateur et non un bug.
- `HomeClient.tsx` : rendu `<LeftNavRail>` (pas dans `layout.tsx` — la pilule a besoin d'un état qui
  n'existe que dans cet arbre, et les 4 destinations n'existent que sur `/`, contrairement à
  `MobileNavMenu` qui reste joignable depuis `/profile`/`/feedback`). Nouvel état `mode` (peuplé par
  `onModeChange`) et `activeSection` (`"home" | "library" | "cv-detail"`), ce dernier piloté par un
  `IntersectionObserver` (root = nouveau `mainRef` sur le conteneur de scroll-snap, threshold 0.5) et non
  par le dernier clic — un défilement manuel à la molette doit aussi faire bouger le surlignage actif.
  Trois nouveaux handlers pour la pilule : `handleGoHome` (sort du mode carte si besoin puis scroll vers
  `#home`), `handleGoMap` (scroll puis `enterMap()`, no-op interne si non connecté), `handleGoLibrary` ;
  `onGoOffers` réutilise le `handleScrollToDetail` existant.
- Décalage de mise en page : `md:ml-24` ajouté directement sur les 3 sections racines (`#home` dans
  `HomeMapSection.tsx`, `#library` dans `LibrarySection.tsx`, `#cv-detail` dans `CVDetailSection.tsx`).
  Un `margin-left` (pas un `padding-left`) a été choisi délibérément : sur un élément `position: relative`
  qui sert de containing block à des enfants `absolute inset-0`, seul le margin déplace réellement la
  boîte (et donc le containing block) — un padding aurait laissé les enfants absolus non décalés pendant
  que le contenu en flux normal bougeait, désynchronisant les deux. Aucune modification nécessaire dans
  `OrbitAnimation.tsx` : son `ResizeObserver` sur le canvas recalcule déjà `CX = W / 2` à chaque
  changement de taille du conteneur, donc le canvas se recentre tout seul dans la boîte rétrécie.
- `CVDetailSection.tsx` : colonne CV `lg:w-[38%] lg:shrink` → `lg:w-1/2 lg:shrink-0`, pour la demande
  explicite de Vincent (« page coupée en 2 de façon égale ») — la colonne de droite (`flex-1`) occupe déjà
  automatiquement l'autre moitié.

### Vérification

- `npx tsc --noEmit` : propre.
- `npx eslint` sur tous les fichiers touchés : propre.
- `npx jest` (`JobFinder/frontend`) : 17 suites / 156 tests passés, sans régression.
- Vérification manuelle dans le navigateur à chaque itération (serveur de dev sur le port 3000) :
  - Non connecté : la pilule affiche l'icône Accueil active en bleu, les 3 autres grisées et `disabled`
    (carte : non connecté ; bibliothèque/offres : pas de CV) — vérifié via les styles calculés
    (`getComputedStyle`), pas seulement visuellement.
  - Test 375px (iframe injectée same-origin, technique validée sur la PR #203) : la pilule est bien
    `display: none`, le menu burger mobile reste fonctionnel, aucun scroll horizontal
    (`scrollWidth === clientWidth`).
  - Connecté (session Google existante, compte réel avec CVs déjà en bibliothèque) : clic sur l'icône
    Carte → la carte de France apparaît en plein écran et l'icône passe au bleu ; clic sur l'icône
    Accueil → retour à l'écran d'import de CV, carte floutée derrière ; clic Bibliothèque → défilement
    vers la grille de CV, icône bibliothèque activée automatiquement (IntersectionObserver) ; clic Offres
    → défilement vers `#cv-detail`, colonnes mesurées à 1104.5px chacune de part et d'autre (split 50/50
    exact dans la largeur restante après la pilule).
  - Tracé `FranceMapIcon` : un premier tracé approximatif (à la main) jugé pas assez reconnaissable par
    Vincent a été remplacé par le tracé exact qu'il a fourni (`france-contour.svg`, path recopié tel quel,
    seule la couleur a changé).

Passage doc-writer : commentaire au-dessus de `enterMap` (`HomeMapSection.tsx`) corrigé — n'énumérait
encore que trois déclencheurs (molette, pilule tactile, indice de scroll), cette PR ajoute `LeftNavRail`
comme quatrième ; explication margin-vs-padding du `md:ml-24` complétée sur place, au même endroit.

Aucune remarque non-bloquante en attente.

---

## PR #230 — chore: supprimer la queue Service Bus `match-ready` sans consommateur

**Date :** 2026-07-25
**Branche :** `chore/remove-match-ready-queue` → `dev`

### Contexte

PR 1/6 du plan "notifications" (recap email des nouvelles offres par CV, décidé avec Vincent le
2026-07-25 — voir `docs/BACKLOG.md` et les entretiens précédents pour le reste du plan, hors périmètre
de cette tâche). Prompt détaillé préparé avec Claude Cowork :
`docs/prompts/prompt-remove-match-ready-queue.md`.

La queue `match-ready` (`envs/dev/servicebus.tf`) a été créée pour un design abandonné : le plan initial
(`docs/ROADMAP.md:168-172`, M2) prévoyait `job-matching → match-ready → job-cv-review → notification
utilisateur`. Le `job-cv-review` a été remplacé par la table `match_analyses` / la queue
`match-analysis` (voir `docs/adr/ADR-018-monetization-architecture.md`) — mais `agents/matching/main.py`
continuait à publier un message (résumé agrégé du run : `run_date`, `cvs_processed`, `new_matches`,
`offers_available`, sans `user_id`/`cv_id`) que personne n'a jamais consommé. `docs/BACKLOG.md` documentait
déjà le symptôme dans un item `[optional]` dédié (27 messages actifs / 26 en DLQ constatés le 08/07),
retiré par cette même PR (voir "Ce qui a été fait" ci-dessous).

### Ce qui a été fait

- `envs/dev/servicebus.tf` : retrait de `"match-ready"` de la liste `queues` et de la ligne
  correspondante dans le commentaire d'en-tête.
- `agents/matching/main.py` : retrait de la constante `MATCH_READY_QUEUE` et de l'appel `send_message`
  associé. `cvs_processed`/`new_matches`/`offers_available` restent utilisées juste après par
  `logger.info("matching_run_completed", ...)` — aucune variable devenue orpheline.
- `docs/BACKLOG.md` : suppression de l'item résolu (`[optional] match-ready sans consommateur`).
  `README.md` mis à jour aussi (liste des queues planifiées, non mentionné dans le prompt d'origine mais
  doc vivante, pas historique).
- Historique volontairement laissé tel quel (hors périmètre) : section `[SUPERSEDED]` de
  `docs/BACKLOG.md:147-172`, toutes les mentions dans `docs/JOURNAL.md`/`docs/adr/`, et `docs/ROADMAP.md`
  — snapshot de planification daté du 2026-05-18, non maintenu depuis (M2 encore marqué "🎯 en cours",
  items `[ ]` jamais cochés aux lignes 216/222/228, milestone AKS abandonné par ailleurs) : traité comme
  un document historique au même titre que les ADRs, pas comme la doc vivante que sont `README.md`/
  `docs/BACKLOG.md`.

### Vérification

- `pytest JobFinder/python` (suite complète) : 376 passés, aucune régression.
- `terraform fmt -check` et `terraform validate` sur `envs/dev` : propres.
- `terraform plan` sur `envs/dev` : un seul destroy imputable à cette PR
  (`module.servicebus.azurerm_servicebus_queue.this["match-ready"]`) ; les autres diffs affichés
  (VM jumpbox, container apps, action group) existent déjà à l'identique sur `dev` non modifié — vérifié
  par un plan comparatif avant/après stash des changements de cette branche, drift préexistant hors
  périmètre.
- `grep -rn "match-ready\|MATCH_READY_QUEUE"` sur tout le repo : plus aucune référence dans du code ou de
  la doc vivante, seulement dans l'historique (`docs/JOURNAL.md`, `docs/adr/`, section `[SUPERSEDED]` de
  `docs/BACKLOG.md`, et `docs/ROADMAP.md` traité comme historique — voir "Ce qui a été fait" ci-dessus).

Passage doc-writer : `README.md` avait bien retiré `match-ready` de la liste des queues mais avait laissé
`offer-fetch-request` absent de la même liste (les 4 queues réelles de `envs/dev/servicebus.tf` sont
`start-matching`, `cv-analysis`, `match-analysis`, `offer-fetch-request`) — corrigé sur place. Docstring de
module de `agents/matching/main.py` complétée (un résumé d'une ligne suivi d'une ligne vide et des
guillemets fermants — reliquat de la suppression de la phrase décrivant l'ancien post `match-ready`) pour
décrire fidèlement le comportement actuel (consomme `start-matching`, purge les matchs obsolètes, enfile
le top-N sur `match-analysis`).

Aucune remarque non-bloquante en attente.

---

## PR #231 — feat: préférence de notification_days sur le profil (PR 2/6 du plan notifications)

**Date :** 2026-07-26
**Branche :** `feat/profile-notification-days` → `dev`

### Contexte

Deuxième PR d'un plan en 6 étapes visant à envoyer, par email, un récapitulatif périodique des nouvelles
offres correspondant à chaque CV d'un utilisateur. Cette PR ne fait qu'ajouter le stockage de la
préférence et son réglage dans l'UI profil — quels jours de la semaine (ISO 8601, 1=lundi ... 7=dimanche)
l'utilisateur souhaite recevoir ce récap. Aucun email n'est envoyé à ce stade : l'agent de notification
planifié qui lira ce champ est la PR 6/6 du plan, pas encore construite. Tableau vide = notifications
désactivées, pas de booléen séparé.

### Ce qui a été fait

- **`shared/models.py`** : nouvelle colonne `notification_days: Mapped[list[int]]` sur `UserProfile`
  (`ARRAY(SmallInteger)`, `nullable=False`, défaut `[7]`), juste après `commune_codes`.
- **Migration 033** (`down_revision="032"`) : ajoute la colonne avec `server_default="{7}"` pour
  initialiser les profils existants sur « dimanche uniquement ».
- **`profile_defaults.py`** : `default_profile_values()` inclut désormais `notification_days: [7]` pour
  tout profil neuf (upload CV, PUT ou GET créant paresseusement la ligne).
- **`schemas.py`** : `ProfileUpdate.notification_days` typé `list[Literal[1..7]] | None`, avec un
  `field_validator` qui déduplique et trie ; `ProfileOut.notification_days: list[int]` ajouté à la réponse.
- **`routers/profile.py`** : un `null` explicite dans le body PUT est normalisé en `[]` (colonne NOT NULL,
  même traitement que `commune_codes`) ; le chemin INSERT de l'upsert utilise
  `updated.get("notification_days", [7])` et non `... or []`.
- **Frontend** : `ProfileData.notification_days: number[]` (`lib/api/types.ts`) ; nouveau composant
  `NotificationDaysToggle.tsx` (multi-sélection des jours, calqué sur `ExperienceToggle.tsx`) ; nouveau
  bloc « Notifications » sur `/profile`, entre les crédits d'analyse et le bloc Expérience, qui partage le
  bouton « Enregistrer » et l'appel PUT existants du bloc Expérience plutôt que d'avoir les siens.
- **Tests** : 6 cas nouveaux/mis à jour dans `test_webapp_profile.py` (défauts, non-interférence d'un PUT
  partiel avec le recalcul d'intention, désactivation par tableau vide, piège du défaut à l'INSERT),
  validation `Literal` + dédup/tri dans `test_schemas.py`, 5 cas pour `NotificationDaysToggle.test.tsx`.

### Décisions techniques

- **`updated.get("notification_days", [7])` plutôt que `... or []`** : un PUT partiel qui ne mentionne pas
  `notification_days` (ex. ne modifie que `commune_codes`) doit conserver le défaut `[7]` sur le chemin
  INSERT (nouveau profil) ; `... or []` aurait confondu « clé absente de la requête » avec « clé présente
  et vide » (opt-out explicite), écrasant le défaut sur tout PUT partiel qui ne cite pas le champ. Commenté
  in situ dans le router, testé explicitement.
- **`[]` = désactivé, pas de booléen séparé** : un utilisateur qui décoche tous les jours n'a simplement
  aucun jour dans le tableau — évite un état incohérent où un flag `enabled=true` coexisterait avec un
  tableau vide.
- **Bouton « Enregistrer » partagé avec le bloc Expérience** : décision produit délibérée pour éviter un
  second aller-retour réseau et un second bouton sur la même page.
- **Entiers ISO 8601 (`isoweekday()`)** plutôt qu'un mapping de noms de jours : le futur agent de
  notification (PR 6/6) comparera directement `datetime.now().isoweekday()` au tableau, sans table de
  correspondance.

### Vérification

- Backend : suite pytest complète verte (370 passed).
- Frontend : suite jest complète verte (161 passed), `npm run build` sans erreur TypeScript.
- Migration : la chaîne Alembic résout bien 033 comme head ; DDL compilé isolément et inspecté
  (`SMALLINT[] DEFAULT '{7}' NOT NULL`).
- Vérification manuelle sur serveur de dev (connexion via session Google) : interaction du toggle,
  round-trip d'enregistrement contre le backend de dev réel (qui n'a pas encore cette colonne — confirmé
  ignoré silencieusement côté serveur, sans erreur), et vérification responsive à 375px (iframe injectée).

Passage doc-writer : commentaire WHY ajouté au-dessus du `field_validator _dedupe_sort_days`
(`schemas.py`) — absent jusqu'ici, alors que les autres validators du même fichier en portent un ; le
reste (commentaires sur `notification_days` dans `models.py`, docstring de la migration 033, commentaire
du piège `insert_values` dans `routers/profile.py`, docstring de `default_profile_values`) était déjà
présent et fidèle au comportement actuel, aucune correction nécessaire.

### Reviewers

- **reviewer-infra** : APPROUVÉ. Remarque initiale (rien ne borne `notification_days` à 1-7 au niveau
  base) traitée en ajoutant `ck_user_profiles_notification_days` (même pattern que `ck_cvs_status`,
  migration 010) à la migration 033. Deux remarques de suivi sur cette contrainte (tableau vide
  autorisé, doublons non empêchés) confirmées comme des états métier voulus (`[]` = désactivé) et déjà
  neutralisés en amont (dédup/tri dans `ProfileUpdate`) — verdict final : aucune remarque non-bloquante.
- **reviewer-backend** : APPROUVÉ. Une remarque non-bloquante maintenue délibérément : `put_profile`
  (`routers/profile.py:130-287`) dépasse le seuil de 40 lignes du skill, mais c'est une dette
  préexistante (~120 lignes avant cette branche) que les ~9 lignes ajoutées par cette PR n'aggravent
  pas — traitement dans un futur refactor dédié, hors périmètre de cette tâche.
- **reviewer-frontend** : APPROUVÉ. Deux remarques corrigées directement (accessibilité :
  `role="group"` + `aria-label` sur le groupe de boutons de `NotificationDaysToggle.tsx` ; documentation :
  ligne ajoutée dans `__tests__/README.md` pour le nouveau fichier de test). Une remarque non-bloquante
  maintenue délibérément, même raisonnement que reviewer-backend : `page.tsx` (~247 lignes, 5+
  préoccupations mélangées) est une dette préexistante que cette PR ne fait qu'étendre en suivant le
  pattern d'extraction déjà en place pour `ExperienceToggle`.

---

## PR #232 — feat(openai): rôle Cognitive Services OpenAI User pour la UAMI caj + variable local_auth_enabled

**Date :** 2026-07-26
**Branche :** `feat/openai-managed-identity-rbac` → `dev`

### Contexte

Rattachée au plan "notifications" (décidé avec Vincent le 2026-07-25/26) ; le décompte total du plan a
bougé (6 → 7 PR, voir le prompt Cowork `prompt-openai-rbac-role.md`, hors de ce repo — le rôle RBAC pour
la future ressource Azure Communication Services Email ne peut être posé qu'une fois cette ressource
créée, donc il devient sa propre PR après la 5) et n'est pas figé à ce stade. `docs/BACKLOG.md:394-406`
liste l'item hardening "Passer `local_auth_enabled = false` + Managed Identity sur OpenAI" en 4 étapes ;
cette PR pose les étapes 2
(assigner le rôle `Cognitive Services OpenAI User` à la UAMI `caj`) et 4 (exposer `local_auth_enabled`
comme variable du module) — sans toucher aux étapes 1 (flip `local_auth_enabled = false`) et 3 (retrait
des secrets `openai-api-key`), qui restent des PR ultérieures du plan. Cette PR ne bascule donc rien :
l'authentification par clé API reste active partout, `local_auth_enabled` garde sa valeur par défaut
`true`.

### Ce qui a été fait

- `modules/openai/variables.tf` : nouvelle variable `local_auth_enabled` (bool, default `true`), avec une
  description qui pointe vers l'item BACKLOG et rappelle la condition du flip (une fois tous les
  consommateurs migrés vers Managed Identity).
- `modules/openai/main.tf` : `azurerm_cognitive_account.this` passe désormais
  `local_auth_enabled = var.local_auth_enabled` au lieu d'une valeur implicite.
- `envs/dev/openai.tf` : volontairement non touché — le module y est appelé sans le nouvel argument, donc
  le défaut (`true`) s'applique implicitement ; aucun diff fonctionnel sur le compte existant.
- `envs/lz_dev/rbac.tf` : nouveau bloc `data "azurerm_cognitive_account" "openai"` (lookup du compte créé
  dans `envs/dev`) + `azurerm_role_assignment.caj_openai_user`, rôle `Cognitive Services OpenAI User`,
  assigné à `azurerm_user_assigned_identity.caj` — même pattern que `caj_acr_pull` et
  `caj_servicebus_owner` déjà présents dans ce fichier.

### Décisions techniques

- Variable additive avec `default = true` : la RBAC atterrit avec zéro diff fonctionnel sur le compte
  OpenAI existant. Le flip vers `false` (et le retrait des secrets) est différé à une PR ultérieure du
  plan, une fois la RBAC en place et vérifiée.

### Vérification

- `terraform fmt -check` et `terraform validate` : propres sur `envs/dev` et `envs/lz_dev`.
- `terraform plan` sur `envs/dev` (avec un `alert_email` substitué localement, absent du tfvars
  gitignored) : grep confirme qu'`azurerm_cognitive_account.this` et
  `azurerm_cognitive_deployment.this[*]` n'apparaissent pas dans la liste des actions du plan — no-op
  confirmé. Les autres diffs affichés dans ce run (VM jumpbox, container apps, action group) sont un
  drift local préexistant causé par d'autres variables locales substituées, sans rapport avec cette PR.
- `terraform plan` sur `envs/lz_dev` (avec le vrai `sp_github_object_id`, récupéré via le diff
  "Refreshing state" d'un premier plan à variable factice) : réduit à exactement
  `Plan: 1 to add, 0 to change, 0 to destroy` — seul `azurerm_role_assignment.caj_openai_user` est créé,
  confirmé contre le compte réel `oai-jf-dev-frc` via la data source.
- Aucun `apply` effectué (CI-only, convention du projet). Vérification manuelle dans le portail (blade
  IAM du compte OpenAI, présence de l'identité `caj` avec le nouveau rôle) différée après merge + apply
  CI.

Passage doc-writer : `modules/openai/variables.tf` et `envs/lz_dev/rbac.tf` relus — la description de
`local_auth_enabled` porte déjà le WHY nécessaire (condition du flip + pointeur BACKLOG), et le nouveau
bloc `rbac.tf` suit exactement le pattern des blocs `caj_acr_pull`/`caj_servicebus_owner` existants (data
source + role_assignment, sans commentaire par bloc) ; le rationale "pourquoi lz_dev gère la RBAC
applicative" est déjà posé une fois dans l'en-tête du fichier (lignes 82-93). Rien à corriger — aucun
fichier Python n'est touché par cette PR (uniquement du Terraform).

Aucune remarque non-bloquante en attente.

---

## PR #233 — fix(frontend): masquer la barre de navigation latérale pour les visiteurs non connectés

**Date :** 2026-07-26
**Branche :** `feature/hide-navbar-unauthenticated` → `dev`

### Contexte

`LeftNavRail` (ajoutée en PR #229) s'affichait pour tout le monde, y compris les visiteurs non connectés :
l'icône Carte apparaissait grisée (`disabled`) via `mapAvailable={isAuthenticated}`, mais le reste de la
pilule (Accueil, Bibliothèque, Offres) restait visible. Incohérent avec le reste de l'expérience visiteur,
qui ne montre aucun élément de navigation propre aux utilisateurs connectés. Périmètre volontairement
limité à la pilule desktop (`LeftNavRail`) — le menu burger mobile (`MobileNavMenu`) n'est pas concerné.

### Ce qui a été fait

- **`HomeClient.tsx`** : tout le bloc `<LeftNavRail>` est désormais conditionné à `isAuthenticated && (...)`
  plutôt que de laisser le composant s'afficher avec des icônes partiellement grisées. `mapAvailable={isAuthenticated}`
  simplifié en raccourci JSX `mapAvailable` (toujours vrai maintenant que tout le bloc n'est rendu que
  connecté), même style que le raccourci déjà utilisé sur la prop `available` dans `LeftNavRail.tsx`.
- **`__tests__/HomeClient.test.tsx`** (nouveau) : première couverture de test pour `HomeClient`. Deux cas —
  la pilule est absente quand `useIsAuthenticated()` renvoie `false`, présente quand elle renvoie `true`.
  Mocks `@azure/msal-react`, `@/lib/api/client`, et stub des sections lourdes (`HomeMapSection`,
  `LibrarySection`) pour isoler le comportement testé.

### Vérification

- `npx tsc --noEmit` : propre.
- `npx eslint` : propre.
- `npx jest` (`JobFinder/frontend`) : suite complète verte, sans régression.
- Deux passages `reviewer-frontend` : verdict final APPROUVÉ, aucune remarque non-bloquante.
- Vérification manuelle sur serveur de dev : visiteur non connecté → aucune pilule visible ; connecté →
  pilule affichée comme avant.

Passage doc-writer : commentaire WHY ajouté au-dessus du bloc `{isAuthenticated && (...)}` dans
`HomeClient.tsx` — explique pourquoi la pilule est entièrement masquée plutôt que partiellement grisée
comme avant cette PR. Aucune autre correction nécessaire dans les deux fichiers touchés.

---

## PR #234 — feat(openai): bascule Azure OpenAI en Managed Identity (PR 4/7 du plan notifications)

**Date :** 2026-07-26
**Branche :** `feat/openai-managed-identity-flip` → `dev`

### Contexte

PR 4/7 du plan "notifications" (recap email des nouvelles offres par CV + migration RBAC OpenAI,
décidé avec Vincent le 2026-07-25/26). La PR 3/7 (#232) a posé le rôle `Cognitive Services OpenAI
User` pour la UAMI partagée `caj` et ajouté la variable additive `local_auth_enabled` (toujours à
`true` par défaut, sans effet). Cette PR bascule réellement l'authentification : `local_auth_enabled
= false` sur le compte OpenAI, suppression du secret Key Vault `openai-api-key`, et migration des 3
vrais clients Python vers l'auth par token Azure AD.

Découverte en préparant cette tâche : `job_matching` n'utilise pas du tout Azure OpenAI (confirmé par
`grep -in "embed|openai" agents/matching/main.py` — uniquement des lectures SQL de colonnes
`embedding` déjà calculées). `container_apps.tf` lui injectait quand même les secrets/env vars
OpenAI — un reliquat de l'ancien pipeline de distillation/reranking LLM (retiré via
`prompt-remove-offer-distillation.md`, `prompt-matching-remove-lexical-bonus.md`). Cette PR retire
cette configuration entièrement pour `job_matching`, pas de bascule puisqu'il n'y a rien à basculer.

### Ce qui a été fait

- `envs/dev/openai.tf` : `local_auth_enabled = false` sur `module "openai"` ; suppression du bloc
  `module "secret_openai_key"`. `module "secret_openai_endpoint"` conservé (l'endpoint n'est pas
  sensible) — noté ci-dessous comme piste de nettoyage hors périmètre.
- `envs/dev/container_apps.tf` : retrait de `local.openai_api_key` (locals), et des entrées
  `secrets`/`env_vars` `openai-api-key`/`AZURE_OPENAI_API_KEY` sur `job_offer_fetching`,
  `job_cv_analysis`, `job_match_analysis` (`AZURE_OPENAI_ENDPOINT` conservé, déjà en valeur directe
  non secrète). `job_matching` : retrait complet des deux secrets et des deux env vars OpenAI
  (`openai-api-key`, `openai-endpoint`), agent confirmé non-consommateur.
- `envs/dev/webapp.tf` : même retrait (`openai-api-key` secret + `AZURE_OPENAI_API_KEY` env var),
  `AZURE_OPENAI_ENDPOINT` et `AZURE_CLIENT_ID` conservés.
- `shared/embedder.py`, `agents/cv_analysis/main.py`, `agents/match_analysis/main.py` : remplacement
  de la construction `AzureOpenAI(api_key=...)` par `DefaultAzureCredential` +
  `get_bearer_token_provider(..., "https://cognitiveservices.azure.com/.default")`, suivant l'exemple
  officiel du SDK (`openai/openai-python`, `examples/azure_ad.py`). `agents/offer_fetching/main.py`
  n'a pas de client OpenAI propre (consomme via `shared.embedder.embed()`) — seul son docstring
  d'en-tête listant les variables d'environnement attendues a été mis à jour.
- `python/tests/conftest.py` : retrait du stub `AZURE_OPENAI_API_KEY` de `_ENV_STUBS`, plus aucun
  module ne le lit.
- `python/.env.example`, `python/scripts/jumpbox_env.sh` : nettoyage des références résiduelles à
  `AZURE_OPENAI_API_KEY` (hors périmètre strict du prompt, mais references directement rendues
  fausses par cette PR). `jumpbox_env.sh` ne va plus chercher le secret KV supprimé.

### Décisions techniques

- `module "secret_openai_endpoint"` semble inutilisé (aucun `data "azurerm_key_vault_secret"` ne le
  relit — tous les consommateurs utilisent `module.openai.endpoint` directement) mais n'est pas
  retiré ici, hors périmètre de cette PR ; à considérer pour un futur nettoyage.
- Aucun rôle "Cognitive Services OpenAI User" n'est actuellement accordé à un principal
  interactif (vérifié via `az role assignment list --assignee` sur l'utilisateur Vincent — Owner au
  niveau subscription, mais `Owner` a `dataActions: []`, donc aucun accès data-plane implicite).
  Seule la UAMI `caj` (Container App Jobs + webapp) porte ce rôle. Aucun script jumpbox n'appelle
  Azure OpenAI aujourd'hui, donc ce n'est pas une régression de cette PR — mais un futur script de
  diagnostic qui appellerait l'API directement depuis le jumpbox aurait besoin d'un rôle dédié.

### Vérification

- `pytest JobFinder/python/tests/ -v` : 370 passed.
- `terraform fmt -check` et `terraform validate` : propres sur `envs/dev`.
- `terraform plan` sur `envs/dev` (avec un `alert_email` substitué localement, absent du tfvars
  gitignored) : `azurerm_cognitive_account.this` montre `local_auth_enabled: true -> false` en
  **mise à jour en place** (pas de replace) — condition d'arrêt du prompt validée. Destruction du
  secret KV `openai-api-key` et mises à jour en place sur les Container App Jobs/webapp concernés,
  conformes à l'attendu. Les diffs affichés sur `module.jumpbox` (VM + schedule), l'action group, et
  `module.frontend` sont un drift préexistant sur des fichiers non touchés par cette PR — sans
  rapport.
- Aucun `apply` effectué (CI-only, convention du projet). Vérification manuelle post-merge des 4
  chemins touchés (cv_analysis, match_analysis, embedder via offer_fetching et webapp/profile) et
  confirmation `job_matching` inchangé, différées après merge + apply CI.

Passage doc-writer : `shared/embedder.py`, `agents/cv_analysis/main.py`, `agents/match_analysis/main.py`
— commentaire WHY ajouté au-dessus de chaque `get_bearer_token_provider(DefaultAzureCredential(), ...)`,
absent jusqu'ici dans les trois fichiers : la construction ne fait ni I/O ni résolution d'identité (la
chaîne de credential n'est parcourue qu'au premier appel réel), ce qui tranche avec
`AZURE_OPENAI_ENDPOINT` juste au-dessus qui lève un `ValueError` fail-fast au chargement du module — sans
ce commentaire, la tension entre les deux lignes voisines n'est pas évidente, et c'est précisément ce qui
permet aux imports de ces modules de rester sans erreur sous pytest sans identité Azure disponible
(confirmé : les tests patchent `_openai_client.chat.completions.create`, jamais la construction du
client). `agents/offer_fetching/main.py` : docstring d'en-tête déjà à jour (mentionne l'auth via Managed
Identity côté `shared.embedder`), rien à corriger. Les trois docstrings de module (`embedder.py`,
`cv_analysis/main.py`, `match_analysis/main.py`) ne mentionnaient pas le mode d'authentification et n'ont
donc pas eu besoin d'édition. `python/scripts/jumpbox_env.sh` porte déjà, depuis cette même PR, le
commentaire WHY sur l'absence de rôle `Cognitive Services OpenAI User` pour un principal interactif —
rien à ajouter.

En vérifiant la portée de la bascule au-delà des fichiers listés dans "Ce qui a été fait" : trouvé
`.github/workflows/buildAgents.yml` (step "Smoke-test webapp image") avec un commentaire devenu faux —
"shared/embedder.py reads AZURE_OPENAI_API_KEY at module level and raises ValueError if absent" ne
correspond plus au code depuis cette PR. Corrigé pour refléter l'auth par Managed Identity actuelle et
noter que la ligne `-e AZURE_OPENAI_API_KEY=x` du smoke-test est un reliquat inoffensif (jamais lu par
l'image) plutôt que de le laisser induire en erreur un futur lecteur. Fichier YAML de workflow, hors
périmètre `.tf`/`.sql`/`.ps1` de l'exclusion de ce rôle, donc traité directement plutôt que signalé à
`reviewer-infra`. `docs/BACKLOG.md:39` référence aussi `AZURE_OPENAI_API_KEY`, mais dans l'instantané figé
du plan original de PR #86 (M4 PR1), déjà divergent sur d'autres points sans jamais avoir été mis à jour
depuis : traité comme un historique, pas une description de l'état actuel, donc non corrigé.

Non vérifié faute d'accès Bash dans ce passage : le chiffre « 370 passed » n'a pas été rejoué (cohérent
avec les 370 déjà rapportés en sortie de PR #231, et PR #232 ne touchait aucun fichier Python entre les
deux — donc plausible par continuité, pas confirmé indépendamment). Numéro de PR #234 non plus vérifié
via `gh` (indisponible dans ce passage) — hérité tel quel de l'entête déjà écrite ; à recontrôler avant
`gh pr create` si une autre PR a pu prendre ce numéro entre-temps.

Les deux points signalés par doc-writer ont été revérifiés côté Claude Code après son passage :
`pytest JobFinder/python/tests/ -v` rejoué (370 passed, inchangé après les commentaires WHY ajoutés)
et `gh pr list --state all --limit 3` confirme que #233 est déjà pris (mergée), #234 est donc bien le
prochain numéro disponible. `.github/workflows/buildAgents.yml` : la ligne `-e AZURE_OPENAI_API_KEY=x`
signalée comme reliquat inoffensif par doc-writer a été retirée (plus aucune image ne la lit).

Aucune remarque non-bloquante en attente.

---

## PR #235 — feat(dev): provisionner la ressource email Azure Communication Services

**Date :** 2026-07-26
**Branche :** `feat/acs-email-resource` → `dev`

### Contexte

PR 5/7 du plan "notifications" (recap email des nouvelles offres par CV, décidé avec Vincent le
2026-07-25/26). Cette PR provisionne uniquement la ressource d'envoi d'email — pas de RBAC (PR 6/7,
doit venir après puisqu'un `azurerm_role_assignment` a besoin que sa cible existe déjà), pas d'agent
consommateur (PR 7/7). Rien n'envoie encore d'email à l'issue de cette PR.

Décision produit actée avec Vincent : domaine personnalisé (`vincentboutin.dev`), pas de domaine géré
par Azure. Adresse d'expéditeur : `jobfinder@vincentboutin.dev`. Vincent gère déjà le DNS de ce domaine
pour ce même projet (`frontend_custom_domain`, PR #191) — la propriété du domaine n'est donc pas un
obstacle, seulement une étape manuelle après cette PR.

### Ce qui a été fait

- **`envs/dev/variables.tf`** : deux nouvelles variables, `notification_sender_domain` (défaut
  `vincentboutin.dev`) et `notification_sender_username` (défaut `jobfinder`), sur le modèle de
  `frontend_custom_domain`.
- **Nouveau module `modules/email_communication/`** : 5 ressources —
  `azurerm_communication_service` (parent, hostname = endpoint du SDK `EmailClient`, futur scope RBAC
  de la PR 6/7), `azurerm_email_communication_service`, `azurerm_email_communication_service_domain`
  (`domain_management = "CustomerManaged"` — Azure ne touche pas au DNS, la preuve de propriété passe
  par les enregistrements exposés en sortie), `azurerm_email_communication_service_domain_sender_username`
  (partie locale `jobfinder`), et `azurerm_communication_service_email_domain_association` (lie le
  domaine vérifié à la ressource parente). `azurerm_communication_service` et le domaine portent
  `prevent_destroy = true` + `protect = "true"` — une destruction accidentelle du domaine imposerait de
  refaire la vérification DNS manuelle, pas juste un nouvel apply.
- **`envs/dev/email_communication.tf`** : nouveau fichier, appelle le module avec
  `data_location = "France"` (cohérent avec la position RGPD déjà actée du projet, ADR-006).
- **`envs/dev/outputs.tf`** : deux nouvelles sorties, `email_verification_records` (les enregistrements
  DNS à ajouter manuellement chez l'hébergeur de `vincentboutin.dev` — Domain, DKIM, DKIM2, SPF, DMARC)
  et `email_sender_address`.

### Décisions techniques

- Schéma confirmé via la doc officielle du provider `azurerm` (~> 4.0, verrouillé 4.72.0) : 5 ressources,
  aucune n'a de rôle RBAC à poser dans cette PR.
- Bug connu côté provider (`hashicorp/terraform-provider-azurerm#29731`) : `verification_records[].dmarc`
  peut revenir vide selon l'état de l'API Azure au moment de l'apply sur certaines versions 4.x. Si
  constaté après merge, récupérer la valeur manuellement sur le portail Azure (IAM du domaine) plutôt que
  de déboguer le provider — les 4 autres enregistrements (Domain, DKIM, DKIM2, SPF) ne sont pas concernés.
- La vérification du domaine n'est pas instantanée et ne fait pas partie de cette PR : le domaine reste
  `NotVerified` tant que les enregistrements DNS ne sont pas ajoutés manuellement, avec un délai de
  propagation non garanti. Ce n'est pas un critère de blocage pour cette PR.

### Vérification

- `terraform fmt -check` et `terraform validate` : propres sur `envs/dev`.
- `terraform plan` sur `envs/dev` (avec un `alert_email` substitué localement, absent du tfvars
  gitignored) : grep confirme exactement 5 créations sous `module.email_communication` (les 5 ressources
  du module), aucune destruction et aucun changement sur des ressources existantes attribuables à cette
  PR. Les autres diffs affichés dans ce run (VM jumpbox, tags d'images de conteneurs, action group) sont
  un drift local préexistant causé par d'autres variables locales substituées ou absentes du tfvars
  gitignored, sans rapport avec cette PR.
- Aucun `apply` effectué (CI-only, convention du projet). Après merge + apply CI : `terraform output
  email_verification_records` à vérifier (Domain, DKIM, DKIM2, SPF non vides ; DMARC potentiellement vide,
  voir bug connu ci-dessus) — les enregistrements à recopier manuellement chez l'hébergeur DNS de
  `vincentboutin.dev` seront documentés dans la description de la PR pour que Vincent puisse les poser
  après merge. Passage à `Verified` dans le portail Azure vérifié séparément, hors CI (délai de
  propagation DNS variable).

Passage doc-writer : commentaire d'en-tête de `communication_email.tf` corrigé (référençait
`docs/prompts/prompt-*.md`, inexistant dans ce repo — les prompts Cowork vivent hors du repo). Toutes
les autres descriptions `variable`/`output` et commentaires WHY du module vérifiés exacts, rien d'autre
à corriger.

Premier passage `reviewer-infra` : verdict APPROUVÉ avec 3 remarques non-bloquantes, toutes traitées :
`azurerm_email_communication_service` ne portait ni `prevent_destroy` ni `protect = "true"` alors que sa
destruction force en cascade celle du domaine (même justification DNS que celle déjà invoquée pour
protéger le domaine) — protection ajoutée pour rester cohérent ; les `validation` de `domain_name` et
`sender_username` n'existaient qu'au niveau de l'appelant (`envs/dev/variables.tf`) — dupliquées au
niveau du module lui-même pour rester réutilisable sans dépendre d'un futur appelant discipliné ; le
fichier `communication_email.tf` renommé en `email_communication.tf` pour reprendre le nom du module à
l'identique, comme `servicebus.tf`/`openai.tf` le font pour leurs modules respectifs.

---

## PR #236 — feat(lz_dev): accorder à caj le rôle Communication and Email Service Owner

**Date :** 2026-07-26
**Branche :** `feat/acs-email-rbac` → `dev`

### Contexte

PR 6/7 du plan "notifications" (recap email des nouvelles offres par CV, décidé avec Vincent le
2026-07-25/26). PR 5/7 (`feat/acs-email-resource`, mergée — PR #235) a créé la ressource Azure
Communication Services Email (`acs-jf-dev-frc`, domaine personnalisé `vincentboutin.dev` vérifié).
Cette PR pose uniquement le rôle IAM permettant à `caj` d'envoyer des mails via cette ressource par
Managed Identity — aucun code applicatif touché. Le job consommateur (`agents/notifications`) est PR
7/7, hors périmètre ici, de même que le renommage de l'adresse expéditrice
(`jobfinder` → `jobfinder_donotreply`), reporté à PR 7 car c'est un changement `envs/dev` qui ne peut
pas être mélangé avec ce changement `lz_dev` (règle Git Flow du projet : une PR ne mélange jamais
platform et app).

### Ce qui a été fait

- **`envs/lz_dev/rbac.tf`** : nouveau bloc à la suite de `caj_openai_user`, même triptyque que les
  rôles `caj` existants — un `data "azurerm_communication_service"` pour retrouver la ressource créée
  dans `envs/dev` (invisible depuis le state `lz_dev` sans ce lookup), puis un
  `azurerm_role_assignment.caj_communication_owner` scopé dessus avec
  `principal_id = azurerm_user_assigned_identity.caj.principal_id` et
  `role_definition_name = "Communication and Email Service Owner"`.

### Décisions techniques

- Rôle choisi : `Communication and Email Service Owner` (GUID `09976791-48a7-449e-bb21-39d1a415f350`).
  Ce rôle n'est pas documenté noir sur blanc par Microsoft comme le minimum requis pour l'envoi de mail
  par Entra ID (la doc officielle mentionne des dataActions `acs.email.read`/`acs.email.write` sans
  préciser quel rôle intégré les porte) — un rôle custom à 2 permissions suffirait en théorie au strict
  nécessaire. Choisi quand même car c'est un vrai rôle intégré Azure confirmé (nom et GUID vérifiés via
  plusieurs sources tierces), et parce que ce projet privilégie déjà des rôles intégrés larges mais
  scopés à une seule ressource plutôt que des rôles custom sur-mesure (`caj_servicebus_owner` fait de
  même avec `Azure Service Bus Data Owner`). `terraform plan` confirme que `role_definition_name`
  résout sans erreur — pas besoin de chercher un nom alternatif.

### Vérification

- `terraform fmt -check` et `terraform validate` : propres sur `envs/lz_dev`.
- `terraform plan` sur `envs/lz_dev` (avec `sp_github_object_id` substitué localement via
  `az ad sp list --display-name sp-jf-github`, absent du tfvars gitignored) : une seule addition,
  `azurerm_role_assignment.caj_communication_owner`, aucun autre changement.
- `terraform plan` sur `envs/dev` : non rejoué avec de vraies valeurs (nécessite les secrets
  `ALERT_EMAIL`/`PORTFOLIO_CONTACT_FUNCTION_URL`, non disponibles localement, seulement en secrets
  GitHub Actions). Confirmé par un autre moyen tout aussi concluant : `git diff --stat` contre
  `origin/dev` ne montre que `envs/lz_dev/rbac.tf` modifié, aucun fichier sous `envs/dev` — un diff
  Terraform sur une couche ne peut pas changer si aucun fichier ni variable de cette couche n'a bougé.
  Confirmation supplémentaire via la CI (`terraformPlan.yml`, qui dispose des vrais secrets) à l'ouverture
  de la PR.
- Aucun `apply` effectué (CI-only, convention du projet). Après merge + apply CI : vérification
  différée sur le portail Azure (IAM de `acs-jf-dev-frc`, confirmer que `id-jf-dev-frc-caj` apparaît
  avec le rôle `Communication and Email Service Owner`). Pas de test applicatif possible dans cette PR
  (aucun agent n'utilise encore ce rôle — c'est PR 7/7).

---

## PR #237 — feat(offer-fetch): move offer fetch scheduler to a single 18:00 run

**Date :** 2026-07-26
**Branche :** `feature/fetch-schedule-18h` → `dev`

### Contexte

Le Container App Job `offer_fetch_scheduler` déclenchait un refresh complet des offres deux fois par
jour (12:00 et 20:00 heure de Paris). Cette PR passe à une seule exécution quotidienne, à 18:00 heure
de Paris.

### Ce qui a été fait

- **`envs/dev/container_apps.tf`, `servicebus.tf`** : `cron_expression` du module
  `job_offer_fetch_scheduler` passé de `"0 10,11,18,19 * * *"` (les 4 heures UTC couvrant 12h/20h
  Paris sous CET et CEST) à `"0 16,17 * * *"` (les 2 heures UTC couvrant 18h Paris sous CET/CEST).
  Commentaires (en-tête du module, section Service Bus) mis à jour en conséquence.
- **`agents/offer_fetch_scheduler/main.py`** : `SCHEDULED_LOCAL_HOURS` passé de `(12, 20)` à `(18,)`
  pour rester synchronisé avec le nouveau cron — c'est cette constante que `_is_scheduled_local_hour()`
  utilise pour no-oper la moitié des déclenchements UTC qui ne correspond pas à l'état DST courant ;
  un désalignement avec le cron Terraform ferait taire le job silencieusement.
- **`agents/offer_fetching/main.py`** : docstring de module mise à jour (décrit
  `offer_fetch_scheduler` comme un relais 18h, au lieu de 12h/20h).
- **`agents/cleanup/main.py`** : docstring de `_cleanup` mise à jour — la période de grâce avant
  purge d'une offre obsolète était formulée comme « 4 cycles de fetch consécutifs » sous la cadence
  2x/jour ; elle est maintenant « 2 cycles consécutifs » sous la cadence 1x/jour. La tolérance réelle
  sous-jacente (2 jours, `CLEANUP_COLLECTED_AGE_DAYS=2`) n'a pas changé, seul le compte de cycles
  dérivé de la fréquence de fetch change.
- **`tests/test_offer_fetch_scheduler.py`** : cas de test mis à jour pour la nouvelle heure planifiée
  unique (16 UTC → CEST, 17 UTC → CET, au lieu des anciennes paires 10/11 et 18/19).
- **`frontend/app/_components/LibrarySection.tsx`** : texte de la page Bibliothèque, « De nouvelles
  offres sont recherchées chaque jour à 12h et 20h pour chacun de vos CVs. » →
  « ...chaque jour à 18h... ».

### Vérification

- Lecture croisée cron ↔ code ↔ tests ↔ UI : `cron_expression = "0 16,17 * * *"` (container_apps.tf)
  correspond à `SCHEDULED_LOCAL_HOURS = (18,)` (offer_fetch_scheduler/main.py), aux cas de test à
  16 UTC (CEST) et 17 UTC (CET) de `test_offer_fetch_scheduler.py`, et au texte UI « 18h » de
  `LibrarySection.tsx`.
- `terraform fmt -check`/`validate`/`plan`, `pytest`, `eslint` : non rejoués dans cette passe
  documentation (hors périmètre de `doc-writer`) — à confirmer par `reviewer-infra`/`reviewer-backend`/
  `reviewer-frontend` et par la CI.

Passage doc-writer : `agents/cleanup/main.py`, la docstring de `_cleanup` attribuait la cadence
1x/jour 18h à « l'offer-fetching agent », alors que le docstring de module de
`agents/offer_fetching/main.py` (touché dans cette même PR) précise que cet agent est désormais
purement événementiel et ne connaît plus l'heure — la cadence planifiée appartient à
`offer_fetch_scheduler`. Reformulé pour attribuer correctement le déclenchement planifié à
`offer_fetch_scheduler` et clarifier que `offer_fetching` lui-même n'a pas d'horaire propre. Toutes
les autres docstrings/commentaires touchés par cette PR (`container_apps.tf`, `servicebus.tf`,
`offer_fetch_scheduler/main.py`, `offer_fetching/main.py` en-tête, `test_offer_fetch_scheduler.py`)
vérifiés exacts vis-à-vis du code actuel, rien d'autre à corriger. Recherche de résidus de l'ancien
horaire 12h/20h dans le reste du repo : seules des mentions historiques hors périmètre trouvées
(`docs/ROADMAP.md` — roadmap M2 figée décrivant un plan jamais implémenté tel quel, GitHub Actions au
lieu de Container App Jobs ; `docs/JOURNAL.md` — entrées passées, jamais réécrites rétroactivement ;
`migrations/versions/030_add_offer_fetch_coordination.py` — docstring de migration décrivant l'état
au moment de l'introduction du pattern événementiel, sans rapport avec cette PR) ; aucune ne relève
d'une correction ici.

---

## PR #238 — feat(agents): l'agent notifications (récap email des offres non vues)

**Date :** 2026-07-26
**Branche :** `feat/notifications-agent` → `dev`

### Contexte

PR 7/7 (et dernière) du plan "notifications" (décidé avec Vincent le 2026-07-25/26). Toutes les
briques précédentes étaient posées : `UserProfile.notification_days` (PR 2/7, mergée), la ressource
Azure Communication Services Email avec le domaine `vincentboutin.dev` vérifié (PR 5/7, mergée —
PR #235), et le rôle `Communication and Email Service Owner` accordé à `caj` par Managed Identity
(PR 6/7, mergée — PR #236). Cette PR ajoute le seul morceau qui manquait : l'agent qui envoie
réellement les mails.

Couche unique (`envs/dev`, pas de mélange platform/app), deux changements logiquement distincts
mais dans la même couche :
1. Le renommage de l'adresse expéditrice (`jobfinder` → `jobfinder_donotreply`), décidé le 2026-07-26
   et reporté ici exprès — `notification_sender_username` touche `envs/dev`, pas `lz_dev`, donc ne
   pouvait pas être fait dans PR 6.
2. Le nouvel agent `agents/notifications`, planifié à 19h heure de Paris (exigence de Vincent).

### Ce qui a été fait

- **`envs/dev/variables.tf`** : `notification_sender_username` par défaut passe de `jobfinder` à
  `jobfinder_donotreply` — force le remplacement de
  `azurerm_email_communication_service_domain_sender_username` uniquement (pas de nouvelle
  vérification DNS nécessaire, le domaine reste vérifié).
- **`python/agents/notifications/main.py`** (nouveau) : sélectionne les `UserProfile` dont
  `notification_days` contient le jour ISO 8601 courant (`.any(...)`, compilé côté PostgreSQL en
  `<valeur> = ANY(notification_days)`), compte en une seule requête batchée (évite un N+1 profil par
  profil, remarque de `reviewer-backend`) les matchs non vus (`Match.seen_at IS NULL`) par CV pour
  tous les profils sélectionnés d'un coup, puis envoie un mail récap listant chaque CV ayant au moins
  un match non vu. La session DB (`_load_recipients_and_counts`) est fermée avant la boucle d'envoi de
  mails, pour ne pas garder une connexion ouverte pendant des appels réseau potentiellement lents.
  N'écrit jamais `Match.seen_at` — colonne mise à jour exclusivement par l'utilisateur dans le webapp —
  donc une offre non vue reste dans le récap tant qu'elle n'a pas été vue dans l'app, y compris sur
  plusieurs envois. Auth par `DefaultAzureCredential` (identité `caj`, aucune clé). Suit le pattern
  DST-aware de `offer_fetch_scheduler` (`_is_scheduled_local_hour`, un seul horaire ici : 19h) et la
  structure générale de `cleanup` (migrations avant tout accès DB, logging structlog, résumé final,
  `try/except SQLAlchemyError` autour des requêtes).
- **`python/agents/notifications/Dockerfile`** (nouveau) : copie de celui d'`offer_fetch_scheduler`,
  seule la commande de démarrage change.
- **`python/requirements.txt`** : ajout de `azure-communication-email`.
- **`python/pytest.ini`** : ajout de `agents/notifications/tests` à `testpaths` — sans ça les
  nouveaux tests ne sont simplement jamais découverts par `pytest`.
- **`.github/workflows/buildAgents.yml`** : ajout du build/push de l'image `agents/notifications`
  (mêmes étapes que `offer-fetch-scheduler`) et de la mise à jour d'image du job
  `job-jf-dev-frc-notifications` — sans ça le nouveau Container App Job créé par Terraform
  référencerait une image jamais construite. Repéré par `reviewer-infra` (le workflow ne connaissait
  aucun des deux avant cette PR).
- **`envs/dev/monitoring.tf`** : ajout de `notifications = module.job_notifications.id` à
  `local.all_job_ids` — sans ça le nouveau job n'aurait pas d'alerte `job_execution_failed` dédiée
  (le commentaire du bloc dit explicitement d'ajouter les nouveaux jobs ici). Repéré par
  `reviewer-infra`. `job_offer_fetch_scheduler` manque encore à cette liste — dette préexistante,
  hors périmètre de cette PR (ce job n'est pas touché ici).
- **`envs/dev/container_apps.tf`** : nouveau module `job_notifications` (Container App Job, trigger
  `timer`, `cron_expression = "0 17,18 * * *"` — mêmes deux horaires UTC susceptibles de correspondre
  à 19h Paris selon l'heure d'été/hiver, exactement le même mécanisme que
  `job_offer_fetch_scheduler`). `replica_timeout_in_seconds = 300` (plus long que les 60s
  d'`offer_fetch_scheduler` : cet agent parcourt la table des profils et envoie potentiellement
  plusieurs mails de façon séquentielle).
- **`python/agents/notifications/tests/`** (nouveau) : `_is_scheduled_local_hour` (vrai pour 17h UTC
  en heure d'été / 18h UTC en heure d'hiver, faux sinon), construction du contenu du mail (fonction
  pure, y compris l'échappement HTML du nom de CV), comptage batché des matchs non vus par utilisateur
  (SQLite en mémoire, DDL minimal comme `cleanup`, y compris un cas à plusieurs utilisateurs pour
  vérifier que les comptes ne se mélangent pas), et l'orchestration de `main()` (hors fenêtre
  planifiée → rien n'est envoyé ; destinataire sans email → sauté et compté ; destinataire sans offre
  non vue → sauté sans envoi ; échec d'envoi individuel → compté dans `failed` sans interrompre la
  boucle sur les destinataires suivants). La sélection des profils par `notification_days.any(...)`
  n'est pas testable contre SQLite (type `ARRAY` non supporté) — testée en mockant `session.execute`
  directement, comme `cv_analysis`/`match_analysis` mockent déjà leur client OpenAI plutôt que l'API
  réelle.

### Décisions techniques

- **Pas de filtre par zone communale** : `GET /cv` (webapp) filtre `match_count`/`unseen_count` par la
  zone communale peinte par l'utilisateur (`commune_zone_condition`, package `webapp`). Cet agent ne
  réplique pas ce filtre : compte tous les matchs non vus par CV, sans filtre géographique. Deux
  raisons — aucun agent de ce repo n'importe le code d'un autre agent (`cleanup`, `matching`,
  `offer_fetch_scheduler` n'importent que `shared.*`), et `commune_zone_condition` vit dans `webapp`,
  pas `shared` (le déplacer serait un refactor hors périmètre). Conséquence : le chiffre du mail peut
  être légèrement supérieur à ce que l'utilisateur voit dans la bibliothèque CV pour les profils avec
  une petite zone peinte. À revisiter si ça devient une source de confusion réelle.
- Gestion d'erreur sur l'appel SDK : `azure.core.exceptions.AzureError` (base commune aux clients
  `azure-core`, déjà utilisée dans le repo pour le blob storage — `routers/cv.py`,
  `scripts/backfill_thumbnails.py`) plutôt qu'un `except Exception` nu, conformément à la convention
  Python du projet.
- **Comptage batché plutôt que par profil** : la première version comptait les matchs non vus par un
  `SELECT ... GROUP BY` exécuté une fois par profil dans la boucle d'envoi (N+1). `reviewer-backend` a
  demandé une requête unique sur `CV.user_id.in_(...)` groupée par `(user_id, cv_id, name)`, répartie
  en mémoire ensuite — corrigé dans `_count_unseen_matches_by_user`. Le même passage a ajouté le
  `try/except SQLAlchemyError` manquant autour des deux requêtes (`_load_recipients_and_counts`) et le
  `logger.info` d'entrée manquant sur le comptage, conformément à la convention Python du projet.
- **Échappement HTML du nom de CV** (`html.escape`) : `CV.name` est un texte libre saisi par
  l'utilisateur ; sans échappement, un nom contenant `<` ou `&` casserait le rendu HTML du mail —
  remarque non-bloquante de `reviewer-backend`, corrigée par prudence (sévérité faible : le
  destinataire est le propriétaire du CV).
- **`except (SQLAlchemyError, CommandError)` autour de `run_migrations()`** plutôt qu'un
  `except Exception` nu — `shared/db.py` documente exactement ces deux types dans son `Raises`,
  même forme que `cv_analysis/main.py`/`offer_fetching/main.py`. Repéré par `reviewer-backend` sur ce
  fichier neuf ; `cleanup/main.py` et `matching/main.py` portent encore l'ancien `except Exception`
  nu sur ce même appel — dette préexistante hors périmètre de cette PR, à traiter séparément.

### Vérification

- `terraform fmt -check` et `terraform validate` : propres sur `envs/dev`.
- `terraform plan` sur `envs/dev` (avec `az login` local + `-var alert_email=...` fourni en ligne de
  commande pour contourner l'absence de cette variable en local, non liée à cette PR) : le diff
  contient les changements attendus pour cette PR —
  `module.email_communication.azurerm_email_communication_service_domain_sender_username.this` remplacé,
  `module.job_notifications.azurerm_container_app_job.this` créé, et
  `azurerm_monitor_metric_alert.job_execution_failed["notifications"]` créé (ajout à `all_job_ids`).
  Le plan complet affichait aussi des changements sur `jumpbox`, `webapp`, l'action group d'alerte, et
  un écart d'image (`:<sha>` réel vs `:latest` désiré) sur plusieurs jobs existants non touchés par
  cette PR (`cleanup`, `cv-analysis`, `matching`, `match-analysis`, `offer-fetching`,
  `offer-fetch-scheduler`) : dérive préexistante, en partie causée par des variables
  (`portfolio_contact_function_url`, valeur réelle d'`alert_email`) absentes du `terraform.tfvars`
  local, en partie par un déploiement CI réel sur `dev` survenu entre deux exécutions locales de
  `plan` pendant cette session — confirmée sans rapport avec cette PR via `git diff --stat`, qui ne
  montre que `variables.tf`, `container_apps.tf`, et `monitoring.tf` modifiés sous `envs/dev`.
- `pytest` : 403 tests passent (21 pour `agents/notifications`), suite complète du repo.
- Pas de `ruff`/linter configuré dans le repo à ce jour (aucune config, aucune dépendance) — rien à
  exécuter sur ce point.
- Après merge et apply CI : vérifier dans le portail que `job-jf-dev-frc-notifications` existe,
  déclencher un run manuel (portail ou `az containerapp job start`) avec au moins un profil de test
  ayant `notification_days` incluant le jour du test et un match non vu — sinon le run se termine en
  no-op silencieux (comportement attendu).

### Correctif post-PR : CI `unitTests.yml` en échec (dépendance manquante)

`unitTests.yml` installe `agents/webapp/requirements.txt` (verrouillé par `pip-compile` à partir de
`agents/webapp/requirements.in`) pour lancer `pytest` sur tout `JobFinder/python` — pas le
`JobFinder/python/requirements.txt` racine édité plus haut dans cette PR, qui ne sert qu'aux
`Dockerfile` de chaque agent. `azure-communication-email` manquait donc à ce fichier verrouillé,
faisant échouer la collecte de `agents/notifications/tests/test_notifications.py` en CI
(`ModuleNotFoundError`) alors que la suite passait en local (venv différent, dépendance déjà
installée manuellement pendant le développement).

- **`agents/webapp/requirements.in`** : ajout de `azure-communication-email`.
- **`agents/webapp/requirements.txt`** régénéré via `pip-compile` : au passage, `pip-compile` a
  aussi ajouté tout l'arbre de dépendances transitives d'`azure-monitor-opentelemetry` (les paquets
  `opentelemetry-instrumentation-*`, `msrest`, `wrapt`, etc.) qui étaient absents du fichier
  verrouillé — celui-ci contenait la ligne `azure-monitor-opentelemetry==1.8.8` sans ses propres
  dépendances, signe qu'il avait été édité à la main plutôt que régénéré à l'introduction de ce
  paquet. Épinglé exactement sur `1.8.8` dans `requirements.in` pour ne pas bouger la version
  documentée dans `shared/telemetry.py` (comportement vérifié empiriquement contre cette version
  précise) : `pip-compile` échoue à résoudre ce pin exact (conflit de contraintes internes,
  `RuntimeError: No stable configuration...`). Laissé sans pin — résolu à `1.8.9` (patch). Vérifié
  que le comportement documenté (kwarg `resource=` vs `service_name=`) tient toujours : les 9 tests
  de `tests/test_telemetry.py` passent avec `1.8.9` installé, dont
  `test_configure_azure_monitor_not_called_service_name_kwarg` qui couvre précisément ce point.
- Suite complète rejouée avec ce nouveau lock file installé : 399 tests passent.

---

## PR #239 — feat(frontend): auto-save silencieux de notification_days + garde de navigation sur modifications non enregistrées

**Date :** 2026-07-26
**Branche :** `feature/profile-notifications-autosave` → `dev`

### Contexte

PR purement frontend (`JobFinder/frontend/`), aucun changement backend. Deux préoccupations
indépendantes traitées ensemble parce qu'elles retravaillent la même page (`/profile`) :

1. `notification_days` (posé par la PR #231) partageait jusqu'ici le bouton « Enregistrer » manuel du
   bloc Expérience/Description, alors que ce champ n'a aucun impact matching/coût contrairement aux
   deux autres (`_INTENT_FIELDS` côté `routers/profile.py`) — il n'a donc pas besoin d'un
   enregistrement manuel ni d'une garde de navigation.
2. Décision produit du 2026-07-26 : ne plus permettre de quitter silencieusement `/profile` (via le
   lien Accueil ou le menu mobile) en perdant des modifications non enregistrées sur
   Expérience/Description.

### Ce qui a été fait

- **`app/profile/_hooks/useNotificationDaysAutosave.ts`** (nouveau) : `handleNotificationDaysChange`
  déclenche désormais un `PUT /profile { notification_days }` autonome via ce hook dédié, débounce
  (`NOTIFICATION_DEBOUNCE_MS = 800`), sur le même schéma que l'auto-save `commune_codes` de
  `HomeMapSection.tsx` (`SAVE_DEBOUNCE_MS`) — dirtiness et timer dans des refs (pas de state) pour ne
  pas re-render la page, échec réduit à un `console.error` (même compromis que `HomeMapSection`),
  flush au démontage. Extrait de `page.tsx` suite à une remarque non-bloquante de `reviewer-frontend`
  (voir section Reviewers). `handleSave()` (bloc Expérience/Description) n'envoie plus
  `notification_days` et retourne désormais `Promise<boolean>` — nécessaire pour servir aussi de
  handler de sauvegarde à la boîte de dialogue du point suivant.
- **`lib/navigation/UnsavedChangesContext.tsx`** (nouveau) : `UnsavedChangesProvider`, monté une fois
  dans `app/layout.tsx` (autour du `<header>` global portant `MobileNavMenu` et `{children}`),
  expose `useUnsavedChanges()` → `{ setHasUnsavedChanges, registerSaveHandler, confirmNavigation }`.
  `confirmNavigation()` résout `true` immédiatement si la page est propre ; si elle est modifiée,
  ouvre la boîte de dialogue et résout selon le choix de l'utilisateur.
- **`app/_components/UnsavedChangesDialog.tsx`** (nouveau) : modale de présentation pure (tout l'état
  vit dans le provider), stylée comme la modale de confirmation existante de
  `DeleteAccountSection.tsx`, avec trois actions — « Annuler » (résout `false`), « Quitter sans
  enregistrer » (résout `true` sans appeler de handler), « Enregistrer et quitter » (appelle le
  handler enregistré, résout `true` si succès, affiche une erreur et reste ouverte sinon).
- **`app/profile/page.tsx`** : nouvel état `dirty`, mis à jour uniquement par
  `handleExperienceChange`/`handleDescriptionChange` (jamais par le handler de notifications).
  Synchronisé dans le contexte via `setHasUnsavedChanges`, `handleSave` enregistré comme handler de
  sauvegarde de la boîte de dialogue, listener natif `beforeunload` gated sur `dirty` (couvre
  fermeture d'onglet/rechargement — la navigation SPA est couverte séparément par
  `confirmNavigation`), et le `Link href="/"` du bandeau desktop passe par `confirmNavigation()`
  avant de naviguer.
- **`app/_components/MobileNavMenu.tsx`** : `goToSection` (quand on quitte une route autre que `/`) et
  les `<Link>` `/profile`/`/feedback` passent désormais par `confirmNavigation()` avant de naviguer
  réellement (interception via `preventDefault` + `router.push`).
- Hors périmètre, délibérément : la navigation navigateur retour/avant (`popstate`) n'est pas
  interceptée.

### Décisions techniques

- **`notification_days` reste hors de la garde de navigation** : aucun état « non enregistré » ne
  s'y applique — c'est le point de départ de toute cette PR, pas une omission.
- **Refs plutôt que state pour la dirtiness/le debounce des notifications** : évite un re-render de
  toute la page à chaque frappe/clic sur le toggle, seul le composant contrôlé
  (`NotificationDaysToggle`) a besoin de refléter la valeur affichée (`notificationDays`, en state).
- **`handleSave` renvoie `Promise<boolean>`** plutôt qu'un simple `void` : c'est le seul moyen pour
  `UnsavedChangesProvider` de savoir si « Enregistrer et quitter » doit fermer la boîte de dialogue
  ou afficher une erreur et rester ouverte.

### Vérification

- `npx jest` : 174 tests verts, dont les 3 fichiers nouveaux/mis à jour ci-dessus
  (`UnsavedChangesContext.test.tsx`, `ProfilePage.test.tsx`, `MobileNavMenu.test.tsx`).
- `npx tsc --noEmit` : propre.

Passage doc-writer : docstrings/commentaires WHY vérifiés fichier par fichier contre le comportement
actuel (`app/profile/page.tsx`, `lib/navigation/UnsavedChangesContext.tsx`,
`app/_components/UnsavedChangesDialog.tsx`, `app/_components/MobileNavMenu.tsx`, `app/layout.tsx`,
et les 3 fichiers de test + `__tests__/README.md`) — tous déjà fidèles et complets, aucune correction
nécessaire.

### Reviewers

- **reviewer-frontend** : APPROUVÉ. Deux remarques non-bloquantes corrigées directement : le bloc
  d'autosave `notification_days` (refs, debounce, flush) extrait de `page.tsx` dans un hook dédié
  (`app/profile/_hooks/useNotificationDaysAutosave.ts`), et un handler `Escape` ajouté à
  `UnsavedChangesDialog.tsx` (démontage conditionnel par le provider, contrairement au modal
  toujours monté de `DeleteAccountSection.tsx` qui a inspiré le pattern). Suite `jest` et
  `tsc --noEmit` rejoués propres après ces deux changements. Deuxième passage : APPROUVÉ, aucune
  remarque non-bloquante.

---

## PR #240 — feat: réanalyse CV et détection d'obsolescence des analyses de match pilotées par l'intention

**Date :** 2026-07-26
**Branche :** `feature/intent-driven-reanalysis` → `dev`

### Contexte

Deux boutons manuels existaient pour tenir les analyses IA à jour avec l'intention déclarée par
l'utilisateur sur `/profile` (`experience_level`, `candidate_description`) : un bouton "reanalyser
les codes ROME" sur la bibliothèque (`POST /cv/{id}/rome/retry`) et un bouton "relancer l'analyse"
sur une analyse CV en erreur (`POST /cv/{id}/analysis/retry`). Aucun mécanisme équivalent n'existait
pour signaler qu'une analyse de match (CV↔offre) déjà terminée était devenue obsolète après un
changement d'intention. Cette PR remplace le premier bouton par un déclenchement automatique et
gratuit, et ajoute la détection d'obsolescence manquante pour le second cas — voir
`docs/prompts/prompt-intent-driven-reanalysis.md`.

### Ce qui a été fait

- **`migrations/versions/034_generalize_intent_tracking.py`** (nouveau) : renomme
  `user_profiles.description_updated_at` (migration 031) en `intent_updated_at` — simple rename de
  colonne, préserve les valeurs existantes — et ajoute `last_intent_dispatch_at` (nullable, pas de
  backfill : `NULL` = "jamais dispatché", correct par construction).
- **`shared/models.py`** : `UserProfile.intent_updated_at` (remplace `description_updated_at`) et
  `UserProfile.last_intent_dispatch_at` (nouveau), avec commentaires expliquant leurs rôles distincts
  — le premier est stampé sur tout changement d'intention et sert `_mark_stale` (routers/matches.py),
  le second ne throttle que le dispatch de réanalyse. `CV.rome_analyzed_at` (migration 031) est laissé
  en place mais n'a plus aucun lecteur maintenant que la réanalyse ROME sur changement d'intention est
  automatique — commentaire mis à jour pour le documenter comme tel plutôt que de le supprimer (encore
  une donnée valide, coût de rétention nul).
- **`agents/webapp/routers/profile.py`** — `put_profile` : stampe `intent_updated_at`
  inconditionnellement dès que `experience_level` OU `candidate_description` change (avant : seul
  `candidate_description` comptait, sous l'ancien nom `description_updated_at`) — nécessaire car
  `match_analysis`'s own `_build_intent_text` rend les deux champs, donc un changement du seul
  `experience_level` rend aussi les analyses de match existantes obsolètes, pas seulement les codes
  ROME. Ajout de `_dispatch_cv_reanalysis` : envoie un message `cv-analysis` simple (sans flag
  `retry_rome_only`/`retry_quality_only`) pour chaque CV du user, routé vers la branche complète
  ROME+qualité de `agents/cv_analysis/main.py` — gratuit, automatique, sans changement de crédits.
  Le dispatch (`_dispatch_start_matching` + `_dispatch_cv_reanalysis`) est throttlé par
  `INTENT_DISPATCH_COOLDOWN_SECONDS` (`shared/config.py`, 300s) pour qu'un utilisateur qui enchaîne
  les sauvegardes de profil ne déclenche pas un volume illimité d'appels IA gratuits ;
  `intent_updated_at`, lui, n'est jamais throttlé — il reflète toujours la dernière intention
  sauvegardée, même quand le dispatch lui-même a été retardé par le cooldown.
- **`agents/webapp/routers/matches.py`** : nouveau helper `_mark_stale`, qui marque
  `MatchAnalysisOut.stale = True` sur une analyse `"done"` dont `completed_at` précède
  `profile.intent_updated_at`. Branché dans `GET /matches` et `GET /matches/cv/{cv_id}` (ce dernier
  étant pollé toutes les quelques secondes par le frontend, il doit rester synchronisé avec la liste
  principale).
- **`agents/webapp/schemas.py`** : `MatchAnalysisOut.stale` (nouveau champ, défaut `False`) — un
  `field_validator(mode="before")` force `stale=False` sur tout `model_validate` (aucune colonne DB
  ne porte ce nom ; sans ce garde-fou, un double de test type `MagicMock` auto-vivifierait un
  attribut `stale` truthy). Seul le routeur peut le mettre à `True`, via
  `model_copy(update={"stale": True})`, qui ne repasse jamais par la validation Pydantic — c'est ce
  contournement de `model_copy` qui rend le contrat "obsolescence calculée uniquement côté routeur"
  réellement infranchissable ailleurs.
- **`agents/webapp/routers/cv.py`** : suppression complète de `POST /cv/{id}/rome/retry`,
  `POST /cv/{id}/analysis/retry`, et du calcul de `rome_reanalysis_available` — les trois n'avaient
  plus de raison d'être une fois la réanalyse ROME automatique.
- **`agents/cv_analysis/main.py`** : docstring de `_mark_rome_analyzed` mise à jour (l'implémentation)
  pour expliquer que `rome_analyzed_at` n'a plus de lecteur maintenant que le bouton manuel de
  réanalyse ROME est supprimé. Passage doc-writer (voir plus bas) sur ce même fichier :
  `_handle_retry_quality_only` et `_handle_retry_rome_only` référençaient encore les deux endpoints
  supprimés comme seuls appelants ; `main()` mis à jour en cohérence.
- **Frontend — `app/_components/MatchAnalysisPanel.tsx`** : badge "Obsolète" + `InfoTooltip` +
  icône de relance (réutilise `onAnalyze`, même retry payant qu'avant) affichés quand
  `analysis.stale`.
- **`app/_components/InfoTooltip.tsx`** : déplacé depuis `app/profile/_components/InfoTooltip.tsx`
  — désormais partagé entre `/profile` et le panneau de match. Import mis à jour dans
  `app/profile/page.tsx`.
- **`app/_components/CvAnalysisCard.tsx`** : bouton manuel "Relancer l'analyse" retiré (l'endpoint
  n'existe plus) — l'état d'erreur affiche désormais un message statique expliquant que la
  réanalyse aura lieu automatiquement si l'utilisateur modifie son expérience ou sa recherche.
- **`app/_components/RomeReanalysisButton.tsx`** : supprimé, ainsi que son branchement dans
  `CVDetailSection.tsx` et `HomeClient.tsx`. `libraryRefreshTrigger` (HomeClient.tsx) est
  volontairement conservé — encore utilisé par 3 autres handlers, seul celui du bouton ROME a été
  retiré.
- **`lib/api/types.ts`** : `CVData.rome_reanalysis_available` retiré, `MatchAnalysisOut.stale`
  ajouté.

### Décisions techniques

- **`_dispatch_cv_reanalysis` réutilise la branche complète du pipeline d'upload** (ROME + qualité)
  plutôt qu'un chemin dédié plus étroit — aucun flag `retry_rome_only`. Conséquence non triviale :
  `_handle_new_cv_analysis` passe `CV.status` par `"processing"` puis `"done"` avant que le matching
  ne retourne des résultats, exactement comme à l'upload. Un CV déjà `"matched"` quitte donc
  visiblement cet état le temps de la réanalyse — la bibliothèque et le panneau d'analyse de
  `CVDetailSection.tsx` (`isAnalysisInProgress`) affichent brièvement un état "en cours". Accepté
  comme compromis plutôt que d'ajouter un chemin de réanalyse plus étroit ; documenté dans la
  docstring de `_dispatch_cv_reanalysis`.
- **`intent_updated_at` jamais throttlé, `last_intent_dispatch_at` seul gate le dispatch** : sépare
  "la dernière intention sauvegardée" (toujours à jour, sert le badge d'obsolescence) de "la
  dernière fois où on a effectivement relancé les analyses" (throttlé) — un save pendant le cooldown
  ne doit jamais faire manquer le badge d'obsolescence sous prétexte que le recalcul lui-même a été
  reporté.
- **`stale` forcé à `False` via `field_validator(mode="before")`, jamais assignable autrement qu'en
  `model_copy`** : garantit que seul `_mark_stale` (qui a accès au profil complet) peut marquer une
  analyse obsolète — un `model_validate` direct depuis la DB ne peut jamais accidentellement le
  faire, y compris depuis un double de test.

### Vérification

- 401 tests backend / 158 tests frontend passent, `tsc --noEmit` et `eslint` propres — chiffres
  rapportés par la session d'implémentation, non rejoués dans cette passe documentation (pas d'accès
  Bash/`git diff` depuis ce rôle — vérification faite en relisant directement le contenu actuel des
  fichiers cités ci-dessus plutôt qu'un diff).
- Recherche de résidus de l'ancien nom `description_updated_at`, des endpoints supprimés
  (`rome/retry`, `analysis/retry`), du composant supprimé (`RomeReanalysisButton`,
  "Relancer l'analyse") et du champ supprimé (`rome_reanalysis_available`) sur tout le repo : aucun
  résidu de production trouvé — seules des occurrences légitimes subsistent (tests asserting
  l'absence du bouton, migrations historiques jamais réécrites, `_handle_retry_rome_only`/
  `_handle_retry_quality_only` eux-mêmes, dont les docstrings ont été corrigées ci-dessous).

Passage doc-writer : `agents/cv_analysis/main.py::_handle_retry_quality_only` attribuait encore son
déclenchement à l'endpoint supprimé `POST /cv/{id}/analysis/retry` — corrigé pour attribuer le seul
appelant réel actuel, `_backfill_cv_analysis` (auto-guérison de `GET /cv/{id}/analysis`, sans rapport
avec un bouton manuel utilisateur). `_handle_retry_rome_only` attribuait de même son déclenchement à
l'endpoint supprimé `POST /cv/{id}/rome/retry` — corrigé pour indiquer qu'aucun appelant réel ne
subsiste aujourd'hui (branche laissée en place plutôt que supprimée, même rationale que
`CV.rome_analyzed_at`). `main()` (`agents/cv_analysis/main.py`) mis à jour pour rester cohérent avec
ces deux corrections. `_dispatch_cv_reanalysis` (`routers/profile.py`) complétée pour documenter
l'effet de bord sur `CV.status` détaillé ci-dessus (Décisions techniques), non mentionné dans la
docstring d'origine. `tests/README.md` : la ligne `test_webapp_cv.py` référençait encore
`POST /cv/{cv_id}/analysis/retry` (supprimé de la suite de tests avec l'endpoint) — remplacée par la
couverture réelle (`GET /cv/{cv_id}/analysis` incl. `_backfill_cv_analysis`) ; la ligne
`test_webapp_matches.py` complétée pour mentionner `_mark_stale`, testé mais absent du tableau.
Toutes les autres docstrings/commentaires touchés par cette PR (`migrations/versions/034_*.py`,
`shared/models.py`, `routers/matches.py`, `schemas.py`, frontend `MatchAnalysisPanel.tsx`/
`InfoTooltip.tsx`/`CvAnalysisCard.tsx`/`CVDetailSection.tsx`/`HomeClient.tsx`/`types.ts`) vérifiés
exacts vis-à-vis du code actuel, rien d'autre à corriger.

---

## PR #241 — feat(notifications): refonte du contenu et du template du récap email

**Date :** 2026-07-26
**Branche :** `feature/email-digest-redesign` → `dev`

### Contexte

Le récap email quotidien (`agents/notifications/main.py`, ajouté en PR #238) se limitait jusqu'ici à
un simple compte de matchs non vus par CV, dans un template `<ul>` minimal. Cette PR le refond
entièrement, contenu et design, suivant `docs/prompts/prompt-email-digest-content-and-design.md`.

### Ce qui a été fait

- **`agents/notifications/main.py`** : pour chaque CV ayant au moins un match non vu, le récap
  affiche désormais le meilleur match non vu (titre, entreprise, localisation, type de contrat,
  score en %) au lieu du seul compte. Ajout d'un accueil personnalisé
  (`UserProfile.display_name`, best-effort depuis le JWT, avec repli générique "Bonjour,") et
  d'une frise calendaire de rappel sur 7 jours dans l'en-tête (couleur selon aujourd'hui/jour
  sélectionné/jour non sélectionné — aujourd'hui l'emporte même si aussi sélectionné). L'objet du
  mail est désormais calculé dynamiquement (singulier/pluriel en français, `_build_digest_subject`)
  au lieu d'être une constante statique. Le template HTML `<ul>` d'origine est remplacé par un
  template `<table>` complet en thème sombre, compatible clients mail (VML/MSO, media query mobile,
  preheader caché).
  - `_count_unseen_matches_by_user` (comptage seul) renommé en `_load_cv_digest_entries_by_user` et
    réécrit en une requête unique SQLAlchemy Core à fonctions fenêtrées
    (`func.row_number().over(partition_by=CV.id, order_by=(Match.score.desc(), Match.id))` — le
    tie-break sur `Match.id` stabilise le choix en cas d'égalité de score — et
    `func.count().over(partition_by=CV.id)`, gardant uniquement `rn=1`) plutôt qu'un `GROUP BY` :
    calcule en un seul passage le compte non-vu ET le meilleur match par CV. Écrite avec le support
    de fonctions fenêtrées de SQLAlchemy Core (pas de SQL brut) spécifiquement pour rester portable
    à SQLite (suite de tests) — contrairement à l'équivalent de `agents/matching/main.py`
    (`_enqueue_top_n_analyses`), qui utilise du SQL brut PostgreSQL-only et est de ce fait exclu de
    la suite de tests SQLite (`tests/README.md`).
  - Nouvelles dataclasses `Recipient` (profil éligible, copié hors de la session avant sa
    fermeture) et `CvDigestEntry` (une entrée de récap par CV : compte + meilleur match).
  - `_build_email_content` et `_send_digest` changent de signature : le sujet est désormais un
    paramètre (`subject: str`), calculé par destinataire via la nouvelle `_build_digest_subject`
    plutôt que dérivé en interne. `main()` rebranché en conséquence.
- **`agents/notifications/tests/test_notifications.py`** : suite réécrite pour couvrir le nouveau
  contenu — meilleur match par CV avec repli localisation → département quand `Offer.location` est
  vide, échappement HTML du titre/entreprise de l'offre (en plus du nom de CV déjà couvert),
  accueil générique vs personnalisé, singulier/pluriel de l'objet (y compris le cas défensif
  0 offre, que `main()` n'atteint jamais mais que la fonction ne doit pas planter dessus), priorité
  aujourd'hui/sélectionné/non-sélectionné de la frise calendaire, et regroupement par utilisateur
  sans mélange sur `_load_cv_digest_entries_by_user` batché.

### Décisions techniques

- **Écart signalé par rapport au prompt** : `docs/prompts/prompt-email-digest-content-and-design.md`
  mentionne un fichier `python/send_test_notification.py` à "garder synchronisé" avec ces
  changements. Ce fichier n'existe nulle part dans ce dépôt — confirmé via
  `git log --all --diff-filter=D --name-only -- '*send_test_notification*'` (aucun résultat, y
  compris en historique supprimé) : il n'a jamais été créé, ce n'est pas un oubli de suppression.
  Traité comme une référence obsolète du prompt et volontairement ignoré — aucun fichier de ce nom
  créé dans cette PR.
- Requête à fonctions fenêtrées (`ROW_NUMBER()`/`COUNT() OVER (PARTITION BY cv_id ...)`) choisie
  plutôt qu'un `GROUP BY` classique précisément parce qu'elle doit renvoyer à la fois l'agrégat
  (compte non-vu) et une ligne de détail (le meilleur match) par CV en un seul aller-retour DB —
  un `GROUP BY` seul n'aurait donné que l'agrégat.

### Vérification

- Passage doc-writer : docstrings de `agents/notifications/main.py` relues fonction par fonction et
  vérifiées exactes par rapport au code actuel, dont la référence croisée à
  `_enqueue_top_n_analyses`/`tests/README.md` ci-dessus, et le mécanisme "deux heures UTC candidates"
  décrit en prose par la docstring de module — cohérence vérifiée contre le
  `cron_expression = "0 17,18 * * *"` réel de `container_apps.tf` (la docstring ne cite pas la
  chaîne cron elle-même, seul le mécanisme). Un seul gap trouvé et corrigé : ni `CvDigestEntry` ni
  `_load_cv_digest_entries_by_user` ne documentaient que `top_offer_location` peut être
  `Offer.department` (repli) ou la chaîne vide (les deux champs blancs) — corrigé sur les deux
  docstrings.
- Remarque non-bloquante de la passe doc-writer (nom de fonction trompeur, hors périmètre docs) :
  corrigée après coup — `_load_recipients_and_counts` renommée en `_load_recipients_and_entries`,
  puisqu'elle ne renvoie plus seulement des comptes mais les entrées de récap complètes
  (`CvDigestEntry`) depuis le renommage de `_count_unseen_matches_by_user`.
- Pas d'accès Bash/`git diff` depuis ce rôle : nombre de tests, `ruff`/lint et `terraform plan` non
  rejoués dans cette passe — vérification faite en relisant directement le contenu des fichiers
  cités ci-dessus, comme pour la passe documentation de la PR #240. Numéro de PR dérivé du dernier
  titre `## PR #NNN` présent dans ce fichier (#240) + 1, faute d'accès à `gh` depuis ce rôle
  (aucun outil Bash disponible, pas seulement `gh` non authentifié) — confirmé exact ensuite via
  `gh pr list --state all --limit 5` (dernier numéro réel : #240).
- **Revue `reviewer-backend`, plusieurs allers-retours avant `APPROUVÉ` définitif :**
  - Point bloquant trouvé et corrigé : `UserProfile.display_name` (claim JWT best-effort, texte
    libre) était injecté dans le corps HTML sans `html.escape()` — même catégorie de donnée que
    `CV.name`/`Offer.title`, déjà échappés partout ailleurs dans ce fichier. Un `display_name`
    contenant `<`/`&` aurait cassé le rendu HTML de l'email (voire pire selon le client mail).
    Corrigé dans `_render_html_body` (le chemin texte brut garde la valeur non échappée, pas de
    markup à casser) ; couvert par `test_build_email_content_escapes_display_name_in_html`.
  - `main()` dépassait la limite de 40 lignes (convention `conventions-python`) — la logique par
    destinataire extraite dans `_process_recipient`.
  - Nouveau helper `_digest_totals` pour éliminer la triplication du calcul
    `(total_unseen, best_score)` entre `_build_digest_subject`/`_render_html_body`/
    `_build_email_content`.
  - Remarque non-bloquante sur un test de tie-break insuffisamment discriminant (vérifiait
    seulement la répétabilité d'un appel, pas la présence réelle du tie-break `Match.id`) —
    corrigée en donnant à `_add_match` un paramètre `match_id` explicite, permettant d'imposer
    quel match gagne à score égal ; vérifié manuellement que ce test échoue si le tie-break est
    retiré de `main.py`.
  - Remarque non-bloquante sur une description de `ORDER BY` devenue périmée dans le docstring de
    `_load_cv_digest_entries_by_user` (ne mentionnait pas le tie-break `Match.id` ni le
    `ORDER BY cv_name` du select final) — corrigée.
---

## PR #242 — fix(frontend): différer le fondu de la carte jusqu'à l'arrivée réelle du scroll sur Accueil

**Date :** 2026-07-26
**Branche :** `feature/navbar-home-scroll-highlight` → `dev`

### Contexte

Les icônes "Carte", "Bibliothèque" et "Offres" de `LeftNavRail` déclenchaient le scroll vers la
section cible et le changement de mode cv/carte de `HomeMapSection` (le fondu avec particules/icône
CV entre la couche upload et la couche carte des communes) dans le même tick. Un clic sur "Carte"
depuis la bibliothèque (ou sur "Bibliothèque"/"Offres" pendant que la carte était affichée) sautait
donc entièrement le passage visuel par la section "Accueil" — l'utilisateur atterrissait directement
sur la cible sans jamais voir le fondu.

### Ce qui a été fait

- **`app/_components/HomeClient.tsx`** : ajout de deux refs, `pendingEnterMapRef` et
  `pendingExitTargetRef` (`"library" | "cv-detail" | null`), et de deux `useEffect` qui les
  consomment une fois la transition en cours réellement arrivée à destination.
  - `handleGoMap` : si `activeSection !== "home"`, lance le scroll vers `home` et pose
    `pendingEnterMapRef.current = true` au lieu d'appeler `enterMap()` immédiatement ; un effet qui
    observe `activeSection` appelle `enterMap()` dès que celui-ci devient `"home"`. Déjà sur
    `home`, le comportement est inchangé (appel immédiat).
  - `handleGoLibrary`/`handleGoOffers` : si le mode est `"map"`/`"to-map"`, appellent `exitMap()`
    tout de suite mais posent `pendingExitTargetRef.current` (`"library"` ou `"cv-detail"`) au lieu
    de scroller immédiatement ; un second effet qui observe `mode` déclenche le
    `scrollIntoView` correspondant dès que `mode` redevient `"cv"` (le fondu retour cv↔carte
    s'étant terminé).
  - `handleGoHome` (déjà correct avant cette PR) et chacun des trois handlers ci-dessus commencent
    désormais par vider les deux refs avant de poser leur propre valeur, pour qu'un nouveau clic
    annule toujours proprement ce qu'un clic précédent avait laissé en attente.
- **`__tests__/HomeClient.test.tsx`** : nouveau bloc de tests sur cette orchestration — entrée
  différée dans la carte, entrée immédiate si déjà sur Accueil, sortie différée vers
  Bibliothèque/Offres, sortie immédiate si la carte n'est pas affichée, et quatre cas d'annulation
  croisée (Bibliothèque annule un `enterMap` en attente, Accueil annule un `enterMap` en attente,
  Accueil annule une sortie en attente vers Bibliothèque, Carte annule elle aussi une sortie en
  attente vers Bibliothèque). `HomeMapSection`
  est mocké pour exposer `enterMap`/`exitMap` comme espions et pour permettre de simuler
  `onModeChange` sans dépendre du timer réel de la transition (`TRANSITION_MS`).

### Décisions techniques

- **Signal "arrivé" réutilisé plutôt que redéfini** : "le scroll a atteint Accueil" est détecté via
  `activeSection`, exactement le même signal piloté par `IntersectionObserver` que celui qui pilote
  déjà la mise en surbrillance de `LeftNavRail` — pas de nouveau mécanisme de détection de fin de
  scroll. De même, "le fondu retour a atterri" est détecté via `mode === "cv"`, l'état que
  `HomeMapSection` reporte déjà lui-même par `onModeChange`.
- **Toujours vider les deux refs en tête de chaque handler** plutôt que de ne poser que celle qui
  concerne le handler courant : un clic est toujours une intention fraîche qui doit pouvoir annuler
  ce qu'un clic précédent attendait encore, y compris quand ce clic précédent visait une ref
  différente (ex. Bibliothèque doit annuler un `pendingEnterMapRef` laissé par un clic Carte
  antérieur, pas seulement poser son propre `pendingExitTargetRef`).

### Vérification

- Relecture directe du contenu actuel de `HomeClient.tsx` et de `HomeClient.test.tsx` (pas d'accès
  Bash/`git diff` depuis ce rôle, même limitation que documentée dans l'entrée PR #240 ci-dessus) :
  les commentaires WHY sur les deux nouvelles refs (lignes 48-57), les deux nouveaux effets
  (lignes 100-119) et chacun des quatre handlers (lignes 188-245) décrivent fidèlement le
  comportement actuel du code et sont cohérents avec les neuf scénarios couverts par les tests —
  rien à corriger.
- `reviewer-frontend` passé trois fois sur cette branche (deux sur `HomeClient.tsx`/son fichier de
  tests, un sur l'addendum `LeftNavRail.tsx` ci-dessous) avec verdict `APPROUVÉ` et
  `Remarques non-bloquantes : aucune` à chaque fois.

### Addendum — fond du rail rendu transparent

**`app/_components/LeftNavRail.tsx`** : le fond du `<nav>` passe de `bg-scrim` (un
`rgba(0, 0, 0, 0.40)` fixe, identique dans `light.ts` et `dark.ts`, `lib/theme/themes/`) à
`bg-transparent` — plus aucun remplissage derrière le rail, en thème sombre comme en thème clair.
Supersède la demande antérieure documentée dans le commentaire du composant (fond sombre
quasi-transparent plutôt que theme-adaptive) ; `bg-transparent` est l'utilitaire Tailwind natif
(aucune valeur de couleur, donc hors du champ de la règle "toujours passer par un token de
thème") et se comporte identiquement dans les deux thèmes par construction — aucune vérification
navigateur nécessaire ni faite depuis ce rôle (même limitation d'accès que documentée dans la
section Vérification ci-dessus). `reviewer-frontend` confirme l'absence de commentaire obsolète
ailleurs dans le fichier ou ses consommateurs.

---

## PR #243 — feat(dev): secret HMAC partagé pour le désabonnement one-click des notifications

**Date :** 2026-07-26
**Branche :** `feature/notifications-unsubscribe-secret` → `dev`

### Contexte

Le prompt `docs/prompts/prompt-email-one-click-unsubscribe.md` (rédigé avec Claude Cowork) demande
d'ajouter les en-têtes `List-Unsubscribe`/`List-Unsubscribe-Post` (RFC 8058) à l'email de
notification, pour que Gmail/Outlook/Yahoo affichent le bouton natif de désabonnement plutôt que de
pousser un utilisateur agacé vers "Signaler comme spam" (ce qui dégraderait la réputation d'envoi de
tous les mails suivants). Le mécanisme retenu : un token signé HMAC-SHA256 sur `user_id`, vérifié par
un nouvel endpoint non authentifié `POST /notifications/unsubscribe` côté webapp. Le secret de
signature doit donc être partagé entre l'agent `notifications` (signe à l'envoi) et `webapp` (vérifie
à la réception) — un nouveau secret Key Vault et deux variables d'environnement.

Cette tâche touche à la fois Terraform (`envs/dev/`) et Python (nouvel endpoint, signature du token) ;
la règle de CLAUDE.md interdisant de mélanger plateforme et app dans une même PR impose de la
séquencer en deux PR (voir aussi la section Gouvernance du prompt) :
1. **Cette PR (infra)** — secret Key Vault + wiring des variables d'environnement, sans aucun code
   Python consommateur.
2. **PR de suivi (app)** — `feature/notifications-one-click-unsubscribe`, endpoint, signature/
   vérification du token, en-têtes sur l'envoi. Pas encore créée à ce stade.

### Ce qui a été fait

- **`notifications_unsubscribe_secret.tf`** (nouveau) : `random_password.notifications_unsubscribe_secret`
  (32 caractères, même charset que le mot de passe admin de `jumpbox.tf`) + le module
  `secret_notifications_unsubscribe` (`keyvault_secret`) qui publie la valeur sous
  `notifications-unsubscribe-secret` dans Key Vault. Généré directement par Terraform plutôt que
  seedé manuellement : contrairement à `ft-client-id`/`entra-external-*` (identifiants tiers réels
  provisionnés hors bande, voir `job-finder-private/docs/MANUAL_OPERATIONS.md`), cette valeur n'a
  aucune contrepartie externe à faire correspondre.
- **`container_apps.tf`** : nouveau local `notifications_unsubscribe_secret`, secret
  `notifications-unsubscribe-secret` et variable d'environnement `NOTIFICATIONS_UNSUBSCRIBE_SECRET`
  ajoutés au Container App Job `job_notifications` (agent 7, déclenché par timer, cron
  `0 17,18 * * *` — 19:00 Europe/Paris avec double run DST-safe, voir PR #237/#200).
- **`webapp.tf`** : même secret et variable d'environnement ajoutés au Container App `webapp`, aux
  côtés des autres secrets Key Vault déjà exposés (`entra-external-client-secret`).

Pas de changement Python dans cette PR — le secret n'est consommé par aucun code applicatif pour
l'instant.

### Décisions techniques

- **`random_password` généré par Terraform plutôt que secret seedé manuellement** : ce secret n'a
  aucun homologue externe à synchroniser (contrairement aux identifiants France Travail ou Entra
  External ID) — Terraform peut donc le générer directement, exactement comme le mot de passe admin
  de `jumpbox.tf`.
- **Wiring sur les deux Container Apps avant tout code consommateur** : accepté comme un état
  intermédiaire volontaire (secret présent, non lu) plutôt que d'attendre la PR 2 pour l'ajouter —
  cohérent avec la règle CLAUDE.md de ne jamais mélanger plateforme et app dans une même PR.

### Vérification

- Relecture directe du contenu actuel des trois fichiers (pas d'accès Bash/`git diff` depuis ce
  rôle) : le commentaire d'en-tête de `notifications_unsubscribe_secret.tf` compare fidèlement le
  bloc `random_password` à celui de `jumpbox.tf` (`length = 32`, `special = true`, même
  `override_special`), et le wiring dans `container_apps.tf` (lignes 52, 343-345, 373-375) et
  `webapp.tf` (lignes 50-52, 92-94) correspond à ce que le commentaire décrit — rien à corriger.
- Nit relevé mais non corrigé ici (relève de `reviewer-infra`, pas de ce rôle) : le commentaire
  d'en-tête de `notifications_unsubscribe_secret.tf` décrit `job_notifications` au présent ("signe
  le token... à l'envoi du récap") alors qu'aucun des deux Container Apps ne consomme encore
  réellement le secret avant la PR 2 — légère asymétrie de temps entre les deux moitiés de la
  phrase.
- Aucune entrée `## PR #243` ni entrée existante pour cette branche dans `docs/JOURNAL.md` avant
  cette passe — nouvelle entrée ajoutée en fin de fichier.

---

## PR #244 — feat(openai): custom_subdomain_name sur le compte Azure OpenAI

**Date :** 2026-07-26
**Branche :** `feature/openai-custom-subdomain` → `dev`

### Contexte

`azurerm_cognitive_account.this` (`modules/openai/main.tf`) n'a jamais eu de `custom_subdomain_name` :
son `.endpoint` restait l'URL régionale partagée, qui refuse l'authentification par token AD
(400 BadRequest systématique — logs prod du 2026-07-26), bloquant la bascule Managed Identity posée
en PR #232/#234. Décision : plutôt que de revenir sur cette bascule (voir
`docs/prompts/prompt-revert-openai-managed-identity.md`, plan abandonné), poser le vrai prérequis
manquant maintenant, tant qu'il n'y a aucun utilisateur en prod.

### Ce qui a été fait

- **`modules/openai/main.tf`** : ajout de `custom_subdomain_name = var.name` sur
  `azurerm_cognitive_account.this` (réutilise `oai-jf-dev-frc`, déjà unique — vérifié en amont via
  `az rest` sur `Microsoft.CognitiveServices/checkDomainAvailability`, `isSubdomainAvailable: true`).

### Décisions techniques

- **Le plan initial supposait un destroy+recreate** (`custom_subdomain_name` documenté comme
  `ForceNew`, entraînant le compte OpenAI et ses 3 déploiements de modèles, avec un retrait temporaire
  du `prevent_destroy` le temps de la fenêtre de maintenance). Un `terraform plan` local a contredit
  cette hypothèse : sur `azurerm ~4.72`, passer `custom_subdomain_name` de non défini à une valeur est
  une mise à jour **en place** (`~ update in-place`, aucun `# forces replacement`), pas un remplacement.
  Confirmé cohérent avec le comportement Azure documenté (le portail expose "Generate Custom Domain
  Name" sur un compte existant sans le recréer) et avec un ticket connu du provider
  (`hashicorp/terraform-provider-azurerm#28585`, qui documente ce même écart entre le comportement réel
  de l'API PATCH — qui ne touche que `customSubDomainName`/`dateCreated`/`endpoint`/`endpoints` — et le
  marquage `ForceNew` historique du provider pour cet attribut).
- **Conséquence : `prevent_destroy` n'a jamais été touché.** Il ne bloque que les destructions ; une
  mise à jour en place n'est pas concernée. Les préoccupations du plan initial (quota `gpt-5-mini` pour
  un redéploiement, drift RBAC cross-stack `lz_dev`/`dev` suite à un nouvel ID de ressource) sont donc
  sans objet — aucun redéploiement, aucun nouvel ID.
- **Drift pré-existant hors-scope observé pendant la vérification locale** : le `terraform plan` complet
  sur `envs/dev` (avec des variables `alert_email`/`portfolio_contact_function_url` de substitution,
  faute d'accès aux secrets CI en local) montre aussi un remplacement de la VM jumpbox et de son planning
  d'extinction, ainsi qu'un retour des tags d'image des Container App Jobs vers `:latest` — drift
  préexistant sur `dev`, sans rapport avec ce changement, non corrigé ici (une seule PR = un seul sujet).
  Le plan CI de cette PR (`terraformPlan.yml`, avec les vraies variables) fait foi, pas ce plan local à
  variables de substitution.

### Vérification

- `az rest` (lecture seule) confirmant la disponibilité du sous-domaine `oai-jf-dev-frc`.
- `terraform fmt -check` propre sur `modules/openai/main.tf` (le seul fichier touché) ;
  `terraform validate` propre sur `envs/dev`.
- `terraform plan` local (scopé puis complet) : seul `module.openai.azurerm_cognitive_account.this`
  change, en `update in-place` — pas de destroy, pas d'impact sur les 3 déploiements de modèles. Le
  secret Key Vault `openai-endpoint` (`module.secret_openai_endpoint`, référence
  `module.openai.endpoint`) n'apparaît pas dans ce plan local car `endpoint` reste un attribut
  "inchangé" tant que l'apply réel n'a pas eu lieu — Terraform ne peut pas prédire la nouvelle URL
  avant que l'API Azure ne la retourne après le PATCH. Sa mise à jour effective (secret KV + toute
  valeur consommée par `container_apps.tf`/`webapp.tf`) n'est donc vérifiable qu'après l'apply CI.
- Reste à faire après merge + apply CI (documenté dans la description de PR) : rejouer un cycle
  `offer_fetching` réel et confirmer un `openai_call_completed` avec `total_tokens` non nul ;
  confirmer dans le portail que le secret `openai-endpoint` reflète bien la nouvelle URL à sous-domaine
  (et non plus l'URL régionale partagée) ; vérifier manuellement que le role assignment `caj`
  (`Cognitive Services OpenAI User`, posé en PR #232) est toujours en place puisque le compte n'est
  pas recréé.
- `docs/BACKLOG.md` : item hardening OpenAI (ligne ~394) refermé avec référence à cette PR.

---

## PR #246 — fix(openai): construire l'endpoint à sous-domaine au lieu de lire l'attribut ARM

**Date :** 2026-07-26
**Branche :** `feature/openai-endpoint-custom-domain` → `dev`

### Contexte

Après merge + apply CI de la PR #244, les agents continuaient à recevoir un 400 sur l'authentification
par token AD. Le prompt initial (`docs/prompts/prompt-openai-endpoint-value.md`, rédigé avec Claude
Cowork) posait comme diagnostic que `azurerm_cognitive_account.this.endpoint` **reste
structurellement** l'URL régionale (`https://francecentral.api.cognitive.microsoft.com/`) quel que
soit `custom_subdomain_name`, et proposait de construire l'URL explicitement pour contourner cette
limitation supposée permanente.

**Ce diagnostic était faux — vérifié avant tout commit.** `az cognitiveservices account show` sur le
compte réel (`oai-jf-dev-frc`) retourne déjà `properties.endpoint = "https://oai-jf-dev-frc.openai.azure.com/"`
et chaque entrée de `properties.endpoints` pointe vers la même URL — l'attribut ARM reflète bien
`custom_subdomain_name`, contrairement à l'hypothèse du prompt. Le vrai problème, confirmé par un
`terraform plan` local **sans aucun changement de code** : le secret Key Vault `openai-endpoint`
(une seule version, datée du 2026-05-07) et les variables d'environnement `AZURE_OPENAI_ENDPOINT`
dérivées de `module.openai.endpoint` contenaient encore l'ancienne URL régionale — l'apply de la PR
#244 a mis en cache dans le state Terraform la valeur d'avant la propagation Azure du sous-domaine
(course entre l'apply et la propagation asynchrone côté control plane Azure), et aucun push sur `dev`
depuis n'a redéclenché de plan/apply pour rattraper ce drift.

C'est la **deuxième PR d'affilée** dont l'hypothèse technique de départ (rédigée par Claude Cowork)
s'avère fausse à la vérification — voir aussi la révision `ForceNew` de la PR #244 elle-même. Signalé
explicitement à Vincent dans la description de cette PR, pas seulement documenté ici après coup.

### Ce qui a été fait

- **`modules/openai/outputs.tf`** : la sortie `endpoint` ne lit plus
  `azurerm_cognitive_account.this.endpoint` — elle construit `"https://${var.name}.openai.azure.com/"`
  directement. Le suffixe `.openai.azure.com/` n'est pas une supposition : confirmé par la requête
  `az cognitiveservices account show` ci-dessus, sur ce compte précis.

### Décisions techniques

- **Corriger le WHY plutôt que de reprendre le diagnostic du prompt tel quel** : le commentaire de
  sortie explique la vraie cause (valeur mise en cache avant propagation, jamais rattrapée faute
  d'un nouveau plan/apply déclenché), pas une limitation permanente de l'attribut ARM qui n'existe
  pas. Une description qui dirait "reste toujours l'URL régionale" serait aussi fausse que
  l'hypothèse `ForceNew` corrigée en PR #244.
- **Construire plutôt que se contenter d'un nouvel apply qui aurait suffi** : un `terraform plan`
  sans changement de code montre déjà la dérive et la corrigerait au prochain apply. Mais le workflow
  du dépôt exige une PR pour déclencher cet apply de toute façon, et la production a déjà cassé une
  fois sur cette course de propagation — rendre la valeur connue au moment du plan (au lieu de
  dépendre d'un attribut calculé potentiellement pas encore à jour) élimine la classe de bug, pas
  seulement l'occurrence actuelle.
- **Propagation automatique aux consommateurs, sans autre fichier à toucher** : `local.openai_endpoint`
  (`container_apps.tf:49`) et `module.secret_openai_endpoint` (`envs/dev/openai.tf:47-56`) lisent
  déjà `module.openai.endpoint` — confirmé par `terraform plan` complet que la correction se propage
  à `job_cv_analysis`, `job_match_analysis`, `job_offer_fetching` et `webapp` (les 4 seuls
  consommateurs directs de `AZURE_OPENAI_ENDPOINT`, cohérent avec les modèles documentés en
  commentaire dans `envs/dev/openai.tf`) sans qu'aucun autre fichier n'ait besoin de changer.
  Ce sont des valeurs d'environnement littérales (pas des références à un secret Key Vault côté
  Container App), donc l'apply crée directement une nouvelle révision avec la bonne valeur.

### Vérification

- `az cognitiveservices account show` (lecture seule) confirmant `properties.endpoint` et
  `properties.endpoints` déjà alignés sur le sous-domaine — infirme le diagnostic initial du prompt.
- `az keyvault secret show`/`list-versions` (lecture seule) confirmant que le secret `openai-endpoint`
  n'a qu'une version, datée d'avant l'apply de la PR #244 — confirme le symptôme réel.
- `terraform fmt -check` propre sur `modules/openai/outputs.tf` ; `terraform validate` propre sur
  `envs/dev`.
- `terraform plan` complet (variables `alert_email`/`portfolio_contact_function_url` de substitution,
  comme en PR #244) : `AZURE_OPENAI_ENDPOINT` passe de l'URL régionale à
  `https://oai-jf-dev-frc.openai.azure.com/` sur exactement les 4 ressources attendues
  (`job_cv_analysis`, `job_match_analysis`, `job_offer_fetching`, `webapp`), plus le secret KV lui-même
  — aucune ressource recréée pour ce changement.
- Drift hors-scope toujours présent (VM jumpbox + planning d'extinction à remplacer,
  `workload_profile_name` du frontend) — inchangé depuis la PR #244, non corrigé ici, signalé à
  nouveau dans la description de PR.
- **Reste à faire après merge + apply CI, obligatoire, pas seulement le plan** (leçon de la PR #244) :
  rejouer un cycle `offer_fetching` réel et confirmer un `openai_call_completed` avec `total_tokens`
  non nul dans les logs — seule preuve que l'URL choisie fonctionne réellement en authentification par
  token. Revérifier au passage que le role assignment `caj` est toujours présent (simple confirmation,
  aucune recréation attendue ici).

---

## PR #245 — feat(backend): lien de désabonnement one-click signé HMAC (RFC 8058) pour le récap notifications

**Date :** 2026-07-26
**Branche :** `feature/notifications-one-click-unsubscribe` → `dev`

### Contexte

PR 2/2 du plan `docs/prompts/prompt-email-one-click-unsubscribe.md` (rédigé avec Claude Cowork, dans
le dépôt/worktree `job-finder` séparé — absent de cet arbre, cohérent avec les autres références de
prompt-file du projet). La PR #243 avait posé le secret Key Vault partagé
(`NOTIFICATIONS_UNSUBSCRIBE_SECRET`, wiré sur `notifications` et `webapp`) sans aucun code
consommateur. Cette PR ajoute le code applicatif : signature/vérification du token, endpoint de
désabonnement, et les en-têtes RFC 8058 sur l'envoi du récap.

Motivation RFC 8058 : sans les en-têtes `List-Unsubscribe`/`List-Unsubscribe-Post`, Gmail/Outlook
n'affichent pas de bouton natif de désabonnement — un destinataire agacé clique alors "Signaler comme
spam", ce qui dégrade la réputation d'envoi de tous les mails suivants via ACS. Les deux en-têtes
ensemble déclenchent le bouton natif et la désinscription en un clic, sans passer par le "Signaler
comme spam".

### Ce qui a été fait

- **`shared/unsubscribe_token.py`** (nouveau) : `sign_unsubscribe_token(user_id)` /
  `verify_unsubscribe_token(token)`, HMAC-SHA256 sur `user_id`, sans expiration par choix (voir
  Décisions techniques). Placé dans `shared/` plutôt que dans l'un des deux agents consommateurs —
  ni `agents/notifications` ni `agents/webapp` n'importe le code de l'autre.
- **`agents/webapp/routers/notifications.py`** (nouveau) : `POST/GET /notifications/unsubscribe`,
  premier endpoint non authentifié du webapp — l'identité vient du token signé, pas d'un JWT. Vide
  `UserProfile.notification_days` via un UPDATE idempotent ; réponse 200 identique que le profil
  existe ou non, pour ne pas révéler l'existence d'un compte à un appelant non authentifié.
  Enregistré dans `agents/webapp/main.py` (`app.include_router(notifications.router)`).
- **`agents/notifications/main.py`** : `_build_unsubscribe_url`, branché dans le pied de page de
  l'email (remplace l'ancien lien nu vers `/profile`) et dans `_send_digest` comme en-têtes
  `List-Unsubscribe` / `List-Unsubscribe-Post` sur l'appel `begin_send` d'Azure Communication
  Services.
- **`JobFinder/Terraform/envs/dev/container_apps.tf`** : ajout de la variable d'environnement
  `WEBAPP_BASE_URL` sur le Container App Job `job_notifications` (= `module.webapp.fqdn`) — découvert
  tardivement, après le merge de la PR #243, que l'agent a besoin de connaître l'URL publique du
  webapp lui-même (et non celle du frontend) pour construire ce lien : le POST automatisé du
  RFC 8058 vient du serveur/client mail, jamais d'un navigateur, donc il doit taper directement le
  backend FastAPI. Repris dans cette PR plutôt que d'ouvrir une troisième PR pour une seule variable.
- Tests : couverture de `shared/unsubscribe_token.py`, de l'endpoint `/notifications/unsubscribe`, et
  du lien/en-têtes RFC 8058 du récap (`tests/test_unsubscribe_token.py`,
  `tests/test_webapp_notifications.py`, `agents/notifications/tests/test_notifications.py`, fixtures
  `conftest.py` associées).

### Décisions techniques

- **Pas de JWT réutilisé pour ce token** : `agents/webapp/auth.py` valide contre Entra External ID
  (rotation de clés, audience) — hors sujet pour un token à usage unique (identifier un `user_id` pour
  un désabonnement, sans notion de session). Un HMAC dédié, scopé par un `_PURPOSE = "unsubscribe"`
  constant, suffit et évite de coupler ce cas à la logique Entra.
- **Pas d'expiration sur le token** : le pire cas d'un token deviné ou fuité est un désabonnement non
  désiré (`notification_days` réinitialisé à `[]`), pas une fuite de données — alors qu'un lien
  expiré après quelques jours produirait un pire résultat (clic "Signaler comme spam" par un
  utilisateur qui rouvre un vieil email).
- **`container_apps.tf` inclus dans une PR par ailleurs Python, malgré la règle invoquée par la
  PR #243** : l'entrée de la PR #243 justifiait explicitement le découpage en deux PR par l'interdit
  CLAUDE.md de mélanger plateforme (`envs/dev/`) et app dans une même PR. Cette PR réintroduit
  pourtant un changement `envs/dev/container_apps.tf` aux côtés du code Python — exactement le mélange
  que la PR #243 disait vouloir éviter. Accepté en connaissance de cause : une seule variable
  d'environnement découverte après coup, plutôt qu'une troisième PR pour ce seul ajout (voir
  Ce qui a été fait) ; la tension avec la justification de la PR #243 n'est pas résolue, seulement
  jugée mineure au regard du coût d'une PR dédiée à un `env` var.
- **`send_test_notification.py` non créé** : le prompt mentionne ce script pour une vérification
  manuelle via Gmail des en-têtes reçus. Son absence de tout l'historique (`git log --all
  --diff-filter=D`, déjà vérifié et signalé dans l'entrée de la PR #243) est reprise ici telle quelle,
  non re-vérifiée dans cette passe (pas d'accès Bash/`git log` depuis ce rôle, voir Vérification) —
  cette étape de vérification manuelle n'a pas été réalisée pour cette PR non plus.

### Vérification

- Relecture des docstrings des fichiers Python touchés (`shared/unsubscribe_token.py`,
  `agents/webapp/routers/notifications.py`, `agents/webapp/main.py`, `agents/notifications/main.py`)
  contre `conventions-python` (Google style, Args/Returns/Raises) :
  - `shared/unsubscribe_token.py` : le Returns de `verify_unsubscribe_token` qualifiait le user_id
    retourné d'"encoded" alors que le code retourne la valeur **décodée**
    (`base64.urlsafe_b64decode(...).decode()`) — corrigé.
  - `agents/webapp/routers/notifications.py` : `unsubscribe()` n'avait pas de section `Raises` alors
    qu'elle propage `SQLAlchemyError` depuis `_clear_notification_days` (500 côté appelant) — ajoutée.
  - `agents/notifications/main.py` : le docstring de module renvoyait, pour la contrainte
    "webapp et non le frontend" de `WEBAPP_BASE_URL`, vers `shared/unsubscribe_token.py` — ce module
    ne couvre que le HMAC/l'absence d'expiration/le placement partagé, pas cette distinction
    webapp/frontend. Corrigé pour pointer vers `_build_unsubscribe_url` (même fichier), qui l'explique
    réellement.
  - Le reste (`agents/notifications/main.py`, docstring de module hors ce renvoi, et
    l'enregistrement du router dans `main.py`) était déjà exact et complet — rien d'autre à changer.
- `container_apps.tf` : le commentaire au-dessus de `WEBAPP_BASE_URL` a été relu contre la valeur
  réelle de `module.webapp.fqdn` (`modules/container_app/outputs.tf` :
  `value = "https://${azurerm_container_app.this.ingress[0].fqdn}"`) — le schéma `https://` est bien
  inclus, donc les docstrings Python qui décrivent cette variable comme une "Base URL"/"Absolute URL"
  sont exactes ; pas de lien sans schéma à signaler.
- Pas d'accès Bash/`git diff`/`gh` depuis ce rôle. Numéro de PR dérivé du dernier titre `## PR #244`
  de ce fichier (+1 = #245) — confirmé exact ensuite via `gh pr list --state all --limit 3`.
- Aucune entrée `## PR #245` ni entrée existante pour cette branche dans `docs/JOURNAL.md` avant cette
  passe — nouvelle entrée ajoutée en fin de fichier.
- Deux corrections faites après la passe doc-writer, sur son signalement (hors périmètre docs) :
  - `shared/unsubscribe_token.py` : `hmac.compare_digest` lève `TypeError` (pas `ValueError`) sur un
    opérande `str` non-ASCII — un `signature` malveillant/corrompu extrait d'un token pouvait donc
    faire planter `verify_unsubscribe_token` (500 sur cet endpoint non authentifié) au lieu de
    renvoyer `None`. Corrigé en incluant l'appel `hmac.compare_digest` dans le `try` et en catchant
    aussi `TypeError`. Nouveau test `test_rejects_a_non_ascii_signature_without_raising`.
  - `shared/unsubscribe_token.py` : `_PURPOSE` était déclarée après le bloc fail-fast de
    `NOTIFICATIONS_UNSUBSCRIBE_SECRET`, violant la règle `conventions-python` (constantes
    immédiatement après les imports, avant toute variable d'environnement). Réordonné.
- **Revue `reviewer-backend` : CHANGEMENTS REQUIS, puis APPROUVÉ après corrections.**
  - Point bloquant : `agents/webapp/routers/notifications.py` déclarait `router`/`logger` avant
    les constantes `_INVALID_TOKEN_HTML`/`_UNSUBSCRIBED_HTML` — même violation d'ordre que
    `routers/cv.py` (non conforme), à l'inverse de `routers/profile.py` (conforme). Réordonné.
  - Remarque non-bloquante prise au sérieux et corrigée (pas seulement notée) : le endpoint
    répondait initialement de façon identique en GET et en POST, les deux désabonnant
    immédiatement. Or le lien visible du footer est un GET, et les liens visibles d'un email
    sont couramment suivis automatiquement par des prefetchers de liens (Outlook Safe Links,
    passerelles antivirus/anti-spam) sans intervention humaine — un GET qui mute aurait
    désabonné silencieusement des utilisateurs n'ayant jamais cliqué. Séparé en deux routes :
    `GET /notifications/unsubscribe` (nouveau `confirm_unsubscribe`) affiche désormais une page
    de confirmation avec un formulaire, sans aucune mutation ; `POST /notifications/unsubscribe`
    (`unsubscribe`, inchangé) reste la seule route qui vide `notification_days`. Le POST
    automatique RFC 8058 (`List-Unsubscribe-Post: List-Unsubscribe=One-Click`) continue de
    désabonner en un clic sans changement ; un humain doit désormais soumettre le formulaire
    (un second POST explicite) pour confirmer. Tests de `tests/test_webapp_notifications.py`
    réorganisés en conséquence (`TestConfirmUnsubscribeGet` / `TestUnsubscribePost`).
  - Remarque non-bloquante, corrigée : `python/.env.example` ne listait ni
    `NOTIFICATIONS_UNSUBSCRIBE_SECRET` ni `WEBAPP_BASE_URL` — ajoutées (le fichier reste
    incomplet pour d'autres variables déjà absentes avant cette PR, hors périmètre ici).
  - Remarque non-bloquante, non corrigée (hors périmètre, systémique à tous les agents CAJ) :
    aucun agent hors `agents/webapp/auth.py` n'appelle `load_dotenv()` — comportement préexistant
    à cette PR, pas introduit par elle.
- **Deuxième aller-retour `reviewer-backend` : CHANGEMENTS REQUIS, injection HTML réelle trouvée
  et corrigée.** En vérifiant spécifiquement la sécurité de l'interpolation de `token` dans
  l'attribut `action` de la page de confirmation (GET), le reviewer a démontré — pas seulement
  supposé — qu'un token peut être forgé pour contenir des caractères `"`/`<`/`>` tout en
  vérifiant toujours avec succès : le décodeur `base64.urlsafe_b64decode` de Python **ignore
  silencieusement** les octets hors alphabet au lieu de les rejeter, donc des caractères
  injectés dans le segment `encoded_user_id` (en nombre multiple de 4, pour ne pas dérégler le
  calcul du padding) sont simplement supprimés au décodage — le `user_id` récupéré et sa
  signature HMAC restent inchangés. Le commentaire précédent affirmant que l'alphabet d'un
  token vérifié est nécessairement sûr pour du HTML était donc factuellement faux. Reproduit et
  confirmé manuellement avant correction (`base64.urlsafe_b64decode('dXN""""lci0xMjM' + '=')`
  décode bien en `b'user-123'`, sans erreur). Corrections :
  - `agents/webapp/routers/notifications.py` : `_CONFIRM_HTML.format(token=token)` (violation
    du style f-strings-exclusif, seul usage de `.format()` du dépôt) remplacé par une fonction
    `_render_confirm_html(token)` qui échappe `token` via `html.escape()` avant de l'interpoler
    dans un f-string — même discipline que `CV.name`/`Offer.title`/`display_name` ailleurs dans
    le projet : ne jamais présumer qu'une valeur est sûre pour du HTML sous prétexte qu'elle a
    été validée pour un autre usage (ici, la vérification de signature).
  - Nouveau test `test_escapes_a_token_crafted_to_break_out_of_the_form_action_attribute` —
    forge un token avec 4 guillemets injectés, vérifie qu'il valide toujours
    (`verify_unsubscribe_token` retourne bien le user_id), puis que la page de confirmation
    l'échappe (`&quot;&quot;&quot;&#x27;` présent, `"""'` brut absent).
- **Troisième revue externe (hors reviewer-backend/-infra) : deux points appliqués, un rejeté
  comme non-bug, deux suggestions déclinées.**
  - Rejeté : "`_clear_notification_days` ne convertit pas `SQLAlchemyError` en réponse HTTP
    explicite, incohérent avec le reste du webapp" — vérifié faux par grep sur tous les
    `except SQLAlchemyError` de `agents/webapp/routers/*.py` (`cv.py`, `profile.py`,
    `matches.py`, `feedback.py`) : sans exception, chaque route logue puis relance nu
    (`raise`), laissant FastAPI produire le 500 par défaut — aucune ne convertit en
    `HTTPException` explicite. Le pattern de `notifications.py` est donc identique à
    l'existant, pas une régression ; corriger isolément ce fichier aurait introduit
    l'incohérence, pas résolu une incohérence préexistante.
  - Appliqué : absence d'expiration/révocation du token — rotation de
    `NOTIFICATIONS_UNSUBSCRIBE_SECRET` casse instantanément tous les liens déjà envoyés
    (emails immuables une fois délivrés, aucun rattrapage possible). Documenté directement
    dans `shared/unsubscribe_token.py` (nouveau paragraphe "Operational consequence") plutôt
    que seulement ici, pour rester visible à quiconque touche ce fichier plus tard : prévoir
    une période de transition acceptant l'ancien ET le nouveau secret dans
    `verify_unsubscribe_token` avant toute rotation, ou accepter la casse comme coût ponctuel
    assumé.
  - Appliqué : `_webapp_base_url` avec un slash final (`WEBAPP_BASE_URL=".../"` mal configuré)
    aurait produit `.../notifications//unsubscribe` (double slash). `module.webapp.fqdn`
    n'en a pas aujourd'hui (vérifié en PR #245 ci-dessus), mais `_build_unsubscribe_url` fait
    désormais `_webapp_base_url.rstrip("/")` avant de construire l'URL, par défense plutôt que
    par confiance dans la valeur Terraform actuelle. Nouveau test
    `test_webapp_base_url_has_no_trailing_slash_even_if_configured_with_one` — vérifié qu'il
    échoue bien sans le correctif avant de le committer (`git` diff temporaire, restauré
    ensuite), pas seulement écrit après coup.
  - Décliné : script `send_test_notification.py` pour vérifier manuellement les en-têtes RFC
    8058 via un vrai client mail — suggestion déjà reconnue comme un écart documenté (voir
    ci-dessus), pas un nouveau point, aucune action supplémentaire.
  - Décliné : ajouter un paramètre optionnel `issued_at`/`token_max_age` à `_signature` pour
    anticiper un futur besoin d'expiration. Explicitement qualifié de "low priority" par la
    suggestion elle-même et non requis par le besoin actuel — ajouter cette surface
    d'interface maintenant serait concevoir pour une exigence hypothétique plutôt que pour
    celle qui existe, à l'inverse de la convention du projet ("no premature complexity").
    Si un vrai besoin d'expiration apparaît un jour, l'ajouter à ce moment-là, avec ses propres
    tests, plutôt que de porter un paramètre mort dans l'intervalle.

## PR #247 — fix(frontend): élargir "Vos correspondances" et supprimer le trait vertical résiduel

**Date :** 2026-07-26
**Branche :** `feature/correspondances-width-fix` → `dev`

### Contexte

Retour direct de Vincent sur la page CV (`CVDetailSection.tsx`) : le texte d'analyse du CV occupe
trop de place à gauche par rapport à la liste des correspondances à droite, et un petit trait
vertical de 1px « qui dépasse » est visible tout en haut à gauche du bloc « Vos correspondances »,
avec l'apparence d'un glitch.

Vérifié en navigateur (session locale, CV `Willis-DELAMOUR`) avant tout correctif : le trait
n'est pas un artefact aléatoire mais la continuation logique du diviseur `border-r` (desktop) /
`border-b` (mobile) porté par la colonne de gauche. Cette bordure est posée sur l'élément qui a
aussi le `pt-2`/`lg:pt-5` (le décalage vertical partagé pour aligner le sélecteur de document
avec l'en-tête « Vos correspondances », voir le commentaire « aligné sur le haut du pill ») — la
`padding-top` est *à l'intérieur* de la boîte bordée, donc la bordure traverse aussi cette zone de
décalage, où rien n'existe encore côté droit (l'en-tête blanc de « Vos correspondances » ne
commence qu'après ce même décalage). Le résultat : un fragment de bordure visible seul contre le
fond sombre de la page, avant que le panneau n'ait visuellement commencé — exactement le
« glitch » signalé.

### Ce qui a été fait

- **`JobFinder/frontend/app/_components/CVDetailSection.tsx`** :
  - Largeur de la colonne CV/analyse (desktop) : `lg:w-1/2` → `lg:w-[42.5%]`, donnant plus d'espace
    à la colonne « Vos correspondances » (`flex-1`, donc ≈57.5% désormais). Ajusté en deux temps en
    session (`45%` d'abord, puis la moitié du décalage en plus sur retour de Vincent) — vérifié à
    chaque étape dans le navigateur plutôt que choisi à l'aveugle.
  - Décalage vertical du haut de cette même colonne : `pt-2 lg:pt-5` (padding) → `mt-2 lg:mt-5`
    (margin). La marge est *hors* de la boîte bordée : le diviseur ne traverse plus la zone de
    décalage et démarre net au niveau du pill/sélecteur de document, sans changer l'alignement
    avec l'en-tête « Vos correspondances » (le décalage total ligne-haut → contenu reste identique,
    seule sa nature padding/margin change).

### Vérification

- Session Chrome connectée (SSO Google existant) sur `localhost:3000`, CV réel
  `Willis-DELAMOUR-CV-DE...`, 71 correspondances.
- Avant/après comparés via `computer.zoom` sur la zone exacte du glitch (coin haut-gauche du bloc
  « Vos correspondances ») : le fragment de trait a disparu ; le diviseur reste continu jusqu'en
  bas de la liste (vérifié en plusieurs points, y compris tout en bas de la zone scrollable) ;
  l'alignement pill ↔ en-tête est inchangé.
- Layout mobile (< `lg`, iframe injectée à 375px de large, technique de
  `docs/JOURNAL.md` PR #203) rejoué après le changement `pt`→`mt` : aucune régression, le
  `border-b` et l'empilement des deux colonnes restent identiques à l'avant.
- Vignette du CV toujours entièrement visible (pas de recadrage) à la largeur de colonne réduite.

## PR #248 — fix(frontend): forcer `prompt=select_account` sur les redirections MSAL pour éviter le bug Entra External ID AADSTS165000

**Date :** 2026-07-26
**Branche :** `fix/msal-force-select-account` → `dev`

### Contexte

Suite du bug de reconnexion Google/CIAM déjà corrigé une première fois par PR #224
(`redirectInFlight`, single-flight sur `acquireTokenRedirect`). Vincent a reproduit le problème une
nouvelle fois après ce correctif et cette fois récupéré le message exact renvoyé par la CIAM :

```
AADSTS165000: Invalid Request: The request did not include the required tokens for the user
context. [...] Failure Reasons:[Token was not provided;]
```

Root cause identifiée (recherche web sur le code d'erreur, voir
https://learn.microsoft.com/en-us/answers/questions/5649443/) : un bug distinct de la race
condition déjà corrigée, documenté publiquement côté Microsoft Entra External ID et sans correctif
officiel à ce jour. Un utilisateur avec une session CIAM « rester connecté » active déclenche, au
retour sur l'app, un raccourci de reconnexion automatique vers le dernier fournisseur d'identité
(Google) qui transmet mal le `code_challenge` PKCE requis dans l'échange avec Google — la CIAM
rejette la réponse au retour avec `AADSTS165000`. Le contournement documenté côté client est de
forcer explicitement le sélecteur de compte (`prompt=select_account`), ce qui fait toujours passer
par le chemin normal (celui qui fonctionne).

### Ce qui a été fait

- **`JobFinder/frontend/lib/auth/msalConfig.ts`** :
  - `loginRequest` porte désormais `prompt: PromptValue.SELECT_ACCOUNT` — couvre les six appels
    `loginRedirect(loginRequest)` explicites répartis sur cinq fichiers (`AuthButton.tsx`,
    `LoginButton.tsx`, `app/profile/page.tsx`, `app/feedback/page.tsx`, et `UploadSection.tsx` qui
    en compte deux — un par point d'entrée non authentifié, drop de fichier et clic). Vérifié par
    grep qu'aucun ne passe par `ssoSilent`/`acquireTokenSilent`, qui n'accepte pas ce paramètre.
  - Nouvelle constante exportée `apiTokenRedirectRequest` (mêmes scopes que `apiTokenRequest`, plus
    `prompt: PromptValue.SELECT_ACCOUNT`), dédiée au fallback `acquireTokenRedirect` de
    l'intercepteur axios. Distincte de `apiTokenRequest` à dessein : cette dernière reste réservée au
    seul flow silencieux (`acquireTokenSilent`, qui n'accepte pas `prompt`).
- **`JobFinder/frontend/lib/api/client.ts`** : le fallback `acquireTokenRedirect` utilise désormais
  `apiTokenRedirectRequest` au lieu de `apiTokenRequest`. Le correctif single-flight `redirectInFlight`
  de PR #224 n'a pas été touché — les deux correctifs sont indépendants et cumulatifs.
- **Tests** :
  - `__tests__/client.test.ts` : l'assertion existante sur `acquireTokenRedirect` vérifie
    maintenant qu'il reçoit `prompt: "select_account"` (confirme que `client.ts` utilise bien
    `apiTokenRedirectRequest`, pas `apiTokenRequest`, pour cet appel).
  - Nouveau `__tests__/msalConfig.test.ts` : importe le **vrai** module `msalConfig.ts` (pas un
    mock) pour garantir que `apiTokenRequest` ne porte pas `prompt` et que `loginRequest` /
    `apiTokenRedirectRequest` portent bien `select_account` — une régression future y serait
    détectée même si `client.ts` ne change pas. `.env.local` n'étant pas chargé par Next.js quand
    `NODE_ENV=test`, les 4 variables `NEXT_PUBLIC_ENTRA_*` requises par le fail-fast de
    `msalConfig.ts` sont injectées à la main dans `process.env` avant le `require`.

### Décisions techniques

- **Effet secondaire assumé, pas une régression** : l'utilisateur devra désormais systématiquement
  choisir son compte Google à chaque connexion interactive — plus de reconnexion « en un clic » via
  le raccourci CIAM. Compromis délibéré pour éviter le bug Microsoft, à ne pas prendre pour un oubli
  lors d'une revue future.

### Vérification

- `npm test` (`JobFinder/frontend`) : 180 tests passent (tous, pas seulement les fichiers touchés).
- `npm run lint` et `npx tsc --noEmit` : aucune erreur.
- Test manuel en navigateur (session Chrome, `localhost:3000`, serveur `next dev` local) : clic sur
  « Se connecter » et lecture de l'URL de redirection réelle vers
  `jobfinderapp.ciamlogin.com/.../oauth2/v2.0/authorize` — confirmé `prompt=select_account` présent
  dans les paramètres de la requête envoyée à la CIAM. Reproduction complète du bug AADSTS165000
  (attente d'expiration réelle du refresh token) non rejouée dans cette session — seule la
  présence du paramètre dans le flux réel a été vérifiée.
- Relecture des docstrings des fichiers touchés (TypeScript, `conventions-frontend`) :
  - `msalConfig.ts` : le docstring de `apiTokenRequest` annonçait « Scopes requested at login »
    alors que son seul consommateur est `acquireTokenSilent` dans `lib/api/client.ts` (vérifié par
    grep) — corrigé. Celui de `apiTokenRedirectRequest` disait que `apiTokenRequest` était « also
    used for `acquireTokenSilent` », impliquant à tort un second consommateur — reformulé.
  - `__tests__/msalConfig.test.ts` : « `acquireTokenSilent` **rejects** a `prompt` param » (affirmait
    un comportement runtime non vérifiable depuis cette passe) → reformulé en « whose type doesn't
    accept a `prompt` param ».
  - Décompte des appels `loginRedirect(loginRequest)` corrigé dans cette même entrée : trois → six,
    répartis sur cinq fichiers (voir Ce qui a été fait).
- Pas d'accès Bash/`git diff`/`gh` depuis ce rôle. Numéro de PR dérivé du dernier titre `## PR #247`
  de ce fichier (+1 = #248) — non confirmé via GitHub dans cette passe.

## PR #249 — fix(ci): ajouter NOTIFICATIONS_UNSUBSCRIBE_SECRET au smoke-test webapp

**Date :** 2026-07-26
**Branche :** `fix/buildagents-webapp-smoke-test-secret` → `dev`

### Contexte

La feature de désabonnement en un clic (PR #243 infra, PR #245 code) a ajouté un import de
`shared/unsubscribe_token.py` dans le webapp (`agents/webapp/main.py` → `routers/notifications.py`
→ `shared/unsubscribe_token.py`), qui lève `ValueError` dès l'import si
`NOTIFICATIONS_UNSUBSCRIBE_SECRET` n'est pas posé (fail-fast, même pattern que les autres modules
`shared/*` — `DATABASE_URL` dans `shared/db.py`, `AZURE_SERVICEBUS_FULLY_QUALIFIED_NAMESPACE` dans
`shared/bus.py`, `AZURE_OPENAI_ENDPOINT` dans `shared/embedder.py`).

L'étape "Smoke-test webapp image" de `.github/workflows/buildAgents.yml` lance `python -c "import
main"` dans l'image webapp avec un set fixe de variables d'environnement — cette nouvelle variable
n'y avait jamais été ajoutée. Conséquence : le smoke-test échouait avec ce `ValueError`, le job
s'arrêtait à cette étape (shell par défaut `bash -e`, pas de `continue-on-error`), et toutes les
étapes suivantes ne s'exécutaient plus, y compris "Push webapp image to ACR", "Build and push
frontend image", et surtout "Update Container App and Container App Job images" — le seul step qui
contient tous les `az containerapp update`/`az containerapp job update` du repo (matching, cleanup,
fetch, fetch-sched, notifications, webapp, cv-analysis, match-analysis, frontend). Résultat concret
observé : `app-jf-dev-frc` tournait encore sur l'image d'avant la feature, `GET
/notifications/unsubscribe?token=...` renvoyait 404 alors que la route existe sur `dev` — pas un
problème de signature de token (DKIM/SPF/DMARC vérifiés `pass` sur un mail de test réel), un
problème de déploiement.

### Ce qui a été fait

- **`.github/workflows/buildAgents.yml`** : ajout de `-e NOTIFICATIONS_UNSUBSCRIBE_SECRET=x` à
  l'étape "Smoke-test webapp image". Commentaire réécrit pour lister explicitement les sept
  variables fail-fast couvertes et leur module d'origine : `DATABASE_URL` (`shared/db.py`),
  `AZURE_SERVICEBUS_FULLY_QUALIFIED_NAMESPACE` (`shared/bus.py`), `AZURE_OPENAI_ENDPOINT`
  (`shared/embedder.py`), `NOTIFICATIONS_UNSUBSCRIBE_SECRET` (`shared/unsubscribe_token.py`),
  `ENTRA_EXTERNAL_TENANT_ID`/`ENTRA_EXTERNAL_CLIENT_ID` (`agents/webapp/auth.py`),
  `AZURE_STORAGE_ACCOUNT_URL` (`agents/webapp/routers/cv.py`). Périmètre de la règle élargi de
  "tout module `shared/*`" à "tout module importé transitivement par `main.py`" (suite à une
  remarque de `reviewer-infra` sur la première version du commentaire, qui cadrait la règle plus
  étroitement que la réalité déjà couverte par la liste) — cette liste reste manuelle (pas
  d'introspection automatique des imports), documentée comme telle plutôt que rallongée
  silencieusement.
- Vérifié `agents/webapp/main.py` et les cinq routers qu'il importe (`cv`, `matches`, `profile`,
  `feedback`, `notifications`) en entier, pas seulement la ligne d'import en cause : les seuls
  modules qui lèvent au niveau module sont les six ci-dessus (quatre dans `shared/*`, deux dans
  `agents/webapp/`) — tous déjà couverts ou viennent de l'être, aucune autre variable manquante
  trouvée. `shared/config.py` utilise `os.getenv(..., default)` partout, jamais fail-fast.

### Vérification

- YAML validé (`yaml.safe_load`) après modification.
- Après merge : un push sur `dev` doit déclencher `buildAgents.yml` et faire aller le job jusqu'au
  bout, en particulier l'étape "Update Container App and Container App Job images". À vérifier
  après coup que `notifications`, `cv-analysis`, `match-analysis` et le frontend (tous bloqués par
  le même bug depuis son introduction) tournent bien sur l'image du commit du fix, pas une image
  plus ancienne.
- `GET /notifications/unsubscribe?token=<token valide>` sur `app-jf-dev-frc` doit renvoyer 200
  (page de confirmation), pas 404.

## PR #250 — fix(notifications): corriger trois bugs de rendu mobile du récap email

**Date :** 2026-07-27
**Branche :** `fix/notifications-email-mobile-render` → `dev`

### Contexte

Trois bugs de rendu visuels propres aux petits viewports mobiles (~360-390px) affectaient le
récap email quotidien (`agents/notifications/main.py`, contenu/template refondus en PR #241) :
le titre "Job Finder" et la frise calendaire de rappel de l'en-tête se chevauchaient, la pastille
d'un jour "sélectionné mais pas aujourd'hui" de cette même frise n'affichait qu'un mince bandeau de
7px coloré au lieu d'un contour complet autour de la pastille, et le texte des boutons (CTA
principal et bouton par CV) ne restait pas centré une fois passé à la ligne sur deux lignes.

### Ce qui a été fait

- **`agents/notifications/main.py`** :
  - `_render_header_html` : `white-space:nowrap` ajouté sur le `<td>` du titre, et un `<td>`
    espaceur fixe de 12px inséré entre le titre et la frise calendaire, pour empêcher leur
    collision sur les viewports étroits.
  - `_render_calendar_html` : la pastille d'un jour "sélectionné mais pas aujourd'hui" (deux `<td>`
    empilés par icône — un bandeau de 7px et un corps de 16px) porte désormais
    `border:1px solid {band}` sur les deux cellules empilées, avec `border-bottom:none` sur la
    cellule du haut et `border-top:none` sur celle du bas pour que les deux bordures se rejoignent
    sans doubler la ligne au milieu — commentaire WHY ajouté au-dessus de ce bloc. Seule
    `_render_calendar_html` a changé ; la signature et les valeurs de retour de
    `_calendar_day_style` sont restées inchangées (les tests `test_calendar_day_style_*` couvrent
    ce tuple), mais son docstring décrivait `band_color` comme la seule couleur du bandeau du
    haut — corrigé pour préciser qu'il sert aussi de couleur de contour à toute la pastille depuis
    ce correctif (voir Décisions techniques).
  - `_render_cta_html` et le bouton par CV dans `_render_cv_card_html` : ajout d'un
    `text-align:center` inline et d'un `line-height` égal à la `font-size` du bouton — commentaire
    WHY ajouté aux deux endroits (certains clients mail ignorent ou suppriment `<style>`/`@media`,
    et n'honorent alors pas l'alignement une fois le texte passé sur deux lignes). Le bouton CTA n'a
    pas la classe `.stack-btn` (seul le bouton par CV l'a) donc aucune règle `@media` ne le couvre
    du tout — l'inline y est la seule protection, pas un doublon défensif d'une règle CSS existante
    comme pour le bouton par CV. `align="center"` ajouté également sur le
    `<td>` du bouton par CV, qui ne le portait pas — cette cellule (celle avec
    `background-color:#2563eb`) n'a pas de rôle équivalent avec `align="center"` côté CTA : le
    bouton CTA est centré horizontalement via le `<td align="center">` englobant de la ligne
    (padding), pas sur la cellule du bouton lui-même.
- **`agents/notifications/tests/test_notifications.py`** : cinq nouveaux tests ajoutés —
  `test_render_calendar_html_wraps_selected_not_today_day_in_a_full_border`,
  `test_render_header_html_separates_title_and_calendar_with_a_spacer_cell`,
  `test_render_cta_html_centers_button_text_inline`,
  `test_render_cv_top_match_html_does_not_touch_button_markup` (garde-fou contre une confusion
  entre `_render_cv_top_match_html` et `_render_cv_card_html`, qui portent chacun un rendu
  distinct), `test_render_cv_card_html_centers_button_text_inline_and_on_wrapping_td`. Assertions
  vérifiées ligne à ligne contre le code actuel de `main.py` dans cette passe.

### Décisions techniques

- **Docstring de `_calendar_day_style` mise à jour, pas seulement vérifiée non-contradictoire** : sa
  description de `band_color` restait techniquement vraie (c'est toujours la couleur du bandeau)
  mais ne mentionnait plus son second usage introduit par ce correctif (couleur de bordure de toute
  la pastille dans `_render_calendar_html`) — complétée d'une clause plutôt que laissée telle
  quelle.
- **Fichier prompt non lisible depuis ce worktree, spec reprise de la consigne de tâche plutôt que
  du prompt lui-même** : `docs/prompts/prompt-fix-notifications-email-mobile-render.md` n'existe pas
  dans cette copie de travail — plus largement, tout le dossier `docs/prompts/` en est absent, y
  compris les prompts déjà cités par le docstring de module de `main.py` lui-même
  (`prompt-email-one-click-unsubscribe.md`) et par les entrées PR #241/#245 de ce journal. C'est un
  artefact de checkout/worktree (voir la note mémoire sur les prompts Cowork vivant sous
  `job-finder/docs/prompts/`, un autre dépôt/emplacement que celui-ci), pas une preuve que ce prompt
  n'a jamais existé — à ne pas confondre avec le cas `send_test_notification.py` documenté aux PR
  #241/#245, où l'absence avait été confirmée par `git log --all --diff-filter=D` (aucun accès Bash
  disponible depuis ce rôle pour rejouer une vérification équivalente ici).
- **`send_test_notification.py`, mentionné dans la consigne de tâche comme référence de ce même
  prompt** : reprise ici telle quelle, non re-vérifiée dans cette passe (pas d'accès Bash/`git log`
  depuis ce rôle) — cohérente avec l'absence déjà confirmée aux PR #241/#245.

### Vérification

- Relecture fonction par fonction des quatre fonctions modifiées et de `_calendar_day_style` :
  markup HTML actuel de `main.py` confronté aux cinq nouveaux tests listés ci-dessus (assertions sur
  `white-space:nowrap`, le `<td>` espaceur de 12px, le compte de `border:1px solid {couleur}` à 2,
  `text-align:center`/`line-height` sur les deux boutons, `align="center"` sur le `<td>` du bouton
  par CV) — correspondance confirmée dans cette passe.
- Suite complète (66 tests), rendu manuel via `_render_html_body` dans des iframes 375px/280px/640px
  et absence de régression au rendu ~640px : repris tels que rapportés dans la consigne de tâche,
  non rejoués dans cette passe (pas d'accès Bash depuis ce rôle).
- Numéro de PR dérivé du dernier titre `## PR #NNN` de ce fichier (#249) + 1, faute d'accès à `gh`
  depuis ce rôle (aucun outil Bash disponible) — non confirmé via GitHub dans cette passe.

## PR #251 — feat: solde de crédits dans PostHog + signal "je voudrais plus de crédits"

**Date :** 2026-07-27
**Branche :** `feature/credits-signals-and-request-more` → `dev`

### Contexte

Demande initiale de Vincent : dashboard Grafana "crédits dépensés par jour" + requête KQL pour
lister les utilisateurs à zéro crédit + réfléchir à un moyen de proposer plus de crédits. Après
investigation par Claude Cowork (voir `docs/prompts/prompt-credits-signals-and-request-more.md`),
le plan a changé de forme — **rien de tout ceci ne passe par Grafana, Terraform de monitoring ou
KQL** :

- `credit_consumed` est déjà capturé côté frontend en PostHog depuis PR #221 (24/07,
  `CorrespondancesPanel.tsx`), sur succès serveur uniquement. Vérifié en interrogeant PostHog
  directement : le pipeline fonctionne, mais `credit_consumed`/`credits_exhausted` étaient à 0
  occurrence faute d'usage réel — un Trend PostHog quotidien sur cet event donnera "crédits
  dépensés par jour" sans changement de code, une fois de l'usage disponible (hors périmètre de
  cette PR, Claude Cowork s'en charge).
- Pour la liste "zéro crédit" : aucune person property PostHog ne portait le solde. Il manquait une
  seule ligne pour rendre `analysis_credits_remaining` filtrable côté Persons — pas de Grafana/KQL
  nécessaire (Partie 1 ci-dessous).
- Pour "proposer plus de crédits" : Vincent voulait un signal léger, pas une vraie feature de
  rechargement — un bouton visible uniquement à 0 crédit, qui capture l'intérêt et alerte Vincent
  par email immédiatement plutôt que de devoir vérifier PostHog périodiquement (Parties 2-5).

Point d'architecture qui a simplifié l'implémentation : le webapp partage déjà l'identité managée
`caj`, qui détient déjà le rôle `Communication and Email Service Owner` sur la ressource ACS
(PR #236) — envoi d'email possible sans aucun changement RBAC, seulement deux nouvelles variables
d'environnement (Partie 4).

### Ce qui a été fait

- **`JobFinder/frontend/app/_components/CreditsBadge.tsx`** : `fetchCredits()` appelle désormais
  `posthog.setPersonProperties({ analysis_credits_remaining })` à chaque fetch réussi (rien sur le
  404 "pas encore de profil"). Rend le solde filtrable côté PostHog Persons — c'est la seule chose
  nécessaire pour que la liste "zéro crédit" existe. Tests étendus dans
  `__tests__/CreditsBadge.test.tsx` (mock `posthog-js`, vérifie l'appel à chaque fetch réussi et
  son absence quand non authentifié).
- **`JobFinder/python/migrations/versions/035_add_more_credits_requested_at.py`** (révision 035,
  down_revision 034) : colonne nullable `more_credits_requested_at` sur `user_profiles`. Pas de
  backfill (`NULL` = "jamais demandé", correct par construction — même logique que 031/034), pas
  d'index (lue uniquement en comparaison sur une ligne déjà chargée par clé primaire). Champ
  correspondant ajouté sur `UserProfile` dans `shared/models.py`, à côté des autres champs crédits.
- **`POST /profile/credits/request-more`** (`JobFinder/python/agents/webapp/routers/profile.py`) :
  authentifié (tout utilisateur, pas admin-only comme `refill_credits`), 202 Accepted. No-op
  silencieux (toujours 202, ne révèle jamais l'état interne) sauf si
  `analysis_credits_remaining == 0`. À 0 crédit : compare `more_credits_requested_at` à une
  nouvelle constante `MORE_CREDITS_REQUEST_COOLDOWN_SECONDS` (`shared/config.py`, défaut 86400s/24h,
  même pattern que `INTENT_DISPATCH_COOLDOWN_SECONDS`) pour décider si un email d'alerte part vers
  `OWNER_ALERT_EMAIL` via Azure Communication Services (singleton module-level `EmailClient`, même
  pattern que le `_blob_service_client` de `routers/cv.py`) — mais `more_credits_requested_at` est
  toujours réécrit à `now`, que l'email parte ou soit dédupliqué par le cooldown. Panne ACS loguée
  et tolérée, ne fait jamais échouer la requête HTTP (même trade-off que
  `match_analysis_request_dispatch_failed`). Nouvelles variables d'environnement fail-fast
  `ACS_EMAIL_ENDPOINT_HOSTNAME`, `ACS_EMAIL_SENDER_ADDRESS`, `OWNER_ALERT_EMAIL`, ajoutées comme
  stubs à `tests/conftest.py`. Tests dans `tests/test_webapp_profile.py`
  (`TestRequestMoreCredits`) — docstring du module de test étendu pour lister aussi la couverture
  `/credits/refill` et `/credits/request-more`, absente de la liste précédente. Suite à une
  remarque bloquante de `reviewer-backend` (`request_more_credits` mélangeait trois
  responsabilités — porte DB, timestamp, envoi d'email — sur ~75 lignes), l'envoi d'email a été
  extrait dans un helper privé placé juste avant, sur le modèle de `_dispatch_start_matching`/
  `_dispatch_cv_reanalysis` déjà présents dans ce fichier. Extraction pure, aucun changement de
  comportement.
- **`JobFinder/Terraform/envs/dev/webapp.tf`** : les trois variables ci-dessus ajoutées à
  `env_vars` du module `webapp`, sourcées depuis `module.email_communication` (déjà utilisé par
  `job_notifications`) et `var.alert_email` (déjà utilisé par l'action group `owner`). Aucun
  nouveau rôle, aucune nouvelle ressource. `terraform fmt -check`/`validate`/`plan` propres sur
  `envs/dev` — le plan ne touche que les `env_vars` du module `webapp`, drift pré-existant (jumpbox,
  tags d'image) confirmé sans rapport via isolation stash/pop.
- **Bouton "Je voudrais plus de crédits"** : nouvel état `creditsExhausted` (booléen, scopé par
  offre comme `analysisError`) posé dans `CorrespondancesPanel.tsx::requestAnalysis` sur la branche
  402 existante → threadé dans `MatchItemData` (`MatchItem.tsx`) → consommé par
  `MatchAnalysisPanel.tsx` (nouveau sous-composant `MoreCreditsCta`) : au clic, POST
  `/credits/request-more`, `posthog.capture("more_credits_requested")`, bascule optimiste (sans
  attendre la réponse API) vers "Merci, votre demande a été transmise !", état local à l'instance du
  panneau (la demande est globale à l'utilisateur, pas à cette offre). Tests étendus dans les trois
  fichiers de composants concernés, plus `MatchList.test.tsx` (nouveaux mocks `posthog-js` et
  `@/lib/api/client`, désormais importés transitivement via `MatchAnalysisPanel`). Suite à une
  remarque non-bloquante de `reviewer-frontend`, `creditsExhausted` est désormais réinitialisé
  dans `toggleExpand` aux côtés d'`analysisError` — sans ce reset, rouvrir une offre après un 402
  survenu sur une offre différente pouvait afficher un CTA obsolète.

### Décisions techniques

- **Pas de test dédié upgrade/downgrade pour la migration 035**, contrairement à ce que listait la
  section "Vérification attendue" du prompt initial : aucune des 34 migrations précédentes n'en a
  un — la suite de tests mocke entièrement la session DB, il n'existe nulle part dans le repo de
  test de migration sur une vraie base. Précédent suivi plutôt qu'introduction d'un pattern
  ponctuel isolé. À noter explicitement ici pour qu'une session future ne redécouvre pas ce même
  écart et ne le prenne pas pour un oubli.
- **Correction doc appliquée pendant cette passe** (`doc-writer`) : le docstring de la migration
  035 et le commentaire du champ `more_credits_requested_at` dans `shared/models.py` affirmaient
  tous deux que la colonne n'était réécrite que "whenever the request isn't deduplicated by the
  cooldown" — faux, le code (`routers/profile.py`) la réécrit inconditionnellement à chaque appel
  accepté (une fois la porte 0-crédit passée), seul l'envoi de l'email dépend de la déduplication.
  Corrigé dans les deux fichiers ; le test
  `test_deduplicates_email_within_cooldown_but_still_stamps_timestamp` couvre déjà ce comportement.
- Mélange Terraform (`envs/dev`) + Python (webapp) + frontend dans une seule PR : autorisé par les
  règles du repo (seul le mélange `envs/lz_*` + `envs/dev` est interdit), précédent déjà établi par
  PR #235.

### Vérification

- `pytest` : 469 tests passent (inchangé après l'extraction `_send_credits_alert_email`, refactor
  pur — les 53 tests de `test_webapp_profile.py` passent sans modification).
- `jest` : 185 tests passent (22 suites, inchangé après le reset `creditsExhausted` dans
  `toggleExpand` — les 27 tests de `CorrespondancesPanel.test.tsx` passent sans modification).
- `tsc --noEmit` et `eslint` : propres sur les fichiers touchés.
- `terraform fmt -check` / `validate` / `plan` propres sur `envs/dev`.
- Vérification manuelle post-merge (Vincent, pas Claude Code) : après apply CI, cliquer le bouton
  en dev et confirmer la réception réelle de l'email — non fait dans cette passe, Claude Code n'a
  pas accès à la boîte mail.
- Numéro de PR confirmé via `gh pr list` : #250 est déjà pris par une PR ouverte sans rapport
  (`fix(notifications): ...`), donc #251 (et non #249 + 1 = #250 comme l'aurait laissé supposer le
  dernier titre de ce fichier).

## PR #252 — fix(ci): ajouter les variables ACS au smoke-test webapp

**Date :** 2026-07-27
**Branche :** `fix/buildagents-webapp-smoke-test-acs-vars` → `dev`

### Contexte

Même classe de bug que PR #249, à peine un jour après : PR #251 a ajouté trois nouvelles variables
d'environnement fail-fast dans `agents/webapp/routers/profile.py`
(`ACS_EMAIL_ENDPOINT_HOSTNAME`, `ACS_EMAIL_SENDER_ADDRESS`, `OWNER_ALERT_EMAIL`, pour l'endpoint
`POST /credits/request-more`), sans les ajouter à l'étape "Smoke-test webapp image" de
`.github/workflows/buildAgents.yml`, qui lance `python -c "import main"` dans l'image webapp avec
un set fixe de variables. Conséquence observée après merge de PR #251 sur `dev` : le smoke-test
échouait avec `ValueError: ACS_EMAIL_ENDPOINT_HOSTNAME environment variable is not set`, bloquant
le job avant l'étape "Update Container App and Container App Job images" — comme pour PR #249,
tous les services restaient sur l'image précédente tant que ce step n'était pas corrigé.

### Ce qui a été fait

- **`.github/workflows/buildAgents.yml`** : ajout de `-e ACS_EMAIL_ENDPOINT_HOSTNAME=...`,
  `-e ACS_EMAIL_SENDER_ADDRESS=...`, `-e OWNER_ALERT_EMAIL=...` à l'étape "Smoke-test webapp
  image", et mise à jour du commentaire listant les variables fail-fast couvertes et leur module
  d'origine. Repro locale avant/après (import direct de `main` avec `PYTHONPATH` pointant sur
  `agents/webapp`, hors Docker) : échec reproduit à l'identique avec l'ancien set de variables,
  succès avec le nouveau.

### Décisions techniques

- Ce type de régression (nouvelle variable fail-fast oubliée dans le smoke-test) s'est maintenant
  produit deux fois en trois PRs (#249, puis #250 et #251 sans incident, puis cette PR). La liste
  reste volontairement manuelle (voir commentaire dans le workflow) plutôt que dérivée
  automatiquement des imports — accepté comme compromis pour l'instant, mais à surveiller si ça se
  reproduit une troisième fois.

### Vérification

- YAML validé (`yaml.safe_load`).
- Import de `agents/webapp/main.py` reproduit localement (hors Docker, `PYTHONPATH` pointant sur
  le dossier `agents/webapp`) : échoue avec l'ancien set de variables (reproduit exactement l'erreur
  CI rapportée), réussit avec le nouveau.
- Après merge : un push sur `dev` doit déclencher `buildAgents.yml` et faire aller le job jusqu'au
  bout, y compris "Update Container App and Container App Job images" pour tous les services.

## PR #254 — fix(webapp): cooldown crédits déclenché par un envoi ACS en échec + export Application Insights du webapp

**Date :** 2026-07-27
**Branche :** `fix/credits-request-cooldown-and-webapp-telemetry` → `dev`

### Contexte

Deux corrections indépendantes, regroupées dans une même PR (même règle que PR #235/#251 :
seul le mélange `envs/lz_*` + `envs/dev` est interdit, `envs/dev` + Python webapp est autorisé).

- **Bug cooldown (`POST /profile/credits/request-more`, introduit par PR #251)** :
  `more_credits_requested_at` était réécrit en base **avant** de savoir si
  `_send_credits_alert_email` avait réellement réussi. Un premier envoi ACS en échec
  démarrait quand même le cooldown de `MORE_CREDITS_REQUEST_COOLDOWN_SECONDS` (24h),
  bloquant silencieusement tous les clics suivants pendant 24h sans que l'alerte
  n'atteigne jamais Vincent — l'endpoint renvoie toujours 202, donc l'utilisateur ne
  voyait jamais l'échec côté frontend. Effet de bord additionnel : un clic dédupliqué
  (dans la fenêtre de cooldown) réécrivait quand même la colonne à chaque appel,
  prolongeant silencieusement le cooldown indéfiniment tant que l'utilisateur recliquait.
- **Télémétrie webapp jamais exportée** : le module `webapp` (`envs/dev/webapp.tf`) n'a
  jamais eu `APPLICATIONINSIGHTS_CONNECTION_STRING` câblée, contrairement à tous les
  Container App Jobs (`container_apps.tf`) qui l'ont depuis leur création — oubli initial,
  jamais corrigé depuis. Conséquence : aucun `logger.info(...)` du webapp n'a jamais atteint
  AppTraces dans Application Insights ; `configure_telemetry()` (`shared/telemetry.py`,
  appelé depuis `agents/webapp/main.py`) tournait en permanence en mode dégradé
  (`telemetry_disabled`, no-op silencieux) sans que rien ne le signale.

### Ce qui a été fait

- **`JobFinder/python/agents/webapp/routers/profile.py`** (`request_more_credits`,
  `_send_credits_alert_email`) : restructuration de l'ordre des opérations. Le SELECT du
  profil reste dans son propre `try/except SQLAlchemyError` → 500. La porte 0-crédit est
  vérifiée juste après. `deduplicated` se calcule à partir de la valeur *existante* de
  `more_credits_requested_at` (inchangé). Seulement si NON dédupliqué,
  `_send_credits_alert_email` est appelé ; seulement si celui-ci retourne `True`,
  l'`UPDATE ... more_credits_requested_at = now` + commit s'exécute (dans son propre
  `try/except SQLAlchemyError` → 500). Un clic dédupliqué ne touche donc plus la DB du
  tout — l'effet de bord de réécriture silencieuse à chaque clic dédupliqué disparaît
  aussi, puisque seul un envoi *réussi* stampe désormais la colonne. Docstrings de
  `request_more_credits` et `_send_credits_alert_email` mises à jour pour refléter le
  nouvel ordre (la seconde ne décrit plus un envoi fire-and-forget avec commit préalable
  — c'est désormais un appel bloquant dont la valeur de retour conditionne le commit).
  Suite à deux remarques non-bloquantes de `reviewer-backend`, les trois échecs distincts
  de ce flux (lookup profil, échec envoi ACS, échec UPDATE du stamp) portent désormais
  chacun leur propre nom d'événement (`more_credits_lookup_failed`,
  `more_credits_alert_email_failed`, `more_credits_stamp_failed`, au lieu du même
  `more_credits_requested_failed` pour les trois) et `_send_credits_alert_email` loggue
  `more_credits_alert_email_started` avant l'appel ACS, sur le modèle de
  `_dispatch_start_matching`/`_dispatch_cv_reanalysis`.
- **`JobFinder/python/tests/test_webapp_profile.py`** (`TestRequestMoreCredits`) : renommé
  `test_deduplicates_email_within_cooldown_but_still_stamps_timestamp` →
  `test_deduplicates_email_within_cooldown_without_restamping` (assertion inversée,
  `commit.assert_called_once()` → `commit.assert_not_called()`), renommé
  `test_acs_failure_is_tolerated_and_still_returns_202` →
  `test_acs_failure_is_tolerated_returns_202_and_does_not_start_a_cooldown` (même
  inversion). Ajout de `test_retries_immediately_after_a_failed_send` : premier appel
  avec `begin_send` qui lève `AzureError`, second avec un `begin_send` qui réussit
  (`MagicMock`) — vérifie que les deux appels renvoient 202, que `begin_send` est appelé
  deux fois (donc pas dédupliqué malgré l'échec du premier), et que `commit` n'est appelé
  qu'une seule fois, pour l'envoi réussi.
- **`JobFinder/Terraform/envs/dev/webapp.tf`** : ajout de
  `{ name = "appinsights-connection-string", value = module.application_insights.connection_string }`
  à `secrets` et `{ name = "APPLICATIONINSIGHTS_CONNECTION_STRING", secret_name =
  "appinsights-connection-string" }` à `env_vars` du module `webapp` — copie exacte du
  pattern déjà en place pour chaque Container App Job dans `container_apps.tf`. Aucun
  changement RBAC, aucune nouvelle ressource ; `shared/telemetry.py` lit déjà ce nom de
  variable et se dégrade silencieusement (log `telemetry_disabled`) en son absence, donc
  côté Python rien à changer pour ce volet.

### Décisions techniques

- **Corrections doc appliquées pendant cette passe (`doc-writer`)** : PR #251 avait
  documenté (docstring de la migration 035, commentaire du champ dans `shared/models.py`,
  commentaire de `MORE_CREDITS_REQUEST_COOLDOWN_SECONDS` dans `shared/config.py`) que
  `more_credits_requested_at` était réécrit *inconditionnellement* à chaque appel accepté,
  seul l'envoi d'email étant dédupliqué par le cooldown — exact au moment où PR #251 a été
  écrite, mais rendu faux par cette PR. Les trois commentaires ont été corrigés pour
  refléter le nouveau comportement (stamp uniquement sur envoi réussi), avec renvoi vers
  cette entrée de JOURNAL.
- **Numéro de PR** : confirmé via `gh pr list` — #253 est déjà pris par une PR ouverte sans
  rapport, #252 est la dernière mergée ; #254 (et non #252 + 1 = #253 comme l'aurait laissé
  supposer une simple incrémentation depuis le dernier titre de ce fichier). Le numéro
  #254 est référencé en dur dans quatre commentaires de code (`profile.py`, `models.py`,
  `config.py`, `035_add_more_credits_requested_at.py`) — si le numéro final de la PR
  diffère, ces quatre fichiers et cette entrée doivent être mis à jour ensemble.
- Même règle de mélange de couches que PR #235/#251 : `envs/dev` (Terraform) + Python
  webapp dans une seule PR, autorisé (seul `envs/lz_*` + `envs/dev` est interdit).

### Vérification

- 475 tests backend passent (54 dans `test_webapp_profile.py`).
- `terraform fmt -check` / `validate` / `plan` propres sur `envs/dev` : le plan isolé
  (stash/pop d'un checkout non modifié) montre que `module.webapp.azurerm_container_app.this`
  était déjà en "will be updated in-place" avant ce diff, à cause d'un drift pré-existant
  déjà documenté dans des entrées de JOURNAL antérieures (tag d'image, `workload_profile_name`
  passant à null) — ce diff ajoute exactement un bloc `secret` et un bloc `env` en plus,
  aucun remplacement de ressource imputable à cette PR.
- Vérification manuelle post-merge (Vincent, pas Claude Code) : après apply CI, recliquer
  sur "Je voudrais plus de crédits" et confirmer dans **AppTraces** (et non
  `ContainerAppConsoleLogs_CL` — les logs structlog du webapp n'y arrivaient jamais avant
  cette PR) l'apparition d'une ligne `more_credits_requested_completed` avec
  `email_sent: true` — preuve que les deux correctifs fonctionnent ensemble.

## PR #253 — fix(frontend): rafraîchissement des badges de compétences après une analyse manuelle

**Date :** 2026-07-27
**Branche :** `fix/manual-analysis-badge-refresh` → `dev`

### Contexte

Après une analyse manuelle d'une offre (bouton "Analyser"), les badges de compétences sur la carte
restaient invisibles tant que la page n'était pas rafraîchie, alors même que le spinner disparaissait
et l'analyse s'affichait correctement dès que le polling la détectait terminée. Cause racine dans
`CorrespondancesPanel.tsx` : le `useEffect` de polling ne copiait que le champ `analysis` de la
réponse `/matches/cv/{cvId}` dans `analysisOverrides` (son state local qui prime sur le prop
`matches` jusqu'au prochain refetch complet), jamais `offer` — or les badges de compétences
s'affichent depuis `offer.key_skills`, un champ `null` tant qu'aucune analyse n'a tourné et qui
n'est mis à jour que dans un `offer` frais. `toItemData` ne fusionnait donc jamais le `key_skills`
à jour tant que `matches` (le prop) ne se rechargeait pas lui-même — ce qui n'arrive qu'au
changement de CV/zone ou à un refresh de page.

### Ce qui a été fait

- **`JobFinder/frontend/app/_components/CorrespondancesPanel.tsx`** : le polling (`useEffect`
  autour de la ligne 104-143) garde désormais `{ offer, analysis }` dans `analysisOverrides` au
  lieu de seulement `analysis`, et `toItemData` (ligne ~307) fusionne les deux champs de l'override
  au lieu d'un seul. Commentaire WHY ajouté au-dessus de la construction de `byOffer` dans le
  polling pour expliquer pourquoi `offer` doit voyager avec `analysis` (sans lui, les badges restent
  masqués malgré une analyse terminée).
- **`JobFinder/frontend/__tests__/CorrespondancesPanel.test.tsx`** : nouveau test de non-régression
  "shows skill badges as soon as polling picks up completion, without a page refresh", ajouté juste
  après le test existant "polls and picks up completion for a pending analysis the user never
  clicked" — vérifie que les badges (`Terraform`, `Azure`) apparaissent dès le tick de polling qui
  détecte la complétion, sans dépendre d'un refetch de `matches`.

**Vérification :** relecture du polling et de `toItemData` confrontée au nouveau test ; aucun autre
endroit du composant ne lisait `key_skills` depuis une source qui aurait pu rester obsolète par
ailleurs.

## PR #255 — fix(frontend): corrige le chemin API du bouton "plus de crédits"

**Date :** 2026-07-27
**Branche :** `fix/request-more-credits-wrong-path` → `dev`

### Contexte

`MatchAnalysisPanel.tsx` appelait `apiClient.post("/credits/request-more")`, un chemin qui n'a
jamais existé : le router `profile.py` (`JobFinder/python/agents/webapp/routers/profile.py:38`)
est monté avec `prefix="/profile"`, donc l'endpoint réel est `/profile/credits/request-more` —
exactement comme `AdminRefillButton.tsx` appelle déjà correctement `/profile/credits/refill`. Le
clic sur "Je voudrais plus de crédits" affichait quand même la confirmation optimiste (voir PR
#251/#254) puisque `requestMoreCredits()` ne dépend pas de la réponse pour basculer son state
local, donc le bug 404 passait inaperçu côté UI comme en CI — le test associé asserte lui-même
l'ancien chemin erroné, ce qui l'a laissé passer sans jamais taper le vrai endpoint.

### Ce qui a été fait

- **`JobFinder/frontend/app/_components/MatchAnalysisPanel.tsx`** : `apiClient.post(...)` pointe
  désormais vers `/profile/credits/request-more` ; le commentaire WHY juste au-dessus, qui
  référençait déjà (mais avec le mauvais chemin) `POST /credits/request-more`, est corrigé en
  même temps.
- **`JobFinder/frontend/__tests__/MatchAnalysisPanel.test.tsx`** : l'assertion
  `expect(apiClient.post).toHaveBeenCalledWith(...)` vérifie maintenant `/profile/credits/request-more`.

### Vérification

- `npx jest __tests__/MatchAnalysisPanel.test.tsx` : 9/9 tests passent.
- Recherche de toute autre occurrence de `/credits/request-more` (sans le préfixe) dans
  `JobFinder/frontend` : aucune restante.
- Vérification manuelle post-merge (Vincent, pas Claude Code) : recliquer sur "Je voudrais plus
  de crédits" en dev et confirmer dans **AppTraces** (message contenant `"more_credits_requested"`)
  qu'un `more_credits_requested_started` puis `_completed` apparaissent enfin — la preuve que la
  requête atteint désormais le backend, ce qui n'était jamais arrivé avant cette PR malgré la
  confirmation optimiste affichée côté UI.

## PR #256 — fix(backend): objet et corps du mail d'alerte crédits plus actionnables

**Date :** 2026-07-27
**Branche :** `fix/credits-alert-email-content` → `dev`

### Contexte

Le mail envoyé à `OWNER_ALERT_EMAIL` par `_send_credits_alert_email` (déclenché par
`POST /profile/credits/request-more`, voir PR #251/#254/#255) avait un objet générique
("Job Finder — demande de crédits supplémentaires") identique à chaque envoi, et un corps
narratif en une phrase mélangeant nom, user_id et email conditionnellement. Vincent doit pouvoir
identifier l'auteur de la demande dès l'objet du mail (utile en scan rapide depuis une
notification push) et retrouver nom/mail/user_id sur des lignes séparées dans le corps, sans
avoir à parser une phrase.

### Ce qui a été fait

- **`JobFinder/python/agents/webapp/routers/profile.py`** (`_send_credits_alert_email`,
  ligne ~518) :
  - `subject` devient `f"CREDITS REQUEST : {who}"` (`who` déjà calculé juste au-dessus =
    `display_name or email or user_id`).
  - `plainText` devient trois lignes fixes (`Nom`, `Mail`, `user id`), chacune avec un fallback
    `"non renseigné"` pour `display_name`/`email` — contrairement à `who`, ces deux champs
    s'affichent maintenant indépendamment l'un de l'autre plutôt qu'en cascade.
- **`JobFinder/python/tests/test_webapp_profile.py`**
  (`TestRequestMoreCredits.test_sends_alert_email_and_stamps_timestamp_at_zero_credits`) : le
  profile de test fixe désormais `display_name`/`email` à des valeurs concrètes
  (`"Jane Doe"` / `"jane@test.example.com"`, au lieu des `MagicMock` par défaut de
  `_make_profile`), et le test asserte l'objet et le corps exacts du mail plutôt que seulement
  l'adresse du destinataire.

### Vérification

- `pytest tests/test_webapp_profile.py` : 54/54 passent (8/8 sur `TestRequestMoreCredits`).
- Recherche globale de l'ancien texte narratif ("demande de crédits supplémentaires", "est à 0
  crédit") : aucune occurrence résiduelle en dehors d'un libellé de `describe()` Jest sans
  rapport (`MatchAnalysisPanel.test.tsx`).
- Vérification manuelle post-merge (Vincent, pas Claude Code) : recliquer sur "Je voudrais plus
  de crédits" en dev et confirmer visuellement le nouvel objet et le nouveau corps dans l'email
  reçu.

## PR #257 — feat: plafond de CVs à 2 emplacements débloqués (portfolio-readiness)

**Date :** 2026-07-27
**Branche :** `feature/cv-slot-lock-portfolio` → `dev`

### Contexte

Effort "portfolio-readiness" : minimiser le coût récurrent par utilisateur (extraction PDF,
embedding, extraction ROME, matching quotidien) tout en gardant visible la fonctionnalité
différenciante multi-CV de l'app. Prompt Cowork
(`docs/prompts/prompt-cv-slot-lock-portfolio.md`, dépôt principal job-finder, pas ce worktree).

### Ce qui a été fait

- **`JobFinder/python/shared/constants.py`** : nouvelle constante `MAX_CVS_PER_USER: int = 2`,
  déclarée avec les autres constantes de module, commentaire WHY expliquant qu'elle est la seule
  source de vérité côté serveur et qu'elle doit être tenue synchronisée manuellement avec
  `UNLOCKED_CV_SLOTS` côté frontend (aucune source commune entre les deux runtimes aujourd'hui).
- **`JobFinder/python/agents/webapp/routers/cv.py`** (`upload_cv`) : garde ajoutée juste après la
  vérification du `content_type`, avant `file.read()` — un `COUNT` sur `cvs` filtré par `user_id`
  (même pattern non indexé que `list_cvs` existant, pas une régression) ; renvoie 403 si
  `existing_count >= MAX_CVS_PER_USER`, avec un log `cv_upload_rejected_at_cap`. Docstring mise à
  jour (`Raises: HTTPException 403`, et `413` ajouté au passage — omis avant cette PR alors que
  `MAX_PDF_BYTES` existait déjà).
- **`JobFinder/python/tests/test_webapp_cv.py`** : nouveau test `test_rejects_upload_at_cap`, et
  `test_rejects_empty_pdf_magic_bytes` paramétré pour vérifier que le garde-fou laisse bien passer
  une requête sous le plafond avant d'atteindre la vérification suivante.
- **`JobFinder/frontend/lib/cvSlots.ts`** (nouveau) : `UNLOCKED_CV_SLOTS = 2` et
  `TOTAL_LIBRARY_SLOTS = 10` — la grille de la bibliothèque garde ses 10 cellules, elle ne
  rétrécit pas.
- **`JobFinder/frontend/app/_components/CVCardLocked.tsx`** (nouveau) : carte verrouillée (icône
  `Lock` de lucide-react + `title` "Emplacement non disponible pour le moment"), affichée par
  `LibrarySection.tsx` pour chaque emplacement au-delà de `UNLOCKED_CV_SLOTS`. Le badge d'en-tête
  affiche désormais "x / 2" au lieu de "x / 10".
- **`JobFinder/frontend/app/_components/UploadSection.tsx`** : les trois chemins de déclenchement
  d'upload (`handleFile`, `handleClick`, la méthode impérative `openPicker` exposée via
  `useImperativeHandle`) sont bloqués dès que `cvCount >= UNLOCKED_CV_SLOTS` — nouvelle prop
  `cvCount` passée depuis `HomeClient.tsx` (`cvList.length`). Message rouge "Tous vos emplacements
  sont occupés" et animation `shakeReject` (nouveau `@keyframes` dans `app/globals.css`) sur la
  zone de dépôt.
- **`JobFinder/frontend/__tests__/UploadSection.test.tsx`** (nouveau) et
  **`LibrarySection.test.tsx`** (bloc `describe` ajouté pour les emplacements verrouillés).
- **`JobFinder/frontend/app/_components/LibrarySection.tsx`** : commentaire WHY ajouté au-dessus
  du slice `realCvs` (voir Décisions techniques ci-dessous).

### Décisions techniques

- **2 emplacements débloqués, pas 1.** Un seul emplacement aurait entièrement évité un bug de
  non-déterminisme connu dans l'extraction des codes ROME (uploader deux fois le même CV peut
  aujourd'hui produire des codes ROME différents → des pools de matching différents — voir
  JOURNAL/mémoire de session autour de `gpt-5-mini`), mais 2 a été choisi délibérément pour
  continuer à démontrer la fonctionnalité de recherche multi-CV. Ce bug est explicitement hors
  scope de cette PR et ne doit pas être rouvert ici.
- **Deux constantes séparées, aucune source commune.** `MAX_CVS_PER_USER` (Python) et
  `UNLOCKED_CV_SLOTS` (TypeScript) vivent dans deux runtimes distincts sans mécanisme de
  synchronisation automatique — elles doivent être maintenues à la main. Exposer le plafond via
  l'API pour éliminer cette duplication est explicitement différé : aucun système de plan/tier
  n'existe encore sur `UserProfile`. Si les deux valeurs venaient à diverger avec le frontend
  au-dessus du backend, `handleFile` avale silencieusement l'échec 403 (`.catch(() => {})`) — la
  carte optimiste apparaît puis disparaît sans message d'erreur, ce qui rendrait la divergence
  difficile à repérer côté UI.
- **Pas de rétro-application aux comptes existants.** Le plafond ne bloque que les *nouveaux*
  uploads. Un compte qui détenait déjà plus de `UNLOCKED_CV_SLOTS` CVs avant cette PR conserve tous
  ses CVs excédentaires côté serveur — leur embedding et leur extraction ROME ont déjà été payés
  une fois à l'upload (pas de coût récurrent de ce côté-là), mais ils continuent d'être matchés
  quotidiennement par l'agent de matching (`agents/matching/main.py`, qui itère sur "every CV with
  an embedding" sans notion de plafond) et de faire enqueuer leurs propres `match_analyses` top-N à
  chaque run (`agents/matching/main.py`, ~lignes 261-270) — c'est ce coût LLM récurrent-là que
  cette PR cherche à réduire, et il continue de s'accumuler pour les CVs excédentaires devenus
  invisibles. Seuls la grille de la bibliothèque et le badge "x / 2" cessent de les afficher
  au-delà des 2 premiers. Aucune étape de réconciliation/archivage n'existe pour ces CVs
  excédentaires ; l'économie de coût visée par cette PR ne s'applique donc qu'aux comptes créés (ou
  aux CVs uploadés) après son déploiement. Documenté ici pour ne pas être redécouvert comme un
  problème non documenté — pas de correctif dans cette PR.
  Le garde-fou d'upload reste cohérent malgré cette troncature d'affichage : `HomeClient.tsx`
  passe à `UploadSection` la longueur de la liste `cvs` complète, non tronquée
  (`onCvsChange?.(cvs)` dans `LibrarySection.tsx`), donc un compte legacy à 5 CVs est bien détecté
  comme au plafond et bloqué en upload, même si la grille n'en affiche que 2 et que le badge lit
  "2 / 2".
- **Pas de nouvel événement PostHog** pour ce changement — explicitement hors scope, différé à un
  travail séparé ultérieur.
- **Pas de migration Alembic** nécessaire — juste un `COUNT` sur la table `cvs` existante, même
  pattern non indexé par `user_id` que `list_cvs` déjà en place, pas une régression introduite par
  cette PR.

### Vérification

- Relecture de `upload_cv`, de la garde 403 et de sa docstring, des deux constantes
  (`MAX_CVS_PER_USER` / `UNLOCKED_CV_SLOTS`) et de leurs commentaires WHY de synchronisation
  manuelle, et de `LibrarySection.tsx`/`UploadSection.tsx` : cohérents avec le comportement décrit
  ci-dessus.
- Pas d'accès Bash/`git diff`/`gh` depuis ce rôle. Numéro de PR dérivé du dernier titre
  `## PR #256` de ce fichier ; aucune entrée `## PR #257` ni entrée existante pour cette branche
  dans `docs/JOURNAL.md` avant cette révision.
- Pas d'exécution de `pytest`/`jest` depuis ce rôle — vérification par relecture du code et des
  tests ajoutés (`test_rejects_upload_at_cap`, `UploadSection.test.tsx`, bloc `describe` ajouté à
  `LibrarySection.test.tsx`) uniquement, pas par exécution.

## PR #258 — feat(frontend): tracker current_cv_count comme propriété de personne PostHog

**Date :** 2026-07-27
**Branche :** `feature/cv-count-posthog-tracking` → `dev`

### Contexte

Suivi ponctuel du plafond de CVs introduit par la PR #257 : donner à une future analyse
PostHog la matière pour observer la répartition réelle 1 CV / 2 CVs par utilisateur. Prompt
Cowork (`docs/prompts/prompt-cv-count-posthog-tracking.md`, dépôt principal job-finder, pas ce
worktree). La construction de l'insight/dashboard PostHog lui-même est explicitement hors
scope de cette PR — différée à Claude Cowork une fois qu'il y aura de la donnée réelle à
visualiser, même découpage que le Trend "crédits dépensés par jour" d'une PR précédente.

### Ce qui a été fait

- **`JobFinder/frontend/app/_components/LibrarySection.tsx`** : import de `posthog` depuis
  `posthog-js` et nouveau `useEffect` qui appelle
  `posthog.setPersonProperties({ current_cv_count: cvs.length })` à chaque changement de
  `cvs.length`, gardé par `!isAuthenticated || loading` pour ne rien poster avant que le premier
  fetch ait résolu ni pour un visiteur anonyme. Commentaire WHY étendu au-dessus de l'effet pour
  couvrir explicitement les deux alternatives écartées (voir Décisions techniques) et le cas
  limite où le garde `loading` ne suffit pas à éviter un `current_cv_count: 0`.
- **`JobFinder/frontend/__tests__/LibrarySection.test.tsx`** : nouveau bloc
  `describe("current_cv_count person property", ...)` — poste après résolution du fetch initial,
  ne poste rien avant résolution, ne poste jamais pour un visiteur non authentifié, poste le
  nouveau total (plus bas) après une suppression locale de CV, et ne reposte pas quand deux polls
  consécutifs de 3s renvoient le même nombre de CVs.

### Décisions techniques

- **Propriété de personne, pas événement.** `current_cv_count` est une valeur vivante attachée à
  l'utilisateur, pas un log d'événements — une future insight PostHog "breakdown by person
  property" peut alors énumérer toutes les valeurs distinctes présentes (1, 2, ou 1/2/3 si le
  plafond est un jour relevé) sans aucun changement de code ni de graphe quand ce plafond bouge ;
  seule la logique de comptage (déjà correcte) compte. Ce zéro-changement-de-graphe vaut pour un
  breakdown côté table `persons` ; un breakdown côté table `events` (person-on-events) refléterait
  la valeur au moment de l'ingestion de chaque événement, pas la valeur courante — à garder en tête
  pour qui construira l'insight.
- **Deux alternatives considérées et écartées.** (1) Compter les événements `cv_uploaded` par
  utilisateur (déjà trackés dans `UploadSection.tsx`) casse dès qu'une suppression a lieu : un
  cycle upload → suppression → ré-upload se lirait comme 2 CVs pour quelqu'un qui n'en détient
  jamais qu'1. (2) Un événement ponctuel `cv_upload_blocked_at_cap` (envisagé puis abandonné dans
  le prompt précédent, `prompt-cv-slot-lock-portfolio.md`) ne se déclenche que pour les
  utilisateurs déjà au plafond en train d'en ajouter — il ne dit rien de la distribution réelle
  1 CV / 2 CVs sur l'ensemble des utilisateurs.
- **Dépendance à `cvs.length`, pas à `cvs`.** Le poll de 3s existant (tant qu'un CV est
  pending/processing/done) ne re-déclenche donc pas l'effet à chaque tick tant que le nombre de
  CVs ne change pas réellement.
- **Pas de dashboard/insight PostHog dans cette PR** — différé à Claude Cowork, comme documenté
  ci-dessus.

### Vérification

- Relecture du nouveau `useEffect`, de son commentaire WHY et des cinq tests ajoutés dans
  `LibrarySection.test.tsx` : cohérents avec le comportement décrit ci-dessus, y compris le cas où
  le garde `loading` seul ne suffit pas (fetch en échec après retry → `current_cv_count: 0` posté
  quand même, documenté dans le commentaire plutôt que corrigé — hors scope de cette PR).
- Pas d'accès Bash/`gh` depuis ce rôle. Numéro de PR dérivé du plus haut `## PR #NNN` de ce
  fichier (`## PR #257`, également la dernière entrée) + 1 ; aucune entrée `## PR #258` ni entrée
  existante pour cette branche dans `docs/JOURNAL.md` avant cette révision.
- Pas d'exécution de `jest` depuis ce rôle — vérification par relecture du code et des tests
  ajoutés uniquement, pas par exécution.

## PR #259 — fix(frontend): move the at-cap rejection feedback onto the icon itself

**Date :** 2026-07-27
**Branche :** `fix/upload-reject-icon-shake` → `dev`

### Contexte

Retour direct de Vincent sur le comportement de blocage au plafond de la PR #257. Le premier
rendu de ce blocage — anneau rouge (`ring-2 ring-destructive`) et animation `shakeReject` en
CSS sur le `<div>` invisible plein écran de `UploadSection.tsx` — se lisait comme "des barres en
dehors" de l'écran. Demande : que l'icône document/fichier au centre de l'écran reçoive un
contour rouge, que son "+" devienne rouge aussi, et que le shake s'applique à l'icône elle-même,
pas au conteneur.

L'icône document est dessinée sur un canvas HTML5 par
`JobFinder/frontend/app/_components/OrbitAnimation.tsx` (fonction `drawDocument`), pas comme des
éléments DOM — la correction ne pouvait donc pas passer par une classe CSS et a nécessité une
approche différente.

### Ce qui a été fait

- **`OrbitAnimation.tsx`** : deux nouvelles props optionnelles sur `Props`, `rejected?: boolean`
  (reflète l'état `capRejected` de `UploadSection` — tant que vrai, le contour et le "+" de
  l'icône se dessinent en rouge, uniquement en état `idle` : l'icône n'est pas dessinée en
  "uploaded" et se dessine toujours non teintée en "done") et `rejectTick?: number` (incrémenté à
  chaque tentative rejetée, relance une salve de shake de la même façon que `clickFlashRef` relance
  déjà l'effet de ripple au clic ailleurs dans ce fichier). Deux nouveaux refs (`rejectedRef`,
  `rejectShakeStartRef`) répercutent ces props dans la boucle d'animation sans relancer tout
  l'effet du canvas (même pattern que `stateRef` existant). Ajout d'un helper
  `shakeOffset(elapsedMs)` — une oscillation sinusoïdale continue et amortie sur
  `SHAKE_DURATION_MS = 400` — en remplacement compatible-canvas des anciens keyframes CSS
  `shakeReject` (le canvas n'a pas de pourcentages de keyframes discrets à réutiliser).
  `drawDocument` prend désormais des paramètres `rejectRgb`/`isRejected` : quand rejeté, elle
  re-trace en rouge le contour du corps du document en réutilisant le path déjà tracé (`fill()` ne
  vide pas le path courant, donc le contour suit exactement le même tracé), et le strokeStyle de la
  croix "+" passe au rouge plein au lieu de la couleur translucide habituelle. L'appel à
  `drawDocument` en état `idle` s'enveloppe dans un `ctx.translate(dx, 0)` où `dx` vient de
  `shakeOffset`.
- **Nouveau token de thème `--canvas-reject`** : ajouté à `lib/theme/types.ts`,
  `lib/theme/themes/dark.ts` (`"248, 113, 113"`, aligné sur le rouge dark de
  `--ring-destructive`), `lib/theme/themes/light.ts` (`"220, 38, 38"`, aligné sur le rouge light
  de `--ring-destructive`), et le `:root` par défaut de `app/globals.css`. Suit l'exception
  documentée par le skill `conventions-frontend` pour `OrbitAnimation.tsx` : le canvas a besoin de
  triplets RGB bruts en custom properties CSS lus via `getComputedStyle`, pas de classes Tailwind,
  qu'il ne peut pas consommer directement.
- **`UploadSection.tsx`** : retrait de la classe conditionnelle
  `ring-2 ring-destructive animate-[shakeReject_0.4s_ease-in-out]` et du `key={rejectTick}` (les
  deux devenus inutiles) sur le `<div>` de la zone de dépôt ; passe désormais
  `rejected={capRejected}` et `rejectTick={rejectTick}` à `<OrbitAnimation>`. Le message texte
  rouge de rejet sous l'icône est inchangé — le retour de Vincent portait spécifiquement sur
  l'anneau/shake du conteneur, pas sur le texte.
- **`app/globals.css`** : retrait du bloc `@keyframes shakeReject`, devenu orphelin.
- **Commentaires WHY ajoutés lors de cette revue de documentation** : la docstring de la prop
  `rejected` précisait initialement "tinte le contour et le + en rouge" sans mentionner que ce
  tintage est volontairement limité à l'état `idle` — complétée pour couvrir explicitement les
  états "uploaded" (icône non dessinée) et "done" (`isRejected` figé à `false` sur l'appel
  `drawDocument` correspondant, désormais commenté ; `rejected` peut pourtant y être vrai aussi,
  cf. décision ci-dessous — le tintage y est supprimé par choix, pas parce que les deux états ne
  peuvent pas coexister). Commentaire ajouté sur le garde `if (rejectTick > 0)` : n'est pas une
  redondance mais évite un shake parasite au montage, puisque `rejectTick` démarre à 0.

### Décisions techniques

- **Shake en oscillation continue plutôt qu'en keyframes** : le canvas ne peut pas rejouer des
  pourcentages de keyframes CSS, donc `shakeOffset` reconstruit l'équivalent avec une sinusoïde
  amortie sur une durée fixe (`SHAKE_DURATION_MS`), pilotée par un timestamp de départ
  (`rejectShakeStartRef`) plutôt que par une classe/key React qui redéclenche un remount.
- **Réutilisation du path existant pour le contour** plutôt qu'un rectangle de contour séparé :
  `fill()` ne vide pas le path courant sur un canvas 2D, donc un simple `stroke()` juste après
  trace exactement le même contour arrondi que le corps du document, sans dupliquer la géométrie
  du path.
- **Signalé, non corrigé (hors scope de cette PR) :** `handleFile` appelle `rejectAdd()` avant
  toute vérification de `animState` (contrairement à `handleClick`/`openPicker`), donc un drop
  pendant un `animState !== "idle"` positionne `capRejected`/`rejectTick` sans aucun retour
  visible : l'icône n'est pas dessinée hors `idle`, et le message texte est lui aussi gardé par
  `idle`. Atteignable si `cvCount` atteint le plafond de façon optimiste en cours d'animation.

### Vérification

- Relecture de `OrbitAnimation.tsx` (props `Props`, `shakeOffset`, `drawDocument`), de
  `UploadSection.tsx` et de `app/globals.css` : commentaires WHY cohérents avec le comportement
  réel après correction de la docstring de `rejected` (voir ci-dessus, corrigée par ce rôle).
- `grep` sur `shakeReject` et `ring-2 ring-destructive` dans `JobFinder/frontend/` : aucune
  occurrence restante hors du commentaire WHY qui les mentionne comme contexte historique — pas
  de résidu de debug, pas de classe orpheline.
- Numéro de PR confirmé par le prompt parent via `gh pr list` (dernière entrée de ce fichier :
  `## PR #258`, donc #259 cohérent) ; aucune entrée existante pour la branche
  `fix/upload-reject-icon-shake` dans `docs/JOURNAL.md` avant cette révision.
- Pas d'accès Bash/`gh`/`git diff` propre depuis ce rôle — pas d'exécution de `jest` : la suite de
  tests jsdom existante (`UploadSection.test.tsx`, `LibrarySection.test.tsx`) n'exerce de toute
  façon pas le dessin canvas, cohérent avec la vérification manuelle en dev server décrite par le
  prompt parent.

## PR #261 — fix(frontend): show MSAL active account instead of accounts[0]

**Date :** 2026-07-28
**Branche :** `feature/fix-auth-account-display-mismatch` → `dev`

### Contexte

Effet secondaire non corrigé du bug Entra External ID déjà documenté par la PR #248
(AADSTS165000, double sélecteur de compte) : `sessionStorage` peut se retrouver avec deux comptes
dans le cache MSAL, et l'ordre du tableau retourné par `accounts` n'est pas garanti. Trois
composants lisaient `accounts[0]` pour afficher le nom/les initiales de l'utilisateur connecté —
avec deux comptes en cache, le mauvais nom pouvait s'afficher. `lib/api/client.ts` résolvait déjà
correctement le compte pour le Bearer token via `instance.getActiveAccount() ?? getAllAccounts()[0]`
— déjà en place avant cette PR, origine non retrouvée dans ce fichier (ni #248 ni #224 ne
l'introduisent d'après leurs propres entrées) : le bug était donc purement un défaut d'affichage, jamais un défaut
d'autorisation — les données backend affichées correspondaient toujours au bon utilisateur, seul
le nom/les initiales affichés en en-tête pouvaient être ceux de l'autre compte en cache.

### Ce qui a été fait

- **`JobFinder/frontend/app/_components/AuthButton.tsx`**, **`JobFinder/frontend/app/profile/page.tsx`**,
  **`JobFinder/frontend/components/LoginButton.tsx`** : les trois lectures de `accounts[0]` (nom
  affiché dans le menu de compte, initiales, en-tête de `/profile`, texte "Connecté en tant que")
  remplacées par `instance.getActiveAccount() ?? accounts[0]`, alignées sur le pattern déjà en
  place dans `lib/api/client.ts`.
- **Commentaires WHY ajoutés** sur les trois sites : précisent que le choix de l'active account
  plutôt que `accounts[0]` n'est pas cosmétique — sans ce commentaire, une relecture future pourrait
  juger `accounts[0]` équivalent et plus simple, et réintroduire le bug.
- **`JobFinder/frontend/__tests__/ProfilePage.test.tsx`** : le mock `useMsal` expose désormais
  `instance.getActiveAccount()` (le mock par défaut du module, utilisé par le `describe` existant
  sur l'autosave `notification_days`, ainsi que le mock dédié du nouveau `describe`). Nouveau test
  dans un `describe` dédié : avec deux comptes en cache (`accounts: [First User, Second User]`) et `getActiveAccount()`
  retournant `Second User`, la page affiche bien "Second User" en en-tête, jamais "First User".
  Commentaire ajouté sur le mock partagé pour signaler que `getActiveAccount` est désormais requis
  par le composant testé, pas juste un ajout arbitraire au mock.

### Décisions techniques

- **Fix display-only, pas de changement d'autorisation** : `lib/api/client.ts` n'a pas été touché,
  il résolvait déjà correctement le compte actif pour le token. Voir Contexte ci-dessus.

### Vérification

- Relecture des trois composants modifiés et de leurs docstrings/commentaires existants : aucune
  docstring de module ne décrivait la logique de résolution du compte affiché, donc rien d'obsolète
  à corriger au-delà des commentaires WHY ajoutés ci-dessus.
- **Écart signalé, non corrigé (hors scope de ce rôle) :** `AuthButton.tsx` et `LoginButton.tsx`
  reçoivent le même correctif mais n'ont aucune couverture de test (aucun fichier
  `AuthButton.test.tsx` / `LoginButton.test.tsx` n'existe) — seul `ProfilePage.test.tsx` couvre le
  scénario à deux comptes. `LoginButton.tsx` n'est par ailleurs importé nulle part dans le code
  applicatif actuel (grep sur `LoginButton` dans `JobFinder/frontend/`) — sa docstring affirmait
  encore "This is the only interactive element of the walking skeleton", devenu faux depuis
  l'existence d'`AuthButton.tsx` ; une note a été ajoutée à la docstring précisant que le composant
  n'est plus câblé dans l'app plutôt que de réécrire la phrase historique, le composant semblant
  être du code mort plutôt qu'un défaut d'affichage actif ; à confirmer avec Vincent avant
  suppression éventuelle.
- Grep sur `useMsal` dans `JobFinder/frontend/__tests__/` pour tout mock qui appellerait
  `getActiveAccount` sans l'exposer sur `instance` (aurait cassé les composants modifiés) :
  `UploadSection.test.tsx` mocke `useMsal` sans `getActiveAccount`, mais
  `UploadSection.tsx` ne déstructure pas `accounts` — non affecté. Aucun autre mock trouvé.
- Pas d'accès Bash/`npm test`/`tsc`/`gh`/`git diff` depuis ce rôle — vérification par relecture des
  trois fichiers modifiés, du test ajouté, et du grep ci-dessus, pas par exécution de la suite de
  tests.
- Numéro de PR confirmé via `gh pr list --state all --limit 5 --json number,title,headRefName` :
  #261 (le titre initialement dérivé du dernier titre `## PR #259` +1 avait donné #260, déjà pris
  par `feature/legal-pages` ouverte en parallèle sur un autre worktree — corrigé après vérification
  GitHub).

## PR #262 — chore(frontend): remove unused LoginButton component

**Date :** 2026-07-28
**Branche :** `chore/remove-dead-loginbutton` → `dev`

### Contexte

`components/LoginButton.tsx` n'était importé nulle part dans l'application — confirmé par grep sur
tout `JobFinder/frontend` : aucune référence dans le code source, les tests, ou un éventuel barrel
export. `AuthButton.tsx` (`app/_components/AuthButton.tsx`) est le vrai contrôle de connexion en
production depuis la phase walking-skeleton (PR #96) : bouton « Se connecter » côté non
authentifié, pill prénom + initiales avec dropdown profil/déconnexion côté authentifié.
`LoginButton.tsx` était un résidu antérieur, jamais retiré. Sa suppression a été signalée à Vincent
pour confirmation avant d'être appliquée dans la PR #261 (`instance.getActiveAccount() ?? accounts[0]`
sur `AuthButton`/`LoginButton`/`ProfilePage`) ; il a confirmé, et la suppression est réalisée dans
cette PR.

### Ce qui a été fait

- Suppression de `JobFinder/frontend/components/LoginButton.tsx` — aucun autre fichier modifié.

### Vérification

- Grep sur `LoginButton` dans tout le repo : plus aucune référence de code (imports, barrel
  exports, tests, Storybook) hors deux mentions de prose sans impact — `docs/JOURNAL.md` (entrées
  passées relatant l'historique du fichier, contexte figé, non modifiées par cette revue) et
  `.claude/skills/conventions-frontend/SKILL.md` (utilisé comme exemple de nom de fichier pour la
  convention `PascalCase.tsx`, pas une dépendance réelle au composant) — aucune des deux ne
  nécessite de changement pour que cette suppression soit sûre.
- Numéro de PR confirmé via `gh pr list --state all --limit 5 --json number,title,headRefName` :
  #261 est la PR de correctif d'affichage MSAL (`feature/fix-auth-account-display-mismatch`, celle
  qui a signalé ce code mort), #260 est `feature/legal-pages` (worktree `agent1`, sans rapport avec
  `LoginButton`) — cette PR prend donc le numéro #262.

## PR #263 — feat(infra): Azure OpenAI en DataZoneStandard (résidence UE)

**Date :** 2026-07-28
**Branche :** `feature/openai-datazone-eu` → `dev`

### Contexte

Les 3 déploiements Azure OpenAI (`gpt-4o-mini`, `gpt-5-mini`, `text-embedding-3-small`) tournaient
en SKU `GlobalStandard` → l'inférence pouvait être routée hors UE, ce qui contredisait
l'engagement RGPD (données CV/utilisateur en UE, ADR-006) et rendrait inexacte la page
confidentialité de la PR #260 (« aucun transfert hors UE »). Vérifié en lecture seule via
`az cognitiveservices model list --location francecentral` : le SKU régional `Standard` (France
seule) n'est disponible pour **aucun** des 3 modèles à francecentral — d'où le choix initial de
`GlobalStandard`. En revanche `DataZoneStandard` (traitement garanti dans la zone de données UE)
l'est pour les 3.

### Ce qui a été fait

- **`envs/dev/openai.tf`** : les 3 déploiements passent de `GlobalStandard` à `DataZoneStandard`.
  Commentaires WHY mis à jour (résidence UE, historique du choix Global).
- **`envs/dev/variables.tf`** : nouvelle variable `openai_capacity_tpm_gpt5_mini` (défaut 500 =
  0,5M TPM). Raison : le quota `DataZoneStandard` de `gpt-5-mini` à francecentral n'est que de 670
  (en milliers), sous le défaut partagé de 1000 (1M TPM) — un apply à 1000 échouerait. Vérifié via
  `az cognitiveservices usage list`. `gpt-4o-mini` (quota 3000) et `text-embedding-3-small` (quota
  2000) gardent la variable partagée à 1000.
- **`modules/openai/variables.tf`** : la validation du `sku_name` des déploiements, qui
  n'autorisait que `Standard`/`GlobalStandard`, accepte désormais aussi `DataZoneStandard`.
  Changement de module minimal, indissociable du changement d'env (pure infra, aucun impact app).

### Décisions techniques

- **DataZone UE plutôt que France stricte** : le mode régional France n'existe pas pour ces
  modèles ; DataZone garantit l'UE (RGPD identique), sans changer de modèle ni de code, à prix
  quasi égal — voire moindre pour l'embedding (DataZone 0,000020 € vs Global 0,000022 €, chiffres
  Vincent).
- **Baisse de capacité `gpt-5-mini` (1M → 0,5M TPM)** assumée : usage réel proche de 0, 0,5M TPM
  reste très au-dessus du besoin ; monter au-delà de ~670 nécessiterait une demande d'augmentation
  de quota Azure.
- **Recréation des déploiements attendue** : changer le SKU d'un `azurerm_cognitive_deployment`
  force un remplacement (destroy+create, même nom). Sans conséquence — ressources sans état, aucun
  `prevent_destroy` sur les déploiements (seul le compte `azurerm_cognitive_account` est protégé).
  Brève indispo par déploiement pendant l'apply, acceptable en dev.
- **Module + env dans la même PR** : la règle « changement de module en PR dédiée » vise les
  features applicatives ; ici tout est infra et l'extension d'une valeur d'allow-list n'a aucun
  sens séparée du changement d'env qui la motive.
- **Swap de modèle `gpt-4o-mini` → `gpt-5-nano` (Agent 3) volontairement hors périmètre** : il
  touche aussi le code Python et demande de re-tester prompts/parsing → PR séparée ultérieure. Ici
  on ne fait que la bascule de résidence, à modèles constants, pour un merge sûr.

### Vérification

- `terraform fmt -check` et `terraform validate` : OK sur les fichiers touchés (le seul diff `fmt`
  résiduel du dépôt est dans `modules/container_app_environment`, préexistant et hors périmètre).
- Quotas `DataZoneStandard` francecentral confirmés en lecture seule (`az cognitiveservices usage
  list`) : `gpt-4o-mini` 3000, `text-embedding-3-small` 2000, `gpt-5-mini` 670 — les capacités
  configurées (1000/1000/500) tiennent toutes.
- `terraform plan` réel (backend distant + quota à l'apply) délégué à la CI et à `reviewer-infra`.
- Suite frontend inchangée par cette PR (infra seule).

## PR #260 — feat(frontend): pages mentions légales & confidentialité + liens légaux globaux

**Date :** 2026-07-28
**Branche :** `feature/legal-pages` → `dev`

### Contexte

Avant l'ouverture de Job Finder au cercle proche de Vincent puis à un public plus large, l'app
doit publier ses mentions légales et sa politique de confidentialité RGPD — obligatoires dès que
des données personnelles réelles (CV, profil) sont collectées, même pour un portfolio non
commercial. Décisions cadrées avec Claude Cowork (cf.
`docs/prompts/prompt-mentions-legales-confidentialite.md`) : éditeur = Vincent Boutin, particulier
sans structure (pas de SIRET, "vbo-cloud" est un nom de projet, pas une entité) ; contact via
l'alias `legal@vincentboutin.dev` (pas l'adresse pro/perso) ; hébergeur = Microsoft France (SIREN
327 733 184, vérifié sur facture Azure réelle) ; pas de CGU ni de gate de consentement dans ce
lot ; textes à portée légale à reprendre **verbatim**, sans reformulation.

### Ce qui a été fait

- **`app/_components/LegalDocument.tsx`** (nouveau, Server Component) : coquille de lecture statique
  partagée par les deux pages légales, réutilisant la surface visuelle profile/feedback
  (`bg-profile-page`, barre de retour desktop, `<main>` centré `max-w-2xl`). Rend un modèle de
  blocs typés `LegalBlock` (`h2` / `p` / `ul` / `lines`). Les textes vivent dans des **chaînes JS**
  (pas des nœuds texte JSX) pour préserver le contenu au caractère près sans que
  `react/no-unescaped-entities` n'échappe apostrophes/guillemets.
- **`app/mentions-legales/page.tsx`** et **`app/confidentialite/page.tsx`** (nouveaux, Server
  Components) : contenu verbatim + `metadata.title`. Aucune garde `isAuthenticated` (contrairement
  à profile/feedback) : les mentions légales doivent rester atteignables **déconnecté**. La page
  confidentialité ne liste **pas** de destinataire « OpenAI » distinct — la ligne « Microsoft
  Azure » couvre déjà le service Azure OpenAI (Microsoft, jamais OpenAI Inc.) ; un commentaire WHY
  le documente dans le fichier. La section « Transferts hors UE » a été alignée sur la migration
  `DataZoneStandard` (PR #263, appliquée) après vérification sur la doc Microsoft (EU Data
  Boundary) : stockage au repos en France Centre, mais traitement IA dans la **zone de données UE**
  de Microsoft (UE + EEE + Suisse, pays adéquat) et rétention anti-abus Microsoft jusqu'à 30 j dans
  cette zone. L'affirmation absolue initiale « aucun transfert hors UE » — inexacte, l'AELE incluant
  Norvège/Suisse hors UE — a donc été remplacée par une formulation exacte. Dans les mentions
  légales, la section « Hébergement » précise « France Centre pour l'hébergement de l'application et
  le stockage des données » (au lieu de l'ancien « pour le calcul et les données », ambigu depuis
  #263 : le calcul IA relève de la zone UE, cf. confidentialité).
- **`app/_components/LegalLinks.tsx`** (nouveau, Server Component) : deux liens discrets
  (`Mentions légales · Confidentialité`) épinglés en bas à gauche en `fixed`, `z-30` (sous le
  header `z-50`, le rail `z-40` et les modales `z-50`, donc jamais par-dessus un dialogue). Le
  choix du `fixed` plutôt qu'un footer en flux vient de la home : c'est un conteneur plein écran
  en snap-scroll (`h-dvh overflow-hidden`) où un `<footer>` après `{children}` serait invisible.
- **`app/layout.tsx`** : rend `<LegalLinks />` globalement, après `{children}`, à l'intérieur des
  providers — présent sur toutes les routes.
- **`app/profile/page.tsx`** : notice RGPD courte (simple `<p>` + lien « En savoir plus » vers
  `/confidentialite`) insérée juste au-dessus de `DeleteAccountSection` dans la zone de suppression
  (son texte dit « ci-dessous »). Texte court validé par Vincent : « analysé par une IA et stocké
  sur l'infrastructure du projet. Rien ne sort de l'UE / AELE… » (« UE / AELE » = l'EU Data Boundary
  de Microsoft, cohérent avec la page confidentialité). `<p>` en `w-full` pour aligner sa largeur sur
  les cartes de section au-dessus. Aucun gate de consentement, aucune modale ; `DeleteAccountSection`
  n'est pas modifié.

### Vérification

- `npx tsc --noEmit` et `npx eslint` sur tous les fichiers nouveaux/modifiés : propres.
- `npx jest` : suite complète **209/209** (25 suites). Nouveaux tests :
  `__tests__/LegalPages.test.tsx` (les deux routes rendent titres + contenu attendu ; assertion
  qu'aucun destinataire « OpenAI » distinct n'apparaît), `__tests__/LegalLinks.test.tsx` (les deux
  liens pointent vers `/mentions-legales` et `/confidentialite`), et un bloc ajouté à
  `__tests__/ProfilePage.test.tsx` (la notice + le lien « En savoir plus » s'affichent, le bouton
  « Supprimer mon compte » reste intact).
- **En attente de relecture visuelle par Vincent (dev server) :** les liens `fixed` étant globaux,
  ils s'affichent aussi par-dessus la home animée (section d'upload de CV, volontairement gardée
  sans texte jusqu'ici) et en coin bas-gauche de la section offres (`CVDetailSection`). Aucun
  ajustement de `CVDetailSection` n'a été fait : l'analyse de la géométrie montre que le
  chevauchement n'existe qu'en desktop large et reste marginal (le contenu de la section démarre à
  `md:ml-24`, hors de la gouttière où se placent les liens). À confirmer/arbitrer visuellement
  plutôt que de rétrécir la vignette CV à l'aveugle.

## PR #264 — feat(frontend): bannière de consentement cookies (PostHog)

**Date :** 2026-07-28
**Branche :** `feature/cookie-consent` → `dev`

### Contexte

PostHog était initialisé au chargement en mode par défaut (cookies + capture immédiate), **sans
consentement** → non conforme ePrivacy/CNIL : les cookies de mesure d'audience exigent un opt-in
préalable, hors exemption que PostHog par défaut ne remplit pas. Les cookies d'auth (MSAL) sont,
eux, strictement nécessaires (exemptés). Décision (avec Vincent) : bannière opt-in **pleine
largeur** (proéminente, pour forcer un choix rapide), choix mémorisé et révocable.

### Ce qui a été fait

- **`lib/consent/ConsentContext.tsx`** (nouveau) : contexte client du choix
  (`accepted`/`declined`/`null`), persisté en `localStorage` (`jf-cookie-consent`). Stocker le
  choix lui-même est exempté (nécessaire pour l'honorer). Flag `hydrated` pour éviter le flash de
  la bannière avant lecture du choix stocké.
- **`app/Providers.tsx`** : `posthog.init()` **uniquement** si `consent === "accepted"` → aucun
  cookie ni capture avant opt-in. Les `posthog.capture(...)` disséminés dans l'app sont des no-op
  tant qu'`init()` n'a pas tourné, donc aucune garde ajoutée sur chaque appel. Branche explicite
  sur les 3 états.
- **`app/_components/CookieConsent.tsx`** (nouveau) : barre pleine largeur en bas (`z-40`, au-dessus
  des liens légaux `z-30`). « Refuser » et « Accepter » équivalents (CNIL, pas de dark pattern),
  lien « En savoir plus » → `/confidentialite`. `<section aria-label>` (bandeau non modal), affiché
  seulement si aucun choix fait.
- **`app/_components/ManageCookiesButton.tsx`** (nouveau) + **`LegalLinks.tsx`** : lien « Gérer les
  cookies » à côté des liens légaux → rouvre la bannière (retrait aussi simple que le consentement,
  exigence CNIL).
- **`app/layout.tsx`** : `<ConsentProvider>` au-dessus de `<PostHogProvider>` ; rend
  `<CookieConsent />`.
- **`app/confidentialite/page.tsx`** : nouvelle section « Cookies » (nécessaires vs mesure
  d'audience, retrait via « Gérer les cookies »).
- **`docs/BACKLOG.md`** (maintenance, hors périmètre de la feature, à la demande de Vincent) :
  archivage des Milestones 4 & 5 (frontend + monitoring/tests, faits) et de l'item smoke-test
  webapp (fait — vérifié dans `buildAgents.yml` + lockfile) ; ajout d'une section « durcissement des
  endpoints publics » suite à l'audit upload du 2026-07-28 (rate limiting, garde de parsing PDF,
  borne `raw_text` avant embedding).

### Décisions techniques

- **Init gaté plutôt qu'init + opt-out par défaut** : ne pas appeler `init()` du tout garantit zéro
  cookie PostHog avant le oui (un `init` en opt-out poserait quand même un cookie d'état).
- **Bug corrigé avant merge (signalé en revue)** : ré-accepter après un refus laissait l'analytics
  éteint — l'effet sortait tôt sur `initialized.current` sans rappeler `opt_in_capturing()` (seul à
  réactiver la capture après `opt_out_capturing()`). Corrigé : sur `accepted`, init si pas encore
  initialisé, sinon `opt_in_capturing()`. Un test de transition (accept→decline→re-accept) couvre
  désormais ce chemin, qu'un test à consentement statique ne pouvait pas atteindre.
- **Fenêtre de re-décision (`null`)** : après « Gérer les cookies », PostHog garde son état courant
  jusqu'au nouveau choix — branche volontairement no-op.
- **Texte bannière** validé avec Vincent, sans « anonyme » : PostHog garde un identifiant, ce serait
  inexact **et** auto-contradictoire avec « données personnelles » (une donnée anonyme n'exigerait
  d'ailleurs pas de consentement).

### Vérification

- `tsc` + `eslint` propres. `jest` : **221/221** (27 suites). Nouveaux/mis à jour :
  `ConsentContext.test.tsx` (persistance / relecture au montage / retrait), `CookieConsent.test.tsx`
  (affichage conditionnel + boutons), `Providers.test.tsx` réécrit (init gaté + transition
  accept→decline→re-accept), `LegalLinks.test.tsx` (+ bouton « Gérer les cookies »), assertion
  section « Cookies » dans `LegalPages.test.tsx`.

## PR #265 — fix(offer-fetching): récupérer les offres au-delà du plafond de pagination France Travail

**Date :** 2026-07-28
**Branche :** `fix/offer-fetching-pagination-ceiling` → `dev`

### Contexte

`_fetch_and_upsert_new_offers` plantait en prod sur le code ROME **M1507** (fort volume) : l'API
France Travail renvoie un **400** dès que la pagination dépasse `range=3050`, alors que toutes les
pages précédentes réussissent. Ce n'est **pas du rate-limiting** (jamais de 429, même `range` exact
sur 3 exécutions réelles) mais un **plafond structurel de profondeur de pagination** (comparable au
`max_result_window` d'Elasticsearch). `raise_for_status()` transformait ce 400 en exception non
catchée qui remontait jusqu'à faire abandonner tout le message Service Bus. Sans isolation par code,
ce message aurait fini en dead-letter (à 10 tentatives) → perte silencieuse du refresh du jour pour
**tous** les codes ROME actifs, pas seulement M1507.

### Ce qui a été fait

- **Tâche 1 — `ft_client.fetch_offers`** : un 400 sur une page au-delà de la première (`start > 0`)
  est traité comme le plafond de pagination — warning `ft_pagination_ceiling_reached` et retour des
  offres déjà collectées au lieu de laisser l'exception remonter. Un 400 sur la 1re page
  (`start == 0`) reste une requête réellement invalide → re-raise inchangé.
- **Tâche 2 — `ft_client.fetch_all_offers`** (nouveau, appelé par `main.py` à la place de
  `fetch_offers`) : recherche par **fenêtre glissante sur la date de création** pour récupérer tout
  le volume malgré le plafond. Sonde légère (`_probe_total`, `range=0-0` lit `Content-Range`) avant
  chaque fetch ; largeur de fenêtre adaptée à la densité réelle (30 j au départ, divisée par 2 tant
  que la tranche dépasse le seuil, plancher 1 j) ; fusion dédupliquée par `ft_id`.
- **Tâche 3 — `main._fetch_and_upsert_new_offers`** : chaque code ROME isolé dans un
  `try/except (requests.RequestException, SQLAlchemyError)` — une panne sur un code (réseau, timeout,
  code invalide → 400 dès la 1re page, erreur DB) logge `offer_fetch_rome_code_failed` et continue au
  lieu d'abandonner le message. `get_access_token` reste hors boucle (un mauvais token fait
  légitimement échouer tout le run). `total_new` ne compte que les codes traités avec succès.

### Décisions techniques

- **Tâche 0 abandonnée — pas de `maxDateActualisation`** : la borne haute symétrique supposée au
  départ n'existe pas. Deux sources de code réel indépendantes (wrapper
  `etiennekintzler/api-offres-emploi` + un space Hugging Face public) confirment que la vraie paire
  min/max de l'API est `minCreationDate`/`maxCreationDate` (date de **création**). On ne remplace
  **pas** `minDateActualisation` par ces params : `dateActualisation` (dernière mise à jour) ≠
  `dateCreation` — une offre créée il y a 8 mois mais republiée hier serait perdue en filtrant sur la
  création. `minDateActualisation` reste donc le filtre **métier** fixe (calculé via
  `OFFER_MAX_AGE_DAYS`) ; `minCreationDate`/`maxCreationDate` ne servent que d'**outil mécanique** de
  découpage, combinés en ET avec lui.
- **Fenêtre glissante plutôt que bisection récursive** (révision de l'algo initial) : plus simple à
  tester, pas de fusion d'arbre, s'adapte naturellement à la densité (grandes fenêtres si peu
  d'offres, petites si beaucoup).
- **`PAGINATION_SAFE_THRESHOLD = 2500`** : marge de sécurité **sous** le plafond observé
  empiriquement (~3050 sur un cas réel) — pas une valeur documentée par France Travail, à ajuster si
  le comportement réel diverge. Le 400 réactif de la Tâche 1 reste le filet de dernier recours si
  même une fenêtre de 1 jour dépasse le seuil (warning `ft_window_leaf_over_threshold`).
- **Pas de `_mark_rome_codes_pending` sur échec d'un code** : ce mécanisme est drainé et rejoué dans
  la même exécution (`_handle_fetch_request`) → boucle infinie sur un échec déterministe. Le code
  reste actif et sera retenté au prochain refresh planifié (18 h).

### Vérification

- `pytest tests/test_ft_client.py tests/test_offer_fetching.py` : **52/52**. Nouveaux tests : plafond
  400 (1re page vs page suivante), garde 204 No Content dans `fetch_offers` (corps vide → retour `[]`
  sans planter), `_probe_total` (lecture `Content-Range` / 0 si absent), `fetch_all_offers` (sonde
  sous seuil → 1 seul fetch ; rétrécissement + fusion/dédup ; plancher 1 j toujours > seuil → partiel
  accepté + warning ; saut d'une fenêtre de création vide `total_window == 0` → pas de fetch, on
  continue le parcours ; sonde à 0 → arrêt), isolation par code ROME (erreur fetch/DB isolée, échec
  `get_access_token` propagé).
- Aucun test existant régressé (429, `min_date`, pagination multi-pages).
- Vérification en conditions réelles (comparer le nombre d'offres M1507 récupérées au total annoncé
  par l'API) reportée après déploiement : pas de credentials FT en local (`.env` absent), tous les
  tests mockent `requests.Session`.
