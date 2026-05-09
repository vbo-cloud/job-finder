# Opérations manuelles — job-finder

Ce fichier documente toutes les opérations effectuées hors de Terraform.
Ces actions ne sont pas reproductibles automatiquement et doivent être refaites manuellement en cas de reconstruction de l'environnement.

---

## Azure — Fondations (hors Terraform)

- Tenant Azure créé manuellement
- Management Groups créés : un groupe projet, un sous-groupe et une subscription par environnement (dev, prod)
- Storage account Terraform state (`stjftfstatefrc`) créé manuellement avec resource locks
- App Registration `sp-jf-github` créé avec federated credentials OIDC (PR, env:dev, env:prod, main)
- Rôles subscription assignés au service principal : `Contributor`, `Resource Policy Contributor`

---

## GitHub — Configuration

- Organisation et dépôt privés créés
- Secrets : `CLAUDE_API_KEY`, `REVIEWER_GITHUB_TOKEN`
- Variables : `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`
- Environnements `dev` et `prod` créés (reviewer obligatoire sur prod)
- Branch protection rules sur `main` et `dev`

---

## RBAC — Key Vault

Le service principal ne peut pas s'auto-assigner des rôles sans avoir préalablement `User Access Administrator`. Ce droit initial est accordé manuellement.

### Fait sur kv-jf-dev-frc
- Rôle `User Access Administrator` assigné au service principal `sp-jf-github`
- Condition : rôles assignables limités à `Key Vault Secrets Officer` uniquement
- Le `Key Vault Secrets Officer` est ensuite créé automatiquement par Terraform

### À faire sur kv-jf-prod-frc
Même opération que dev, à effectuer après le premier apply prod qui créera le Key Vault.

---

## Policy Azure — Ajout manuel de "global"

La policy `allowed-locations` de `lz_prod` ne contenait pas `"global"` au moment où les Private DNS Zones ont été créées. La policy a été mise à jour manuellement dans Azure pour débloquer l'apply, puis le code Terraform a été mis à jour en conséquence.

---

## IAM — sp-jf-platform (SP gouvernance)

Service principal dédié à la gouvernance des landing zones. Créé manuellement car
l'opération de bootstrap nécessite des droits Owner qui ne peuvent pas être auto-provisionnés.

- App Registration `sp-jf-platform` créé dans Entra ID
- Rôles assignés au niveau subscription :
  - `RBAC Administrator` (conditionné — exclut Owner, User Access Administrator, RBAC Administrator lui-même)
  - `Resource Policy Contributor`
- `Storage Blob Data Contributor` sur le container `lz-tfstates` uniquement
- Federated credentials OIDC configurés pour GitHub Actions :
  - `github-pr` → pull_request
  - `github-dev` → environment:dev
- Variable GitHub `AZURE_PLATFORM_CLIENT_ID` ajoutée
- Jobs `apply-lz-dev` et `plan lz_dev` migrés vers ce SP dans les workflows CI/CD

### Après migration
- Révoquer `User Access Administrator` sur `sp-jf-github` — retour à Contributor + rôles data-plane uniquement

---

## IAM — Projet Terraform séparé

Les role assignments sont gérés dans `JobFinder/Terraform/iam/`, appliqué
manuellement avec le compte utilisateur (pas via sp-jf-github).

```bash
cd JobFinder/Terraform/iam/dev
terraform init
terraform apply
```

Faire de même pour `iam/prod/` lors du mirror prod.
Révoquer `User Access Administrator` sur kv-jf-dev-frc et kv-jf-lz-dev-frc
depuis le portail une fois l'apply IAM confirmé.
