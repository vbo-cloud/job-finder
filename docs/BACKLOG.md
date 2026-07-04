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

### [M4 bis — PR 8] Agent cv-review — analyse CV vs offres (forces/faiblesses/suggestions)

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

### [optional] Sortir les GeoJSON du dépôt Git
`public/geo/` pèse ~38 Mo (dont 29 Mo de contours HD) versionnés dans Git — le clone
s'alourdit à chaque régénération du dataset. Pistes : Git LFS, ou hébergement sur le
Storage Account existant (CDN) avec téléchargement au build (`scripts/build-communes-geo.mjs`
tourne déjà en une commande ; risque : disponibilité des sources Etalab au moment du build).
