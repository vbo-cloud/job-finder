# Backlog — job-finder

Améliorations et dettes techniques identifiées au fil du projet.

---

## Milestone 4 — Frontend Next.js



### [M4 — PR 1] Agent cv-analysis — extraction ROME codes depuis texte CV

Nouvel agent Python consommant la queue `cv-analysis`. GPT-4o-mini extrait les codes ROME depuis le texte brut du CV et met à jour `user_profiles.rome_codes`.

**Contexte :** `POST /cv/upload` envoie actuellement un message `offer-ready` après upload mais ne renseigne jamais les `rome_codes`. Sans cette étape, le job offer-fetching utilise les codes fallback hardcodés au lieu des vrais besoins du candidat.

**Fichiers à créer :** `agents/cv_analysis/main.py`, `agents/cv_analysis/Dockerfile`, `agents/cv_analysis/requirements.txt`

**Pipeline cible après cette PR :**
```
POST /cv/upload
  → extraction texte PDF ✅
  → embedding CV ✅
  → upsert cvs + user_profiles ✅
  → send_message("cv-analysis", {cv_id, user_id, raw_text})  ← NOUVEAU
  → [ne plus envoyer offer-ready ici — c'est cv-analysis qui le fait]

job-jf-dev-frc-cv-analysis (queue: cv-analysis)  ← NOUVEAU
  → lit le texte du CV depuis Blob Storage (via blob_url)
  → GPT-4o-mini : extrait liste de codes ROME depuis raw_text
  → UPDATE user_profiles SET rome_codes = [...] WHERE user_id = ?
  → send_message("offer-ready", {rome_codes, ...})
```

**Implémentation :**
- `agents/cv_analysis/main.py` : consomme `cv-analysis`, lit le texte brut du CV depuis Blob Storage via `blob_url` (BlobServiceClient + DefaultAzureCredential), appel GPT-4o-mini avec prompt système dédié, parse la réponse JSON `{"rome_codes": ["M1805", ...]}`, UPDATE `user_profiles`, envoie `offer-ready`
- Prompt GPT-4o-mini : extrait les 3 à 5 codes ROME les plus pertinents depuis le texte du CV, retourne uniquement du JSON valide
- `agents/webapp/routers/cv.py` : remplacer `send_message("offer-ready", ...)` par `send_message("cv-analysis", {cv_id, user_id, blob_url})` — passer `blob_url` plutôt que `raw_text` : les CVs volumineux peuvent dépasser la limite de 256 KB des messages Service Bus Standard. L'agent cv-analysis lit le texte depuis le blob (déjà stocké en amont) via son URL.
- `envs/dev/container_apps.tf` : nouveau module `job_cv_analysis` (queue: `cv-analysis`, image `agents/cv-analysis:latest`, variables `DATABASE_URL`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_CLIENT_ID`, `AZURE_SERVICEBUS_FULLY_QUALIFIED_NAMESPACE`)
- `envs/dev/servicebus.tf` ou fichier approprié : ajouter la queue `cv-analysis` dans le module Service Bus
- `buildAgents.yml` : ajouter le step build/push `agents/cv-analysis`
- `docs/JOURNAL.md` mis à jour

---

### [M4 — PR 2] Infrastructure frontend — Container App Next.js + CI/CD

**Fichiers :** `envs/dev/frontend.tf`, `modules/container_app/outputs.tf`, `.github/workflows/buildAgents.yml`

- `envs/dev/frontend.tf` : déploiement du Container App frontend via `module.container_app` — image `agents/frontend:latest`, port 3000, scale-to-zero, variables d'environnement :
  - `NEXT_PUBLIC_API_URL` : FQDN du Container App webapp (`module.webapp.fqdn`)
  - `NEXT_PUBLIC_ENTRA_TENANT_ID` : valeur de `data.azurerm_key_vault_secret.entra_tenant_id`
  - `NEXT_PUBLIC_ENTRA_CLIENT_ID` : valeur de `data.azurerm_key_vault_secret.entra_client_id`
- `buildAgents.yml` : ajouter step build/push `JobFinder/frontend` → `agents/frontend:latest` + `az containerapp update` pour le frontend
- `outputs.tf` : exposer `frontend_url` (FQDN public du Container App frontend)
- **Dockerfile frontend en build multi-stage** : passer du build mono-stage actuel (PR #88) à `builder` → `runner` (sortie `.next/standalone`, dépendances dev élaguées) pour réduire fortement la taille de l'image. Nécessite `output: "standalone"` dans `next.config.mjs`. La taille d'image ne compte qu'au déploiement Container Apps, d'où le report dans cette PR d'infra.
- `docs/JOURNAL.md` mis à jour
- **[M4 — PR 2, au déploiement]** Configurer `images.remotePatterns` dans `next.config.mjs` avec les domaines des images externes utilisées (avatars utilisateur, logos d'entreprises dans les offres, etc.). Actuellement `remotePatterns: []` — toute image distante via `next/image` sera bloquée jusqu'à ce que ce champ soit renseigné.

---

### [M4 — PR 3] Frontend Next.js — setup projet + auth Entra External ID

Initialisation du projet Next.js et mise en place de l'authentification.

**Répertoire :** `JobFinder/frontend/`

- `npx create-next-app@14` avec TypeScript + Tailwind CSS + App Router
- `Dockerfile` : image Node.js 20-alpine, `npm run build` + `npm start`, port 3000
- `.dockerignore` : exclure `node_modules`, `.next`, `.env*`
- Intégration MSAL : `@azure/msal-browser` + `@azure/msal-react`
- `lib/auth/msalConfig.ts` : configuration MSAL depuis les variables d'environnement (`NEXT_PUBLIC_ENTRA_*`)
- `lib/auth/AuthProvider.tsx` : `MsalProvider` wrappant l'app entière (`"use client"`)
- `lib/api/client.ts` : instance Axios avec intercepteur qui injecte le JWT Bearer dans chaque requête
- Page `/login` ou composant de garde : redirige vers le login MSAL si non authentifié
- `docs/JOURNAL.md` mis à jour

---

### [M4 — PR 4] Frontend — page upload CV avec animation Three.js

Page d'accueil avec l'animation sphères + upload CV.

**Fichiers :** `app/page.tsx` et composants associés

- `components/upload/OrbitAnimation.tsx` : animation Three.js — sphères en orbite autour d'une icône document centrale (`"use client"`)
- `components/upload/CVDropzone.tsx` : zone de dépôt PDF, validation client (type + taille max 10 MB), appel `POST /cv/upload`
- États visuels :
  - Idle : sphères en orbite, icône "+" au centre
  - Uploading : sphères convergent vers le centre, spinner
  - Processing : icône remplacée par miniature du PDF, texte "Analyse en cours…"
  - Done : transition vers `/library`
- Gestion d'erreur : toast si upload échoue (fichier invalide, serveur indisponible)
- `docs/JOURNAL.md` mis à jour

---

### [M4 — PR 5] Frontend — bibliothèque de CV

**Fichiers :** `app/library/page.tsx` et composants

- `GET /matches` + `GET /profile` appelés au chargement
- `components/library/CVGrid.tsx` : grille horizontale scrollable, une carte par CV
- `components/library/CVCard.tsx` : nom du CV, date d'analyse, nombre de nouveaux matchs, nombre total, score global
- Indicateurs globaux sous la grille : total nouveaux matchs, total matchs disponibles
- État vide : message "Aucun CV importé" + bouton retour upload
- Actions sur chaque carte : renommer, supprimer (confirmation)
- Clic sur une carte → navigation vers `/cv/[id]`
- `docs/JOURNAL.md` mis à jour

---

### [M4 — PR 6] Frontend — vue détail CV (placeholders cv-review)

**Fichiers :** `app/cv/[id]/page.tsx` et composants

- Zoom fluide à l'ouverture (Framer Motion)
- Deux onglets : **CV Review** et **Offers**
- **Onglet CV Review** : placeholder "Analyse en cours…" ou données mockées — sera remplacé par les vraies données de l'agent cv-review en M4 bis
- **Onglet Offers** :
  - `components/cv/OfferList.tsx` : liste des offres avec titre, entreprise, localisation, score, date, bouton favori, lien "Postuler"
  - `components/cv/OfferCard.tsx` : carte dépliable — description complète, compétences requises, placeholder "Analyse des écarts" (rempli par cv-review plus tard)
- Navigation gauche/droite entre CV (Framer Motion)
- `docs/JOURNAL.md` mis à jour

---

### [M4 — PR 7] Frontend — page profil utilisateur

**Fichiers :** `app/profile/page.tsx`

- Appels `GET /profile` + `PUT /profile`
- Formulaire : localisation, types de contrat, catégories métier
- `rome_codes` affichés en lecture seule (gérés par l'agent, non modifiables)
- Sauvegarde avec feedback visuel (toast succès/erreur)
- `docs/JOURNAL.md` mis à jour

---

### [SUPERSEDED — voir ADR-018] Agent cv-review — analyse CV vs offres (forces/faiblesses/suggestions)

> ⚠️ Conception remplacée par `docs/adr/ADR-018-monetization-architecture.md` : review globale par CV → analyse par paire CV↔offre (table `match_analyses`), déclenchée automatiquement sur le top N courant par palier + à la demande via crédits. Le détail ci-dessous est conservé pour mémoire mais ne doit plus servir de base d'implémentation.

Agent Python consommant `match-ready`. Analyse le CV contre les top offres matchées et produit une review structurée.

**Nouveau modèle DB :** table `cv_reviews`
```
cv_reviews
  id          UUID PK
  cv_id       UUID FK → cvs.id
  forces      TEXT[]         nullable=False
  faiblesses  TEXT[]         nullable=False
  suggestions TEXT[]         nullable=False
  competences_detectees   TEXT[]  nullable=False
  competences_manquantes  TEXT[]  nullable=False
  score_global            Float   nullable=False
  created_at  TIMESTAMPTZ    nullable=False, default=utcnow
```
⚠️ `score_global` est de type `Float` (SQLAlchemy) — pas `Numeric` — acceptable pour un score de similarité non critique. Toutes les colonnes doivent avoir `nullable=False` ou `nullable=True` explicite (convention CLAUDE.md). `DateTime(timezone=True)` sur `created_at`.

**Fichiers à créer :** `agents/cv_review/main.py`, `agents/cv_review/Dockerfile`, `agents/cv_review/requirements.txt`
**Migration :** `migrations/versions/004_add_cv_reviews.py`
**Nouveau endpoint FastAPI :** `GET /cv/{cv_id}/review` → retourne la `cv_reviews` du CV
**Terraform :** nouveau Container App Job `job-jf-dev-frc-cv-review` (queue: `match-ready`)
**CI/CD :** step build/push `agents/cv-review` dans `buildAgents.yml`

---

### [M4 — PR 9] Frontend — brancher cv-review sur la vue détail CV

Remplacer les placeholders de l'onglet "CV Review" par les vraies données.

**Fichiers :** `app/cv/[id]/page.tsx`, `components/cv/CVReview.tsx`

- Appel `GET /cv/{cv_id}/review`
- Si la review n'existe pas encore : afficher "Analyse en cours…" (l'agent n'a pas encore tourné)
- Si disponible : afficher forces, faiblesses, suggestions, compétences détectées/manquantes, score global
- Idem pour "Analyse des écarts" dans les cartes d'offres dépliables

---



---

### Milestone 5 : Monitoring et tests

### [M5 — PR 1] ADR-017 : Terraform — action group + 6 alertes + injection APPLICATIONINSIGHTS_CONNECTION_STRING

Implémentation de l'ADR-017, partie infrastructure.

**Fichiers :** `envs/dev/monitoring.tf`, `envs/dev/container_apps.tf`, `envs/dev/webapp.tf`

- `monitoring.tf` : `azurerm_monitor_action_group` (email vincentboutin.dev@gmail.com) + 6 alertes :
  - `alert-jf-dev-frc-webapp-5xx` — log alert KQL, taux 5xx > 5% sur 5 min, sévérité 0
  - `alert-jf-dev-frc-servicebus-dlq` — metric alert, DeadletteredMessages > 0, sévérité 1
  - `alert-jf-dev-frc-postgresql-cpu` — metric alert, cpu_percent > 80% sur 10 min, sévérité 1
  - `alert-jf-dev-frc-openai-throttling` — metric alert, `AzureOpenAIRequests` filtré sur HTTP 429 > 5 sur 5 min, sévérité 2 — ⚠️ `BlockedCalls` ne s'applique qu'au tier Provisioned throughput ; sur le tier pay-per-use (utilisé ici) le bon metric est `AzureOpenAIRequests` avec dimension `StatusCode = 429`
  - `alert-jf-dev-frc-agent-fetch-absent` — log alert KQL, absence de `offer_fetch_run_completed` depuis 25h, sévérité 1
  - `alert-jf-dev-frc-webapp-availability` — standard web test GET `/docs` + metric alert availability < 99%, sévérité 0
- `container_apps.tf` : injecter `APPLICATIONINSIGHTS_CONNECTION_STRING` (secret depuis KV `appinsights-connection-string`) dans les 3 jobs
- `webapp.tf` : idem pour le Container App webapp
- Ajouter output `fqdn` dans `modules/container_app/outputs.tf` si absent
- `docs/JOURNAL.md` mis à jour

---

### [M5 — PR 2] ADR-017 : Python — instrumentation azure-monitor-opentelemetry + duration_seconds

Implémentation de l'ADR-017, partie code.

**Fichiers :** 4 `requirements.txt`, 3 `main.py` agents, `agents/webapp/main.py`

- Ajouter `azure-monitor-opentelemetry` dans les 4 `requirements.txt`
- Dans chaque `main()` : `configure_azure_monitor(connection_string=os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"))` — no-op si absent (dev local)
- Ajouter `duration_seconds` dans les logs de fin de run des 3 agents (`offer_fetch_run_completed`, `matching_run_completed`, `cleanup_completed`)
- `docs/JOURNAL.md` mis à jour

### [M5 — PR 3] Tests unitaires Python (ADR-016)

**Fichiers :** `JobFinder/python/tests/`, `requirements.txt` des agents concernés

- `pytest` + `pytest-mock` dans les requirements des agents concernés
- `tests/test_cleanup.py` : logique cutoff, branche NULL `ft_updated_at`
- `tests/test_auth.py` : validation JWT, expiration, mauvais issuer (mock JWKS)
- `tests/test_cv_upload.py` : validation content_type, magic bytes, taille max
- `tests/test_cors.py` : scénarios preflight CORS (origine autorisée présente → en-tête `Access-Control-Allow-Origin` ; origine absente / `CORS_ALLOWED_ORIGINS` non configurée → preflight rejeté, pas d'en-tête) — follow-up identifié par le reviewer de la PR #87 (CORS)
- Step `pytest` dans le workflow CI/CD : déclenché sur tout changement dans `JobFinder/python/**` (indépendamment des path filters Terraform par environnement), s'exécute avant les steps de plan. Trigger à spécifier explicitement dans le PR pour éviter toute ambiguité lors de l'implémentation.
---

## CI/CD

### [improvement] Terraform plan avec `-out` en CI
Séparer le workflow en `plan -out=tfplan` (sur PR) et `apply tfplan` (sur merge).
Garantit que ce qui est appliqué est exactement ce qui a été reviewé.

---

## Terraform

### [hardening] Désactiver les access keys sur le storage account applicatif
`shared_access_key_enabled = false` — provider azurerm ~> 4.0 déjà en place.
**Fichier :** `modules/storage/main.tf`

### [optional] Authentification Entra ID pour le backend Terraform state
Ajouter `use_azuread_auth = true` dans tous les `backend.tf` pour que Terraform
accède au storage account de state via token Entra ID plutôt que via access keys.
Nécessite le rôle `Storage Blob Data Contributor` sur `stjftfstatefrc` pour :
- `sp-jf-github` (applies CI/CD)
- Le compte utilisateur personnel (applies manuels `iam/`)
**Fichiers :** tous les `backend.tf`

---


## Infrastructure

### [optional, if needed] Upgrade SKU PostgreSQL prod → GP_Standard_D2s_v3
Azure déconseille le tier Burstable pour la production. Acceptable tant que le trafic prod reste faible.
**Fichier :** `envs/prod/postgresql.tf`

### [prod] Augmenter max_executions sur les jobs queue
En dev, `max_executions = 1` sur tous les jobs queue. À revisiter pour prod :
- `job-jf-prod-frc-fetch` et `job-jf-prod-frc-matching` : prévoir `max_executions = 5`
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

### [improvement] Extraire `Invoke-GraphRequest` dans un `graph-utils.ps1` partagé

`Invoke-GraphRequest` est actuellement dupliquée à l'identique dans `setup-entra-external-tenant.ps1` et `setup-sp-jf-ciam-setup.ps1`. À extraire dans un fichier partagé (dot-sourcing `. "$PSScriptRoot/graph-utils.ps1"`) dès qu'un 3ᵉ script Graph viendra s'ajouter. En dessous de deux scripts, la duplication est acceptable — au-delà, elle devient une dette de maintenance.

**Fichier à créer :** `JobFinder/powershell/graph-utils.ps1`

---

### [hardening] Écrire les secrets Entra directement dans Key Vault au lieu de la console

`setup-entra-external-tenant.ps1` affiche actuellement les secrets sensibles dans la
console (section résumé) pour copier-coller manuel dans `kv-jf-dev-frc` :
le client secret Entra External ID (`entra-external-client-secret`) et le
secret OAuth Google (`google-oauth-client-secret`). Ces valeurs transitent par
l'historique du terminal et risquent de fuiter.

**Solution cible :** écrire directement dans Key Vault via
`az keyvault secret set --vault-name kv-jf-dev-frc --name <secret> --value <valeur>`
au lieu de les afficher. Ne garder en console que les identifiants non sensibles
(tenant id, client ids). Conditionner l'écriture KV à la présence d'un secret
fraîchement généré (le bloc idempotent ne régénère pas un secret encore valide).

**Fichier :** `JobFinder/powershell/setup-entra-external-tenant.ps1`

---

### [hardening, pre-v1.0.0] Passe sécurité — séparation des privilèges, à commencer par PostgreSQL

**Contexte**

Diagnostic remonté par Claude Code (session d'investigation, pas encore de correctif appliqué) :
il n'existe aujourd'hui qu'un seul rôle Postgres, `administrator_login` (superutilisateur), avec un
unique mot de passe généré (`random_password.admin`). Ce rôle est stocké une seule fois dans Key
Vault (`postgresql-connection-string`, `main.tf:74-82`) et cette même chaîne de connexion admin est
injectée telle quelle comme `DATABASE_URL` dans **tous** les services : le webapp (seul service
exposé publiquement, qui accepte des uploads de CV/PDF venant d'utilisateurs non fiables) ET tous
les jobs batch internes (`offer_fetching`, `matching`, `cv_analysis`...). Aucun `CREATE ROLE` limité,
aucun `GRANT` restreint nulle part dans les migrations ou le Terraform.

C'est une violation classique du principe du moindre privilège, pas critique en dev, mais à corriger
avant une mise en prod : si le webapp était compromis (dépendance vulnérable, faille de parsing PDF,
etc.), l'attaquant aurait un contrôle total sur toute la base — y compris les tables `offers` et
`matches` dont il n'a normalement pas besoin — au lieu d'être cantonné à `user_profiles`/`cvs`.

**Solution cible (Postgres)**

Créer des rôles Postgres distincts par service avec des `GRANT` ciblés — ex. un rôle `webapp` limité
en lecture/écriture à `user_profiles`, `cvs`, `matches` (pas `offers`), un rôle par job batch limité
aux tables qu'il touche réellement. Chaque rôle avec son propre secret Key Vault plutôt qu'une
`DATABASE_URL` admin partagée.

**Périmètre élargi**

Ce point PostgreSQL est le déclencheur, mais l'idée est d'en faire une passe de sécurité plus large
sur la séparation des privilèges dans le projet (accès Key Vault, scopes des managed identities,
permissions storage account, etc.) plutôt qu'un correctif isolé. À cadrer avec Claude Cowork avant
implémentation (choix des rôles, granularité des `GRANT`, impact sur les migrations Alembic
existantes) — rien n'a été modifié à ce stade.

**Fichiers concernés (au moins) :** `lz_dev/postgresql.tf` ou équivalent (rôle admin actuel),
migrations Alembic (`python/migrations/`), définitions des variables d'environnement `DATABASE_URL`
par service (`envs/dev/container_apps.tf` et jobs associés).

---


## Azure OpenAI

### [hardening, pre-v1.0.0] Passer local_auth_enabled = false + Managed Identity sur OpenAI

Les agents s'authentifient actuellement avec une clé API stockée dans Key Vault (`openai-api-key`). La Managed Identity (UAMI `id-jf-dev-frc-caj`) est déjà en place — même pattern que la migration Service Bus (PR #75).

**Solution cible :**
1. Passer `local_auth_enabled = false` dans `modules/openai/main.tf`
2. Assigner le rôle `Cognitive Services OpenAI User` à la UAMI sur le compte OpenAI (dans `lz_dev` via sp-jf-platform)
3. Supprimer les secrets `openai-api-key` des Container Apps et du Key Vault
4. Exposer `local_auth_enabled` comme variable du module

**Fichier :** `modules/openai/main.tf`

---

## Qualité du code Terraform

### [improvement] Ajouter des blocs `validation` sur les variables de modules
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
- `tests/e2e/`       — tests end-to-end à définir en M4

---

## FastAPI — Dette technique

### [urgent] Pincer les dépendances et ajouter un smoke-test de démarrage webapp

Trois manques successifs dans le Dockerfile/requirements webapp ont causé trois crash-loops en prod sans être détectés en CI :
- PR #88 : `alembic` absent de `requirements.txt`
- PR #90 : `python-multipart` absent de `requirements.txt`
- PR #91 : `migrations/` absent du build context Dockerfile

**Solution 1 — `pip-compile` (lockfile)** : adopter `pip-tools` pour séparer les dépendances directes (non épinglées, dans `requirements.in`) des dépendances résolues et épinglées (générées dans `requirements.txt`). `pip-compile` résout aussi les dépendances transverses — `python-multipart` serait apparu automatiquement.

```bash
pip install pip-tools
cd JobFinder/python/agents/webapp
# renommer requirements.txt → requirements.in
pip-compile requirements.in  # génère requirements.txt épinglé
```

**Solution 2 — smoke-test de démarrage** : ajouter un step dans `buildAgents.yml` qui lance l'image webapp avec `docker run --rm -e DATABASE_URL=postgresql://x:x@localhost/x <image> python -c "import main"` (ou équivalent) pour valider que l'import réussit avant le push vers ACR.

**Fichiers :** `agents/webapp/requirements.in` (à créer), `agents/webapp/requirements.txt` (regénéré), `.github/workflows/buildAgents.yml`.

### [optional] Blob orphelin sur échec DB dans POST /cv/upload
Si le blob est uploadé mais que le `session.commit()` échoue ensuite,
le blob reste orphelin dans le Storage Account. Solution future :
nettoyer les blobs orphelins via un job périodique ou stocker l'URL
blob uniquement après le commit réussi (nécessite refacto du flow).

### [v1.0.0] Renommer la UAMI `id-jf-dev-frc-caj` en `id-jf-dev-frc-apps`
La UAMI est partagée entre les Container App Jobs et la webapp Container App.
Le suffixe `caj` (Container App Job) ne reflète plus son périmètre réel.
À renommer lors du provisionnement prod à v1.0.0 pour partir sur une base propre.

### [optional] Champ `updated_at` sur UserProfile
Ajouter `updated_at` (DateTime, auto-update) sur le modèle `UserProfile`
pour l'observabilité et l'audit. Nécessite une migration Alembic.

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

---

## Carte des communes (feature/profile-geo-search) — suites identifiées en review

### [optional] Support tactile du pinceau de communes
`CommunePaintLayer` n'écoute que les événements souris (`mousedown`/`mousemove`/`mouseup`) —
la carte est inutilisable sur mobile/tablette. Migrer vers les Pointer Events
(`pointerdown`/`pointermove`/`pointerup` + `touch-action: none`) pour couvrir souris,
stylet et tactile avec un seul chemin de code.
Depuis la PR #154, la transition « focus pull » de l'accueil est elle aussi molette
uniquement : la migration devra ajouter un déclencheur tactile pour l'entrée/sortie du
mode carte (geste vertical, `touchstart` passif) et le coordonner avec la garde
« trait de pinceau en cours absorbe le scroll » de `HomeMapSection`.

### [optional] Sortir les GeoJSON du dépôt Git
`public/geo/` pèse ~38 Mo (dont 29 Mo de contours HD) versionnés dans Git — le clone
s'alourdit à chaque régénération du dataset. Pistes : Git LFS, ou hébergement sur le
Storage Account existant (CDN) avec téléchargement au build (`scripts/build-communes-geo.mjs`
tourne déjà en une commande ; risque : disponibilité des sources Etalab au moment du build).

---

## Carte à l'accueil (feature/home-map-transition, PR #154) — suites identifiées en review

### [a11y] Raccourci Escape pour sortir du mode carte
Aucun moyen clavier de quitter le mode carte de l'accueil (molette uniquement) — un
utilisateur clavier qui y entre est coincé. Piste déjà signalée par le `TODO(a11y)`
dans le handler wheel de `HomeMapSection.tsx` : écouter `keydown` Escape en mode
`"map"` et déclencher la même sortie (flush + reset de vue + transition).

### [optional] État « peinture en cours » orphelin si le mouseup n'est jamais délivré
Le trait se termine par le `mouseup` écouté sur `window` — il fonctionne donc aussi
hors du conteneur Leaflet, et c'est voulu (un trait en cours doit absorber le scroll
même si le curseur sort de la carte pendant le drag ; appeler `onPaintingChange(false)`
sur `mouseleave` casserait cette garde). Reste un cas limite : bouton relâché hors de
la fenêtre du navigateur sans que le `mouseup` soit délivré → `paintingRef` reste
`true` et bloque la sortie par molette jusqu'au clic suivant. Durcissement possible :
réinitialiser l'état de trait (`strokeRef`, `onPaintingChange(false)`) sur
`window.blur` dans `CommunePaintLayer`.

---

## Filtre géographique department fallback (feature/fix-commune-zone-department-fallback) — suites identifiées en review

### [optional] Index composite/partiel sur offers (commune, department)
`_commune_zone_condition()` filtre systématiquement `commune IS NULL AND department IN (...)`
comme une unité — actuellement couvert par deux index simple-colonne (`ix_offers_commune`,
`ix_offers_department`). Un index composite `(commune, department)`, ou mieux, un index partiel
`ON department WHERE commune IS NULL`, serait plus ciblé et plus petit. Pas urgent avec le volume
actuel (~5000 offres) ; à revisiter si la table grossit significativement.

### [optional] Chunker la lecture des migrations de backfill sur grosses tables
La migration `014_add_offer_department.py` charge tout le résultat de
`SELECT id, location FROM offers WHERE commune IS NULL` en mémoire via `fetchall()` avant de
backfiller. Sans risque pour le volume actuel (~3000 lignes), mais si une future migration de
backfill doit toucher un ordre de grandeur plus élevé de lignes, prévoir une lecture par lots
(curseur serveur ou pagination `LIMIT`/`OFFSET`) plutôt qu'un chargement complet en mémoire.

---

## Badge bibliothèque — zone, refresh et CORS (fix/library-unseen-count-refresh, PR #157) — suites identifiées en review

### [optional] Nettoyer `seenIds` si le retry de réconciliation échoue aussi
`CorrespondancesPanel.tsx` retente le `PATCH .../seen` quand le backend dit encore
`is_new: true` pour une offre déjà dans le cache local — mais si ce retry échoue aussi
(réseau, 5xx transitoire), l'id reste dans `seenIds` sans qu'aucun signal ne permette de
le retenter avant le prochain remontage de l'effet (nouveau fetch de `matches` : sélection
d'un autre CV, changement de zone, ou rechargement de page). Fenêtre étroite en pratique,
mais retirer l'id de `seenIds`/`localStorage` dans le `.catch()` permettrait un retry plus
rapide sans attendre un déclencheur externe.

### [optional] Garde anti-course sur `refreshTrigger` / `fetchCvs`
`LibrarySection.fetchCvs` n'a aucune protection contre les réponses hors-ordre (pas
d'`AbortController` ni de compteur de séquence) — si `refreshTrigger` est incrémenté deux
fois rapprochées (ex. sauvegarde de zone suivie immédiatement d'une consultation d'offre,
tous deux câblés sur ce compteur depuis PR #157), une réponse plus ancienne arrivant après
une plus récente écraserait l'état avec des données périmées. Rare et sans conséquence
grave (le badge se corrige au déclencheur suivant), mais à durcir si `LibrarySection` gagne
un jour un debounce ou si les déclencheurs se multiplient.

### [optional] Extraire la réconciliation `seenIds` en hook dédié
L'effet de réconciliation dans `CorrespondancesPanel.tsx` (retry du `PATCH .../seen` quand
le backend contredit le cache local) pourrait devenir un hook `useStaleSeenReconciliation(matches, cvId, seenIdsRef, onMatchSeen)` — rendrait l'intention explicite au point d'appel et le
comportement testable indépendamment du reste du composant, qui gère déjà plusieurs
préoccupations (tri, filtres, sélection, sauvegarde).

### [optional] Déplacer `commune_zone_condition` vers `shared/` si un 3e router en a besoin
`cv.py` importe actuellement `commune_zone_condition` directement depuis `routers.matches`
(couplage router-à-router). Acceptable tant que seul `cv.py` en dépend en plus de son
propre module ; si un troisième router a un jour besoin du filtre géographique, déplacer
la fonction vers un module partagé (ex. `shared/db_filters.py`) pour rendre la dépendance
explicite plutôt que de laisser les routers s'importer mutuellement.

---

## Profil expérience/description, blend intention et suppression de compte (feature/profile-experience-search-fields, PR #158) — suites identifiées en review

### [optional] Contraintes DB sur `experience_level` et `candidate_description`
`experience_level` (`String`) et `candidate_description` (`Text`) n'ont aucune contrainte
au niveau base — seule la couche Pydantic (`Literal["0-2", "2-5", "5+"]`,
`Field(max_length=1000)`) protège contre des valeurs invalides, et uniquement pour les
écritures passant par l'API. Un `CHECK (experience_level IN ('0-2', '2-5', '5+'))` et un
`CHECK (char_length(candidate_description) <= 1000)` (ou `sa.Enum`/`VARCHAR(1000)`)
fermeraient cette faille pour un accès direct DB ou un futur outil admin. Risque faible tant
que l'API reste le seul point d'écriture.

### [optional] Index vectoriel sur `intent_embedding`
La colonne `user_profiles.intent_embedding` (migration 016) n'a pas d'index `ivfflat`/`hnsw`.
Sans impact tant que le nombre d'utilisateurs reste faible ; à ajouter dans une migration
dédiée une fois la colonne peuplée en volume et si `matching/main.py` fait des recherches de
similarité dessus (pas le cas aujourd'hui — c'est un blend scalaire, pas une recherche ANN).

### [optional] Suppression de blobs non transactionnelle dans `delete_account`
`_delete_cv` supprime les blobs Azure avant le commit DB (trade-off documenté dans
`routers/cv.py` et `routers/profile.py`). Pour un compte avec N CVs, un échec DB après le
Nᵉ appel laisse les blobs des CVs déjà traités définitivement supprimés alors que leurs
lignes DB sont rollback. Amélioration possible : collecter toutes les URLs de blobs,
committer la transaction DB d'abord, supprimer les blobs ensuite — échange contre des
lignes orphelines (plus faciles à détecter et nettoyer) plutôt que des blobs orphelins. Le
cas d'échec mi-boucle est déjà loggé (`account_delete_blob_failed` avec
`deleted_blob_urls`) pour un nettoyage manuel en attendant.

### [optional] N+1 requêtes `rome_codes` dans la boucle `delete_account`
`_delete_cv` recharge et réécrit `user_profiles.rome_codes` à chaque CV plutôt que de
batcher les N CVs d'un compte en une seule opération. Sans impact aux volumes actuels par
utilisateur ; prévoir un chemin de suppression en lot si ce nombre grossit significativement.

### [optional] `intent_embedding` recalculé même si la valeur résultante ne change pas
`put_profile` relance un appel d'embedding Azure OpenAI dès qu'un champ intent
(`experience_level`/`candidate_description`) est présent dans le body, même si la valeur
résolue est identique à l'existante. Coût = un appel embed superflu par sauvegarde
inchangée ; à court-circuiter en comparant `intent_text` à la valeur stockée avant d'appeler
`embed()`, si ça devient un poste de coût notable.

### [optional] Allowlist explicite pour `set_` dans l'upsert `ON CONFLICT`
`put_profile` passe le dict `updated` complet en `set_=updated` sur `on_conflict_do_update`.
Aucun risque aujourd'hui (`ProfileUpdate` n'expose que des champs sûrs), mais si un futur
champ de `ProfileUpdate` ne doit jamais être modifiable sur conflit (ex. un équivalent de
`created_at`), il s'y glisserait silencieusement. Une allowlist explicite des colonnes
modifiables serait plus sûre à long terme.

### [a11y] `InfoTooltip` — dismiss clavier et positionnement sur petit écran
`InfoTooltip.tsx` s'affiche au survol/focus mais n'a pas de gestion `Escape` (contrairement
à la modale de `DeleteAccountSection`), et son positionnement `bottom-full left-full` peut
déborder de l'écran sur viewport étroit selon l'emplacement du bouton `?`. Cosmétique/a11y
mineur, pas de blocage fonctionnel.

### [optional] Modale de suppression de compte — focus trap `Tab` incomplet
`DeleteAccountSection.tsx` gère `Escape` pour fermer la modale mais ne piège pas la
navigation `Tab` — le focus peut sortir vers des éléments situés derrière l'overlay. Une
lib de focus-trap ou une gestion manuelle de `tabIndex` fermerait ce gap a11y ; faible
priorité pour un projet portfolio.

### [optional] `DeleteAccountSection` — erreurs réseau et 503 indifférenciées
Le `catch` de `handleConfirmDelete` affiche le même message générique pour un timeout
réseau et un 503 backend. Envisager de distinguer via le status HTTP de la réponse pour
un message plus actionnable (ex. suggérer un retry sur 503 vs vérifier la connexion sur
timeout).

---

## Bibliothèque — grille et bouton de suppression (feature/library-redesign, PR #159) — suites identifiées en review

### [optional] `MAX_PDF_BYTES` dupliqué entre frontend et backend
`LibrarySection.tsx`/`UploadSection.tsx` (frontend) et `routers/cv.py` (backend)
définissent chacun `MAX_PDF_BYTES = 10 * 1024 * 1024` séparément — actuellement identiques
(vérifié), mais rien n'empêche une dérive silencieuse si l'une des deux valeurs change sans
l'autre : le rejet client resterait à 10 Mo alors que le serveur accepterait/refuserait à un
seuil différent, ou l'inverse. Une constante partagée (ex. exposée par un endpoint de config,
ou documentée en commentaire croisé dans les deux fichiers) fermerait ce risque.

### [optional] `POST /cv/upload` — fichier entièrement bufferisé avant la vérification de taille
`routers/cv.py` lit tout le corps (`await file.read()`) avant de comparer sa taille à
`MAX_PDF_BYTES` et de renvoyer 413. Un upload volontairement surdimensionné consomme donc
mémoire et bande passante avant d'être rejeté. À durcir avec une vérification de
`Content-Length` ou une lecture par chunks avec arrêt anticipé, si l'endpoint est exposé à un
trafic non fiable.

### [optional] Durées d'animation de fermeture dupliquées en dur dans `CVCard.tsx`
`CLOSING_MS` (délai JS avant retour à `idle`) et les durées CSS inline des animations de
sortie (`emgLOut`/`emgROut`/`lineOutH`/`lineOut`, `.08s`) sont ajustées en cohérence à la
main plutôt que dérivées d'une seule source — si `CLOSING_MS` change, les durées
`animation` des `style` inline ne suivent pas automatiquement. Une custom property CSS
(`--closing-ms`) posée à côté du style inline et référencée par les keyframes
fermerait ce risque de désynchronisation ; impact actuel nul, les deux valeurs sont
cohérentes aujourd'hui.

### [optional] `scrollend` — course possible avec un autre scroll concurrent
`handleScrollToHome` (`HomeClient.tsx`) écoute `scrollend` sur le conteneur de scroll une
seule fois (`{ once: true }`) après avoir déclenché `home.scrollIntoView()`. Si un autre
scroll (utilisateur ou composant tiers) survient entre l'appel et l'événement, `finish()`
se déclenche sur ce scroll-là au lieu du nôtre — le sélecteur de fichier s'ouvrirait avant
que la page ait réellement atterri sur la section d'accueil. Cas limite jugé peu probable
en pratique (aucun autre scroll programmatique concurrent dans le flux actuel) ; à
surveiller si un futur scroll automatique est ajouté ailleurs sur la page.

## Re-matching sur changement d'intention du profil (feature/profile-intent-rematch, PR #161) — suites identifiées en review

### [optional] Corrélation des logs via `bind_contextvars` plutôt que `user_id` en paramètre
`_dispatch_offer_ready` (`routers/profile.py`) accepte `user_id` uniquement pour le logging.
Si ce pattern d'helpers de dispatch se répand dans d'autres routers, préférer
`structlog.contextvars.bind_contextvars(user_id=...)` en début de requête (ou un dict de
contexte structuré) pour que les identifiants de corrélation suivent automatiquement tous
les logs de la requête au lieu d'être threadés de fonction en fonction.

### [optional] Élargir le catch fire-and-forget aux autres exceptions transitoires Azure
Le `except ServiceBusError` de `_dispatch_offer_ready` couvre le contrat actuel, mais
`send_message` pourrait aussi lever d'autres exceptions transitoires du SDK Azure (ex.
`azure.core.exceptions.HttpResponseError` via le credential). Risque faible aujourd'hui vu
le contrat fire-and-forget (le run planifié suivant rattrape) — à réexaminer si le SLA du
matching se resserre : soit élargir le catch, soit remonter l'erreur avec retry.

## Agent d'analyse IA — CV seul + paires CV↔offre (feature/agent-analyse-cv-offres, PR #162) — suites identifiées en review

### [optional] Polling de l'analyse de paire — endpoint dédié plutôt que `GET /matches/cv/{cvId}` complet
`CorrespondancesPanel.tsx` interroge `GET /matches/cv/{cvId}` (liste complète des matchs)
toutes les 3s tant qu'au moins une analyse manuelle est en attente, pour ne lire que le champ
`analysis` des offres concernées. Inoffensif à `MATCH_ANALYSIS_AUTO_TOP_N = 1` (peu de matchs
par CV en bêta), mais devient coûteux si ce seuil augmente ou si un CV accumule beaucoup de
matchs — chaque tick refetch alors des dizaines/centaines de lignes pour ne lire qu'un ou deux
statuts. Un endpoint plus chirurgical (ex. `GET /matches/{cvId}/offers/{offerId}/analysis`,
ou un `GET` batché sur la liste des `offerId` en attente) éviterait de retélécharger tout le
match list à chaque tick. À faire si `MATCH_ANALYSIS_AUTO_TOP_N` est relevé au-delà de la
bêta ou si des CVs avec de très nombreux matchs deviennent courants.

## Diagnostic pipeline post-PR #162 (fix/cv-analysis-backfill-and-receive-timeout, PR #163) — suites identifiées

### [recommandé] Feedback UI après relance du matching depuis /profile
Changer l'expérience ou les informations complémentaires relance bien le matching
(PR #161, vérifié en production le 08/07 : run complet ~40 s après l'enregistrement),
mais l'UI ne le montre nulle part : ni indication « matching relancé / en cours » après
l'enregistrement, ni rafraîchissement des correspondances une fois le run terminé — il
faut recharger la page pour voir les nouveaux scores. C'est ce silence qui a fait
percevoir la fonctionnalité comme cassée. Pistes : état « Recherche mise à jour —
recalcul des correspondances… » sur la page profil après un enregistrement qui a
dispatché, et/ou re-fetch des matchs au retour sur l'accueil (poll léger de quelques
dizaines de secondes, sur le modèle du polling de `CvAnalysisCard`).

### [optional] `match-ready` sans consommateur — messages qui expirent en DLQ
La queue `match-ready` (job-matching → notification utilisateur, servicebus.tf) n'a
aucun consommateur : 27 messages actifs et 26 en dead-letter constatés le 08/07, les
plus anciens expirant vers la DLQ au fil de l'eau. Sans impact fonctionnel, mais du
bruit dans les métriques. À purger et/ou à doter d'un TTL court tant que l'agent de
notification n'existe pas.

### [optional] Purger la DLQ d'`offer-ready` (50 messages historiques)
50 messages accumulés en dead-letter sur `offer-ready` (constat du 08/07, antérieurs
aux fixes de la PR #163). Sans impact — le matching consomme normalement la queue —
mais à purger pour que le compteur DLQ redevienne un signal utile d'alerte.

---

## Bonus de rareté relative au corpus (feature/matching-corpus-relative-skills-weighting, PR #180) — suites identifiées

### [recommandé] Valider le seuil 0.75 sur le corpus réel après le premier run de fetch
Le seuil `TERM_STOPWORD_THRESHOLD` (0.75) a été validé sur corpus synthétique uniquement.
Après le premier run d'offer_fetching post-déploiement, vérifier qu'aucun terme réellement
discriminant n'est exclu sur le corpus de prod :
`SELECT term, doc_frequency, total_offers FROM term_stats WHERE term IN ('terraform','ci/cd');`
(ratio attendu bien en dessous de 0.75). Si un terme discriminant dépasse le seuil,
réévaluer la valeur plutôt que de l'accepter telle quelle.

### [recommandé] Valider le classement sur de vraies offres d'un secteur non-tech
Le corpus réel est probablement mono-sectoriel (repli `FALLBACK_ROME_CODES`, tous
informatique). Dès qu'un profil non-tech existe en base (ex. infirmier, code ROME
santé type J1506), déclencher offer_fetching pour ce code et vérifier que le bonus
produit un classement sensé sur de vraies offres — la généralisation reste une
hypothèse validée en synthétique tant que ce test n'a pas eu lieu.

### [optional] Colonne `tsvector` précalculée + index GIN si le corpus grossit
Les `to_tsvector('french', ...)` sont recalculés à chaque requête de matching
(~4600 offres, 2 runs/jour : acceptable). Si le corpus gagne un ordre de grandeur
ou si le matching devient plus fréquent, stocker une colonne `tsvector` générée
sur `offers`/`cvs` avec index GIN.

### [optional] Extraire `total_offers` dans une table meta plutôt que répété par ligne
Chaque ligne de `term_stats` porte le même `total_offers` pour un cycle donné —
redondant mais sans conséquence à ce volume. Une table snapshot séparée (ou une
ligne meta unique) serait plus propre si la table devait grossir ou être historisée.

---

Le pipeline de distillation LLM des offres (feature/offer-distillation-pipeline, PR #184)
et ses suites identifiées (transaction autour du SELECT + publish) ont été retirés
entièrement — voir docs/prompts/prompt-remove-offer-distillation.md. Le matching
repose de nouveau sur un embedding direct du texte brut de l'offre.

---

### [optional] `_embed_pending_offers` fait un UPDATE par offre (N+1) — revoir avant un backfill massif
`agents/offer_fetching/main.py::_embed_pending_offers` boucle sur les offres en attente et
exécute un `UPDATE` par offre à l'intérieur d'une seule transaction — correct pour l'atomicité,
mais lent à l'échelle (un backfill de plusieurs milliers d'offres, ex. reset complet des
embeddings). Acceptable à la cardinalité actuelle (fetch quotidien de quelques centaines d'offres).
À remplacer par une écriture en masse (`UPDATE ... FROM (VALUES ...)` ou
`bulk_update_mappings`) avant tout run de backfill à grande échelle.

---

## Déploiement frontend Container App (feature/frontend-web-deployment, PR #191) — suites identifiées en review

### [optional] Dédier une identité managée au frontend plutôt que réutiliser celle des Container App Jobs
`envs/dev/frontend.tf` câble `identity_ids`/`registry_identity` sur `data.azurerm_user_assigned_identity.caj`
(`id-jf-dev-frc-caj`), la même UAMI que les Container App Jobs et le webapp. Ça fonctionne
aujourd'hui car la seule permission pertinente pour le frontend est le pull ACR, partagée par
tous les conteneurs — mais le frontend n'appelle directement aucun service Azure (contrairement
au webapp ou aux jobs), donc il hérite implicitement de toute permission future accordée à cette
UAMI sans en avoir besoin. Un couplage silencieux : si `id-jf-dev-frc-caj` gagne un rôle
supplémentaire pour un besoin backend, le frontend l'obtient aussi sans qu'aucune ligne de code
ne le mentionne explicitement.

**Solution cible :** provisionner une UAMI dédiée au frontend (pull ACR uniquement), ou a minima
documenter explicitement le partage intentionnel si une identité dédiée est jugée disproportionnée
pour un portfolio project — un commentaire WHY a été ajouté dans `frontend.tf` en attendant.
**Fichier :** `envs/dev/frontend.tf` (et un nouveau module identité si une UAMI dédiée est retenue).
