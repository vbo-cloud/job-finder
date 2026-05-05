# Backlog — job-finder

Améliorations et dettes techniques identifiées au fil du projet.

---

## CI/CD

### [improvement] Terraform plan avec `-out` en CI
Séparer le workflow en `plan -out=tfplan` (sur PR) et `apply tfplan` (sur merge).
Garantit que ce qui est appliqué est exactement ce qui a été reviewé.

---

## Terraform

### [refacto M1→M2] Upgrade provider azurerm ~> 3.0 → ~> 4.0
Nécessite de traiter les breaking changes (storage_account_id, etc.).
À faire pendant la phase de refactoring Terraform, pas en cours de M1.

---

## Nettoyage

### [post-apply] Supprimer les blocs `moved {}` après leur premier apply réussi
Les fichiers `moved.tf` sont temporaires — ils migrent les adresses de state sans détruire les ressources. Chacun peut être supprimé dès que l'apply correspondant a réussi.
- `envs/lz_dev/moved.tf`, `envs/lz_prod/moved.tf` : supprimer après apply lz (peut être fait indépendamment de M1)
- `envs/dev/moved.tf` : supprimer après apply dev
- `envs/prod/moved.tf` : supprimer à la fin du M1, lors du premier apply prod (ajouté exceptionnellement pour éviter un destroy au plan)
**Fichiers :** `envs/lz_dev/moved.tf`, `envs/lz_prod/moved.tf`, `envs/dev/moved.tf`, `envs/prod/moved.tf`

---

## Infrastructure

### [optional, if needed] Upgrade SKU PostgreSQL prod → GP_Standard_D2s_v3
Azure déconseille le tier Burstable pour la production. Acceptable tant que le trafic prod reste faible.
**Fichier :** `envs/prod/postgresql.tf`

### [optional] Self-hosted runner dans le VNet pour isoler le storage account Terraform state
Permettrait de fermer l'accès public au storage account. Coût : une VM Azure supplémentaire.

---

## Sécurité

### [optional] Renommer l'App Registration Azure → `sp-jf-github`
Purement cosmétique. `az ad app update --id <app-id> --display-name sp-jf-github`

---

## ADRs à rédiger

- **ADR-014** : Stratégie de cache (Redis vs cache applicatif)
- **ADR-015** : Frontend (Next.js vs React SPA vs serveur-rendu)
- **ADR-016** : Stratégie de test (unit, integration, e2e)
