# Roadmap — job-finder

_Mis à jour : 2026-05-18_

---

## Vue d'ensemble

```
M0 ✅ → M1 ✅ → M2 🎯 → M3 🔮 → Refacto 🔧 → M4 🔮 → M5 🔮 → M6 🔮
Infra    Data    Agents   API     Git+Terraform  AKS    Frontend  Optim
Done    Done    En cours ~5 j     Avant prod     ~5 j    ~5 j    ongoing
```

**Rythme :** 10h/jour
**Durée totale estimée :** 4 à 6 semaines
**Coût M1 :** ~20-30 €/mois | **Coût M3+ :** ~55-75 €/mois (avec AKS minimal)

---

## Milestone 0 — Fondations Azure ✅ TERMINÉ

> _Base infra cloud, CI/CD, reviewer agent_

- [x] Landing Zone : Resource Groups, RBAC, Azure Policy
- [x] Réseau : VNet, Subnets, NSG (francecentral)
- [x] Terraform : remote state (stjftfstatefrc), modules (rg/network/compute/data)
- [x] CI/CD : GitHub Actions + OIDC (4 federated credentials configurés)
- [x] Pipeline : `terraform plan` sur PR, `terraform apply` sur merge
- [x] Reviewer agent : Claude Sonnet (APPROVE / REQUEST_CHANGES automatique)
- [x] ADRs 001-013 : toutes les décisions d'architecture documentées

---

## Milestone 1 — Data Layer + Services IA ✅ TERMINÉ

> _Stack données et IA provisionnée sur Azure. Structure Terraform actuelle conservée (lz-dev, dev, lz-prod, prod) — le refactoring viendra après._
> **Durée estimée : 3 à 5 jours**
> **Coût : ~20-30 €/mois**

### Jour 1 — Config Git + Key Vault

**Matin (~3h)**
- [ ] Branch protection rules sur `main` et `dev` (via Claude Code + `gh api`)
- [ ] Commit des `.terraform.lock.hcl` manquants (lz_prod, prod) — feature branch → PR → dev

**Après-midi (~7h)**
- [ ] `modules/keyvault/` — `azurerm_key_vault` (purge_protection=true, RBAC)
- [ ] Stocker les premiers secrets : connection strings, API keys
- [ ] PR ouverte, CI passe, merge

### Jour 2 — PostgreSQL + Blob Storage

- [ ] `modules/data/postgresql.tf` — Flexible Server B1ms (francecentral)
- [ ] Extension pgvector activée — `vector(1536)` pour les embeddings
- [ ] Alembic configuré (`alembic upgrade head` au boot du container)
- [ ] `modules/data/blob_storage.tf` — containers `cvs` et `offers-raw`
- [ ] Accès via managed identity (pas de connection string)

### Jour 3 — Service Bus + Azure OpenAI

- [ ] `modules/messaging/servicebus.tf` — namespace Basic → Standard
- [ ] Queues `offers-collected`, `offers-analyzed`, `matches-ready`
- [ ] `modules/ai/openai.tf` — ressource cognitive account (francecentral)
- [ ] Déploiement `gpt-4o-mini` + `text-embedding-3-small`

### Jour 4 — Monitoring + Validation

- [ ] `modules/monitoring/application_insights.tf`
- [ ] Log Analytics Workspace + Application Insights
- [ ] Alertes : error rate API >5%, dead-letter >0, CPU PostgreSQL >80%
- [ ] `terraform plan` passe sur les 4 environnements
- [ ] PR mergée, `terraform apply` exécuté en CI
- [ ] Connexion PostgreSQL vérifiée depuis un script Python local
- [ ] Premier embedding généré via Azure OpenAI (test manuel)
- [ ] DOC.md mis à jour

---

## Transition M3 → prod — Refactoring Git + Terraform 🔧

> _Restructuration Terraform par composant et mise en place du staging éphémère, avant la mise en production réelle. Délibérément décalé après M3 : le refacto a plus de valeur une fois que l'application est fonctionnelle et que les dépendances inter-composants sont connues._
> **Durée estimée : 1 à 2 jours**
> **Voir ADR-013 pour le détail complet**

### Pourquoi ici et pas avant

À ce stade, les modules Terraform de M1 sont stables et les ressources existent en dev. Refactorer avant M2 évite de migrer des agents, une API et un cluster AKS plus tard — ce serait bien plus coûteux. Et contrairement à maintenant, la structure n'a encore aucune dépendance inter-composants à démêler.

### Nouvelle structure Terraform

```
envs/
├── dev/
│   ├── landing-zone/    → state: dev-landing-zone.tfstate
│   ├── network/         → state: dev-network.tfstate
│   ├── data/            → state: dev-data.tfstate
│   ├── ai/              → state: dev-ai.tfstate
│   ├── messaging/       → state: dev-messaging.tfstate
│   ├── compute/         → state: dev-compute.tfstate
│   └── monitoring/      → state: dev-monitoring.tfstate
├── staging/             → même structure — ÉPHÉMÈRE
└── prod/
    └── ...              → même structure
```

### Nouveau Git flow

```
feature/* → dev → release/vX.X.X → [staging éphémère] → main (tag vX.X.X)
```

- `main` ne reçoit que des releases validées par un environnement miroir de prod
- `staging/` est créé automatiquement à l'ouverture d'une `release/*` et détruit après merge

### Tâches

- [ ] Créer la structure de dossiers par composant dans `dev/`, `staging/`, `prod/`
- [ ] Déplacer le code Terraform existant dans les bons composants
- [ ] Migrer les state files (`terraform state mv` si nécessaire)
- [ ] Ajouter les `outputs.tf` dans `landing-zone/` et `network/`
- [ ] Câbler les `terraform_remote_state` dans les composants dépendants
- [ ] Réécrire `terraformPlan.yml` : path filters par composant + `needs:` ordering
- [ ] Créer `terraformStaging.yml` : apply sur `release/**`, destroy sur merge vers `main`
- [ ] Créer `envs/staging/` (même structure que `prod/`, tfvars staging)
- [ ] Mettre à jour les branch protection rules (`release/*`, checks staging sur `main`)
- [ ] DOC.md mis à jour

---

## Milestone 2 — Agents Python 🎯 EN COURS

> _Cœur métier : fetch, analyse LLM, matching vectoriel, cv-review_
> **Durée estimée : 7 à 10 jours**
> **Coût : ~25-35 €/mois** (tokens OpenAI en développement)

### Architecture cible M2

```
Onboarding utilisateur
  → sélection catégories métier (UI lisible, pas de codes ROME exposés)
  → mapping interne catégorie → codes ROME
  → stockage dans user_profiles.rome_codes

Upload CV (M3 — web app)
  → extraction texte PDF (pdfplumber)
  → embedding (text-embedding-3-small) → cvs table
  → CV-analysis agent (GPT-4o-mini)
      → extrait codes ROME + compétences
      → affine user_profiles.rome_codes
  → matching immédiat contre offres existantes en base

GitHub Actions cron (2x/jour — 12:00 et 20:00 UTC)
  → lit l'union des rome_codes depuis user_profiles
  → fetch France Travail (OAuth2, pagination) pour ces codes
  → embedding batch inline (text-embedding-3-small)
  → stockage dans offers table (rome_code inclus)
  → post message offer-ready {"run_date": "...", "count": N}

job-matching (Container App Job, queue: offer-ready)
  → pour chaque CV en base :
      filtre offres WHERE rome_code = ANY(user.rome_codes)
      + vector search (cosine similarity pgvector)
      + GPT-4o-mini : score + explication par offre
  → stockage dans matches table
  → post message match-ready

job-cv-review (Container App Job, queue: match-ready) ← DERNIÈRE FEATURE
  → analyse CV vs top-3 offres matchées
  → GPT-4o-mini : gaps de compétences + suggestions personnalisées
  → notification utilisateur
```

### Schéma DB — nouveautés M2

```
user_profiles (nouveau)
  user_id        UUID PK
  rome_codes     TEXT[]     -- ex: ['M1805', 'M1802']
  job_categories TEXT[]     -- ex: ['Développement', 'Data']
  location       TEXT
  contract_types TEXT[]     -- CDI, CDD, freelance
  created_at     TIMESTAMPTZ

offers (existant — colonne à ajouter)
  rome_code      TEXT       -- pour filtrage au matching
```

### Jour 1 — Fondations Python ✅ TERMINÉ

- [x] `shared/models.py` — tables `offers`, `cvs`, `matches`
- [x] `shared/db.py`, `shared/bus.py`, `shared/embedder.py`
- [x] Migrations Alembic — schéma initial
- [x] Squelettes agents

### Jour 2 — Schéma DB M2 + nettoyage Terraform

- [x] Terraform : suppression `job-offer-fetching` et `job-embedding-offer`
- [x] Terraform : `job-matching` rebranchée sur `offer-ready`
- [ ] Migration Alembic : table `user_profiles` + colonne `rome_code` sur `offers`
- [ ] `shared/models.py` : modèle `UserProfile`

### Jours 3-4 — GitHub Actions fetch + CV-analysis agent

- [ ] `.github/workflows/offerFetch.yml` : cron 12:00/20:00 UTC
- [ ] `scripts/fetch_offers.py` : lit ROME codes depuis DB → France Travail OAuth2 → pagination → embed batch → stocke → post `offer-ready`
- [ ] Credentials France Travail dans Key Vault (`ft-client-id`, `ft-client-secret`)
- [ ] Agent CV-analysis : GPT-4o-mini → extraction ROME codes + compétences → `user_profiles`

### Jours 5-6 — Agent Matching

- [ ] `agents/matching/main.py` : consomme `offer-ready`
- [ ] Filtre offres par `rome_codes` du profil utilisateur
- [ ] Vector search pgvector (cosine similarity) → top-N
- [ ] GPT-4o-mini : score + explication par offre
- [ ] Stockage dans `matches` + post `match-ready`
- [ ] Dockerisation + déploiement image réelle sur Container App Job

### Jour 7 — Validation pipeline end-to-end

- [ ] Seed script : crée un profil test avec rome_codes → déclenche le pipeline complet
- [ ] Pipeline complet : fetch → matching → match-ready
- [ ] Traces visibles dans Application Insights
- [ ] Qualité du matching validée manuellement sur 10 cas

### Jours 8-9 — Agent CV-review ← DERNIÈRE FEATURE

- [ ] `agents/cv_review/main.py` : consomme `match-ready`
- [ ] Analyse CV vs top-3 offres matchées
- [ ] GPT-4o-mini : gaps de compétences + suggestions personnalisées
- [ ] Notification utilisateur (email ou push — à définir en M3)
- [ ] Dockerisation + déploiement

### Jour 10 — Release M2

- [ ] Test end-to-end avec profils réels
- [ ] Première release `release/v0.3.0` → `main` → tag `v0.3.0`
- [ ] JOURNAL.md mis à jour

---

## Milestone 3 — API FastAPI + Migration AKS 🔮

> _API publique + passage en production sur Kubernetes_
> **Durée estimée : 4 à 6 jours**
> **Coût : ~55-75 €/mois** (AKS 1-2 nœuds Standard_B2s)

### Jours 1-2 — API FastAPI

- [ ] Structure : `app/main.py`, `app/routers/`, `app/models/`, `app/schemas/`
- [ ] `GET /jobs` — liste des offres avec filtres (localisation, contrat, salaire)
- [ ] `POST /match` — soumet un CV, retourne les offres matchées
- [ ] `GET /recommend/{user_id}` — recommandations personnalisées avec explications
- [ ] Documentation Swagger auto sur `/docs` (showcase portfolio)
- [ ] Dockerisation : `uvicorn app.main:app --host 0.0.0.0 --port 8000`

### Jour 3 — Azure AD B2C

- [ ] Créer tenant B2C (West Europe)
- [ ] Configurer user flow "Sign up and sign in"
- [ ] Login social : Google + Microsoft
- [ ] Enregistrer l'application FastAPI dans B2C
- [ ] Validation JWT avec `python-jose` dans FastAPI

### Jours 4-5 — Migration AKS

- [ ] `dev/compute/aks.tf` — cluster AKS (1 nœud Standard_B2s)
- [ ] Déploiement des 4 agents + API en pods Kubernetes
- [ ] Ingress Controller + TLS (cert-manager)
- [ ] Managed Identity pour accès aux ressources Azure
- [ ] Autoscaling HPA sur l'API et les agents

### Jour 6 — Validation M3

- [ ] API accessible publiquement via HTTPS
- [ ] Authentification B2C fonctionnelle (signup + login)
- [ ] `/docs` Swagger accessible
- [ ] Pipeline complet sur AKS : collecte → recommandation
- [ ] Release `release/v1.0.0` → staging → `main` → tag `v1.0.0`
- [ ] DOC.md mis à jour

---

## Milestone 4 — Frontend 🔮 (optionnel)

> _Interface utilisateur pour les candidats_
> **Durée estimée : 4 à 6 jours**
> **Coût : +5-10 €/mois** (Static Web App ou Container)

### Jours 1-2 — Setup + Auth

- [ ] Choix framework (ADR-014 à rédiger) — Next.js recommandé
- [ ] Page d'accueil + login B2C
- [ ] Upload CV (PDF → Blob Storage)

### Jours 3-5 — Dashboard

- [ ] Liste des offres recommandées + score matching + explication IA
- [ ] Filtres : localisation, type de contrat, salaire
- [ ] Page profil utilisateur

### Jour 6 — Deploy

- [ ] Azure Static Web Apps (Next.js export) ou Container Apps
- [ ] Tests end-to-end (Playwright ou Cypress)
- [ ] Release `release/v1.1.0` → staging → `main` → tag `v1.1.0`
- [ ] DOC.md mis à jour

---

## Milestone 5 — Optimisation 🔮

> _Affinage, coûts, performance_
> **Durée estimée : ongoing**

- [ ] Cache des embeddings fréquents (ADR-015 — Redis vs cache applicatif)
- [ ] Optimisation prompt engineering (meilleure extraction GPT-4o-mini)
- [ ] Compression vecteurs pgvector (256 dims si qualité suffisante → -83% stockage)
- [ ] Dashboard coûts Azure OpenAI (tokens/jour, coût/recommandation)
- [ ] Alertes Monitor affinées selon les patterns réels de production

---

## Planning global (10h/jour)

| Phase | Durée estimée | Semaine |
|---|---|---|
| M0 | ✅ Terminé | — |
| M1 — Data Layer + IA | 3-5 jours | Semaine 1 |
| Refacto Git + Terraform (ADR-013) | 1-2 jours | Semaine 1-2 |
| M2 — Agents Python | 7-10 jours | Semaines 2-3 |
| M3 — API + AKS | 4-6 jours | Semaines 3-4 |
| M4 — Frontend | 4-6 jours | Semaine 4-5 |
| M5 — Optimisation | ongoing | Semaine 5+ |
| **Total M1→M4** | **~20-29 jours** | **~4-6 semaines** |

---

## Budget mensuel par phase

| Phase | Compute | PostgreSQL | ACR | OpenAI | Service Bus | Monitoring | **Total** |
|---|---|---|---|---|---|---|---|
| **M1** | Container Apps ~0€ | ~13€ | ~5€ | ~2€ dev | ~0€ Basic | ~0€ | **~20-30€** |
| **M2** | Container Apps ~0€ | ~13€ | ~5€ | ~5-15€ | ~10€ Standard | ~0€ | **~33-43€** |
| **M3+** | AKS 1 nœud ~17-35€ | ~13€ | ~5€ | ~10-20€ | ~10€ | ~2€ | **~55-75€** |

> **Note :** Le control plane AKS est gratuit. Le coût vient uniquement des VMs worker nodes. Avec 1 nœud `Standard_B2s` (~17€/mois), AKS reste abordable pour un portfolio.

---

## Prochaine action

**Aujourd'hui (Jour 1 de M1) :** configurer les branch protection rules sur `main` et `dev` via Claude Code, puis ouvrir la PR des `.terraform.lock.hcl` manquants. Ensuite : module Key Vault.
