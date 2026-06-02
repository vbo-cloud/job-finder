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

### [refacto M1→M2] Désactiver les access keys sur le storage account applicatif
`shared_access_key_enabled = false` — nécessite azurerm ~> 4.0 (le provider 3.x
utilise les clés en interne à la création). À combiner avec la migration provider.
**Fichier :** `modules/storage/main.tf`

### [optional] Authentification Entra ID pour le backend Terraform state
Ajouter `use_azuread_auth = true` dans tous les `backend.tf` pour que Terraform
accède au storage account de state via token Entra ID plutôt que via access keys.
Nécessite le rôle `Storage Blob Data Contributor` sur `stjftfstatefrc` pour :
- `sp-jf-github` (applies CI/CD)
- Le compte utilisateur personnel (applies manuels `iam/`)
**Fichiers :** tous les `backend.tf`

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

### [prod] Augmenter max_executions sur les jobs queue
En dev, `max_executions = 1` sur tous les jobs queue. À revisiter pour prod :
- `job-jf-prod-frc-embedding-offer` et `job-jf-prod-frc-matching` : prévoir `max_executions = 5`
  selon le volume d'offres traitées.
**Fichier :** `envs/prod/container_apps.tf` (à créer lors du mirror prod)

### [optional] Self-hosted runner dans le VNet pour fermer l'accès public des resources data plane

**Problème actuel**

Le provider azurerm utilise le **data plane** (et non l'API ARM management) pour certaines ressources :
- `azurerm_storage_container` → appelle `https://{account}.blob.core.windows.net/{container}`
- `azurerm_key_vault_secret` → appelle `https://{vault}.vault.azure.net/secrets/{name}`

Ces endpoints sont sur réseau privé (`public_network_access_enabled = false`). Le runner GitHub-hosted étant public, il ne peut pas les atteindre → 403 à l'apply.

**Workaround actuel (M1)**

`public_network_access_enabled = true` sur le storage account et le Key Vault. La protection reste assurée par le RBAC (rôles data-plane requis). Identique au compromis déjà documenté pour le Key Vault (PR #11).
**Fichiers :** `modules/storage/main.tf`, `modules/keyvault/main.tf`

**Solution cible**

Un runner self-hosted dans le VNet peut atteindre les endpoints privés. Options par ordre de coût croissant :
- **Container Apps Jobs** (runner éphémère) — quelques centimes par run, s'arrête après le workflow. Pattern recommandé par GitHub pour Azure. Non trivial à mettre en place.
- **VM scale set à zéro** — scale à zéro au repos, coût de stockage résiduel uniquement.
- **VM permanente** — ~100€/mois. Disproportionné pour un projet portfolio.

Une fois un runner VNet en place : passer `public_network_access_enabled = false` sur le storage et le Key Vault, et supprimer les commentaires de workaround.

---

## Sécurité

### [hardening] Réduire le scope Contributor de sp-jf-platform à rg-jf-lz-dev-frc

**Contexte**

`sp-jf-platform` dispose actuellement de `Contributor` au scope subscription pour pouvoir créer et modifier les ressources de `lz_dev`. Ce scope large est nécessaire au bootstrap (création du RG `rg-jf-lz-dev-frc` lui-même), mais devient inutilement large une fois le RG stable.

**Solution cible**

Une fois `lz_dev` appliqué avec succès et `rg-jf-lz-dev-frc` stable :
1. Réduire le scope de `Contributor` à `rg-jf-lz-dev-frc` uniquement
2. Implémenter un mécanisme de bootstrap one-shot (job GitHub dédié ou script manuel) pour recréer le RG en cas de reconstruction depuis zéro — ce job utiliserait un accès temporaire élevé, révoqué après exécution

`RBAC Administrator` et `Resource Policy Contributor` restent au scope subscription — ils en ont besoin pour les policies et role assignments globaux.

**Bénéfice** : réduit le blast radius si les credentials de `sp-jf-platform` sont compromis.

**Fichier :** `JobFinder/powershell/setup-sp-jf-platform.ps1`

---

### [optional] Renommer l'App Registration Azure → `sp-jf-github`
Purement cosmétique. `az ad app update --id <app-id> --display-name sp-jf-github`

---

## Architecture IAM / Gouvernance

### [refacto M1→M2] Créer un SP platform dédié et migrer la gouvernance

**Contexte du problème**

Actuellement, `sp-jf-github` est le SP unique qui gère à la fois les landing zones (`lz_dev/`, `lz_prod/`) et les couches applicatives (`dev/`, `prod/`). Ce SP est limité à Contributor + rôles data-plane, ce qui crée des blocages dès qu'une opération de gouvernance requiert des droits élevés :
- Créer une policy assignment avec `roleDefinitionIds` → le caller doit posséder le rôle délégué (Owner pour déléguer Owner à la Managed Identity)
- Poser des management locks directement → nécessite `Microsoft.Authorization/locks/write` (Owner ou rôle custom)
- Assigner des rôles à d'autres SPs → nécessite `Microsoft.Authorization/roleAssignments/write`

En entreprise suivant Azure CAF, la landing zone est gérée par un SP platform dédié avec des droits élevés. La sécurité est compensée par des contrôles stricts sur le pipeline (branch protection, approvals obligatoires, audit log). Le SP applicatif reste limité au strict nécessaire.

**État actuel (2026-05-06)**
- `sp-jf-github` dispose de Contributor + User Access Administrator + Storage Blob Data Contributor au niveau subscription
- Rôle Owner révoqué
- `iam/dev/` supprimé — les role assignments et la policy assignment sont désormais gérés directement par CI/CD depuis `lz_dev/rbac.tf` et `lz_dev/lock-policy.tf`

**Travail restant pour M1→M2**
- Créer `sp-jf-platform` dans Entra ID avec Owner au niveau subscription et OIDC configuré pour GitHub Actions
- Migrer les jobs `apply-lz-dev` et `apply-lz-prod` vers `sp-jf-platform` dans `.github/workflows/terraformApply.yml`
- Révoquer User Access Administrator sur `sp-jf-github` — retour au Contributor + rôles data-plane uniquement
- Documenter la création de `sp-jf-platform` dans `docs/MANUAL_OPERATIONS.md`
- Utiliser `iam/prod/` pour le bootstrap one-shot de `sp-jf-platform` (opération manuelle, une seule fois)

**Solution cible**

Deux SPs distincts, deux pipelines :

- **`sp-jf-platform`** — Owner au niveau subscription. Déploie uniquement `lz_dev/` et `lz_prod/` via CI/CD. Crée les policies, les assignments, les locks, les role assignments pour les autres SPs.
- **`sp-jf-github`** — Contributor + rôles data-plane. Déploie uniquement `dev/` et `prod/`. Ne touche pas à la gouvernance.

**Ce que ça élimine**
- Le rôle User Access Administrator sur `sp-jf-github`
- Toute dépendance à `iam/` pour la gestion courante des droits

**Comportement de la policy de lock à connaître**
- Tag `protect=true` retiré → le lock **reste** (la policy ne supprime pas les locks existants)
- Lock supprimé manuellement → Azure Policy le **repose** à la prochaine évaluation (~24h ou au prochain événement sur la ressource)
- Compléter avec une alerte Azure Monitor sur l'événement `Microsoft.Authorization/locks/delete` pour détecter toute suppression en temps réel

**Fichiers concernés :** `.github/workflows/terraformApply.yml`, `envs/lz_dev/lock-policy.tf`, `envs/lz_dev/rbac.tf` (à créer), `iam/dev/` (à supprimer), `docs/MANUAL_OPERATIONS.md`

---

## Azure OpenAI

### [refacto M1→M2] Passer local_auth_enabled = false + Managed Identity sur OpenAI

**Contexte**

En M1, `local_auth_enabled = true` sur le compte Azure OpenAI — les agents s'authentifient avec une clé API stockée dans Key Vault. C'est acceptable en dev mais pas idéal en prod : une clé API est une secret à gérer, stocker et rotater.

**Solution cible (M2)**

Quand les Container Apps existent avec une Managed Identity :
1. Passer `local_auth_enabled = false` dans `modules/openai/main.tf`
2. Assigner le rôle `Cognitive Services OpenAI User` à la Managed Identity de chaque agent sur le compte OpenAI
3. Les agents s'authentifient via token Entra ID — plus de clé API
4. Supprimer les secrets `openai-api-key` du Key Vault — ils deviennent inutiles

Exposer `local_auth_enabled` comme variable dans le module pour pouvoir le différencier par environnement si besoin.

**Fichier :** `modules/openai/main.tf`

---

## Qualité du code Terraform

### [refacto M1→M2] Ajouter des blocs `validation` sur les variables de modules
Les modules Terraform n'ont pas systématiquement de blocs `validation` sur leurs variables. Ajouter des validations sur tous les champs qui ont des contraintes évidentes (formats, plages de valeurs, valeurs acceptées) pour faire échouer le `plan` avec un message clair plutôt qu'un comportement inattendu à l'apply ou au runtime. Ne pas valider les champs sans contrainte (`name`, `location`) qui sont de toute façon validés par Azure.
**Fichiers :** tous les `modules/*/variables.tf`

---

## Release 1.0.0 — Environnement Staging

### [release/1.0.0] Créer un environnement staging éphémère pour la validation pre-prod

En entreprise, une branche release déclenche un environnement staging — copie isolée de prod créée from scratch pour valider l'application avant mise en production réelle.

**Workflow cible**

1. Ouverture de `release/1.0.0` → CI/CD déploie automatiquement `lz_staging/` + `staging/`
2. Données de test injectées (offres fictives, CV de test)
3. Tests end-to-end automatisés dans la pipeline :
   - Les agents tournent avec de vraies offres de test
   - Un CV de test est soumis via l'API
   - Le mail de matching est reçu et vérifié
4. Validation humaine
5. Merge `release/1.0.0` → `main` → CI/CD déploie prod
6. Tag `v1.0.0`, environnement staging détruit automatiquement

**Principes**
- Staging est **éphémère** — créé à l'ouverture de la release, détruit après le merge. Zéro coût résiduel.
- Même code Terraform que prod, uniquement `env = "staging"` différent.
- Tests end-to-end automatisés, pas manuels.

**Fichiers à créer**
- `envs/lz_staging/` — landing zone staging
- `envs/staging/`    — infra applicative staging
- `.github/workflows/terraformStaging.yml` — déploiement et destruction automatiques
- `tests/e2e/`       — tests end-to-end à définir en M2

---

## FastAPI — Dette technique

### [pre-v1.0.0] Contrainte unique sur cvs.user_id
Ajouter une migration Alembic `003_add_uq_cvs_user_id.py` avec
`uq_cvs_user_id` sur `cvs.user_id`. Remplacer le select-then-insert
dans `routers/cv.py` par un `pg_insert ON CONFLICT DO UPDATE` —
cohérent avec le pattern `user_profiles`.

### [pre-v1.0.0] Pincer les dépendances de la webapp
Lancer `pip-compile requirements.txt` dans `agents/webapp/` pour
générer un lockfile reproductible. À faire avant v1.0.0.

### [optional] Blob orphelin sur échec DB dans POST /cv/upload
Si le blob est uploadé mais que le `session.commit()` échoue ensuite,
le blob reste orphelin dans le Storage Account. Solution future :
nettoyer les blobs orphelins via un job périodique ou stocker l'URL
blob uniquement après le commit réussi (nécessite refacto du flow).

### [optional] Champ `updated_at` sur UserProfile
Ajouter `updated_at` (DateTime, auto-update) sur le modèle `UserProfile`
pour l'observabilité et l'audit. Nécessite une migration Alembic.

---

## ADRs à rédiger

- **ADR-014** : Stratégie de cache (Redis vs cache applicatif)
- **ADR-015** : Frontend (Next.js vs React SPA vs serveur-rendu)
- **ADR-016** : Stratégie de test (unit, integration, e2e)

---

## Automatisation IA — idées futures

### [optional] Tests unitaires générés par IA
Utiliser Claude Code pour générer des tests pytest couvrant les agents Python :
- `_upsert_offers` avec des données mockées (France Travail API simulée)
- Logique de cleanup (cutoff, branches NULL)
- `_embed_pending_offers` sans appel réel à l'API OpenAI (mock)
- `send_message` / `receive_message` dans `shared/bus.py`

### [optional] Enrichissement du reviewer agent — audit sécurité ciblé
Étendre le system prompt du reviewer agent pour détecter automatiquement :
- Secrets ou credentials exposés en clair
- Ressources critiques sans `prevent_destroy`
- NSG avec règles ouvertes à `0.0.0.0/0`
- Variables sensibles passées en plain-text plutôt qu'en secret Key Vault

### [optional] Analyse de logs Application Insights via IA
Script qui récupère les logs des dernières 24h depuis Application Insights
et les envoie à Claude pour détecter des anomalies, patterns d'erreur récurrents,
ou dégradations de performance. Utile pour le monitoring et démontre l'usage
de l'IA au-delà de la génération de code.
