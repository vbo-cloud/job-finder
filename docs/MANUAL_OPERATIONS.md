# Opérations manuelles — job-finder

Ce fichier documente toutes les opérations effectuées hors de Terraform.
Ces actions ne sont pas reproductibles automatiquement et doivent être refaites manuellement en cas de reconstruction de l'environnement.

---

## Azure — Fondations (hors Terraform)

- Tenant Azure créé manuellement
- Management Groups créés : un groupe projet, un sous-groupe et une subscription par environnement (dev, prod)
- Storage account Terraform state (`stjftfstatefrc`) créé manuellement avec resource locks
- Containers blob créés manuellement : `lz-tfstates` (sp-jf-platform) et `app-tfstates` (sp-jf-github)

---

## GitHub — Configuration

- Organisation et dépôt privés créés
- Secrets : `CLAUDE_API_KEY`, `REVIEWER_GITHUB_TOKEN`
- Variables : `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_PLATFORM_CLIENT_ID`, `SP_GITHUB_OBJECT_ID`
- Environnements `dev` et `prod` créés (reviewer obligatoire sur prod)
- Ruleset sur `main` et `dev` : required check `gate`, no force push, no deletion

---

## IAM — sp-jf-platform (SP gouvernance landing zones)

Créé via le script PowerShell idempotent `JobFinder/powershell/setup-sp-jf-platform.ps1`.

**Rôles assignés :**
- `RBAC Administrator` au niveau subscription (conditionné — exclut Owner, User Access Administrator, RBAC Administrator lui-même)
- `Resource Policy Contributor` au niveau subscription
- `Contributor` au niveau subscription — création et modification des ressources lz_dev
- `Storage Blob Data Contributor` sur le container `lz-tfstates` uniquement

**Federated credentials OIDC :**
- `github-pr` → `repo:vbo-cloud/job-finder:pull_request` (plan sur PRs)
- `github-dev` → `repo:vbo-cloud/job-finder:environment:dev` (apply sur dev)

**Variable GitHub ajoutée :** `AZURE_PLATFORM_CLIENT_ID`

---

## IAM — sp-jf-github (SP CI/CD couche applicative)

Créé via le script PowerShell idempotent `JobFinder/powershell/setup-sp-jf-github.ps1`.

Le script crée uniquement l'App Registration, le Service Principal et les federated credentials OIDC.
**Les role assignments sont entièrement gérés par sp-jf-platform via `lz_dev/rbac.tf`** — aucune assignation manuelle requise après le premier apply lz_dev.

**Federated credentials OIDC :**
- `github-pr` → `repo:vbo-cloud/job-finder:pull_request`
- `github-dev` → `repo:vbo-cloud/job-finder:environment:dev`

**Variable GitHub ajoutée :** `SP_GITHUB_OBJECT_ID` (Object ID du SP, requis par `lz_dev/rbac.tf` via `TF_VAR_sp_github_object_id`)

---

## RBAC — Key Vault (obsolète depuis PR #18)

> ⚠️ Cette section décrit l'ancienne procédure manuelle. Elle est remplacée par la policy `auto_lock` et la gestion des rôles via `lz_dev/rbac.tf`.
>
> Les rôles Key Vault Secrets Officer sont désormais assignés automatiquement par la CI/CD (sp-jf-platform via rbac.tf). Aucune intervention manuelle requise.

---

## Policy Azure — Ajout manuel de "global"

La policy `allowed-locations` de `lz_prod` ne contenait pas `"global"` au moment où les Private DNS Zones ont été créées. La policy a été mise à jour manuellement dans Azure pour débloquer l'apply, puis le code Terraform a été mis à jour en conséquence.

---

## France Travail API — Credentials

Les secrets `ft-client-id` et `ft-client-secret` ne sont pas provisionnés par Terraform.
Ils doivent être créés manuellement après inscription à l'API.

1. S'inscrire sur https://francetravail.io/data/api/offres-emploi et créer une application
   pour obtenir un `client_id` et un `client_secret`
2. Stocker les deux valeurs dans le Key Vault dev :
   ```bash
   az keyvault secret set --vault-name kv-jf-dev-frc \
     --name ft-client-id --value "<valeur>"
   az keyvault secret set --vault-name kv-jf-dev-frc \
     --name ft-client-secret --value "<valeur>"
   ```

Ces secrets sont lus par le workflow `offerFetch.yml` via OIDC au moment de chaque run.

---

## À faire lors de la reconstruction prod (v1.0.0)

1. Relancer `setup-sp-jf-platform.ps1` et `setup-sp-jf-github.ps1` si les SPs sont absents
2. Créer l'environnement GitHub `prod` avec reviewer obligatoire
3. Ajouter le federated credential `github-prod` sur sp-jf-platform (`repo:…:environment:prod`)
4. Créer les containers blob `lz-tfstates` et `app-tfstates` si absents
5. Appliquer `lz_prod` via CI/CD avant `prod`
