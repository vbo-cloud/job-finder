# Récapitulatif des ADRs — job-finder

Toutes les décisions d'architecture du projet, dans l'ordre de prise de décision.

---

## Vue d'ensemble

| ADR | Titre | Décision | Statut |
|-----|-------|----------|--------|
| [ADR-001](ADR-001-data-layer-database.md) | Base de données du data layer | PostgreSQL Flexible Server (B1ms) | Accepté |
| [ADR-002](ADR-002-compute-platform.md) | Plateforme de compute | Azure Container Apps (définitif — AKS abandonné) | Accepté |
| [ADR-003](ADR-003-vector-search.md) | Moteur de recherche vectorielle | pgvector dans PostgreSQL | Accepté |
| [ADR-004](ADR-004-schema-migration.md) | Outil de migration de schéma | Alembic + SQLAlchemy | Accepté |
| [ADR-005](ADR-005-container-registry.md) | Container Registry | Azure Container Registry (Basic) | Accepté |
| [ADR-006](ADR-006-llm-provider.md) | LLM Provider | Azure OpenAI (GPT-4o-mini) | Accepté |
| [ADR-007](ADR-007-agent-orchestration.md) | Orchestration des agents | Azure Service Bus | Accepté |
| [ADR-008](ADR-008-embedding-model.md) | Modèle d'embedding | text-embedding-3-small | Accepté |
| [ADR-009](ADR-009-api-framework.md) | Framework API | FastAPI | Accepté |
| [ADR-010](ADR-010-job-offer-collection.md) | Collecte des offres d'emploi | France Travail API | Accepté |
| [ADR-011](ADR-011-user-authentication.md) | Authentification utilisateur | Microsoft Entra External ID | Accepté |
| [ADR-012](ADR-012-monitoring.md) | Monitoring et observabilité | Azure Monitor + Application Insights | Accepté |
| [ADR-013](ADR-013-git-terraform-cicd.md) | Stratégie Git, Terraform et CI/CD | Release branch + composants + staging éphémère | Accepté |
| [ADR-015](ADR-015-frontend-framework.md) | Framework frontend | Next.js 14 — App Router, TypeScript, Tailwind CSS, Framer Motion, MSAL | Accepté |
| [ADR-016](ADR-016-testing-strategy.md) | Stratégie de test | pytest unitaire ciblé — e2e différé v1.1.0 | Accepté |
| [ADR-017](ADR-017-monitoring-alerting.md) | Monitoring et alerting | Application Insights + KQL + 6 alertes Azure Monitor | Accepté |

---

## Architecture cible résumée

```
┌─────────────────────────────────────────────────────────────┐
│                        job-finder                           │
├─────────────────────────────────────────────────────────────┤
│  Frontend (Next.js 14 — Container App)                      │
│  └── upload CV / bibliothèque / offres / profil             │
├─────────────────────────────────────────────────────────────┤
│  API (FastAPI + uvicorn — Container App)                    │
│  └── /cv/upload  /matches  /profile  /cv/{id}/review        │
├─────────────────────────────────────────────────────────────┤
│  Agents (Python — Container App Jobs)                       │
│  ├── offer-fetching  → offer-ready (Service Bus)            │
│  ├── cv-analysis     → offer-ready (Service Bus)            │
│  ├── matching        → match-ready (Service Bus)            │
│  ├── cv-review       ← match-ready (Service Bus)            │
│  └── cleanup         (timer quotidien)                      │
├─────────────────────────────────────────────────────────────┤
│  IA                                                         │
│  ├── Azure OpenAI GPT-4o-mini (analyse, scoring, reco)      │
│  └── Azure OpenAI text-embedding-3-small (vectorisation)    │
├─────────────────────────────────────────────────────────────┤
│  Data                                                       │
│  ├── PostgreSQL Flexible Server                             │
│  │   ├── Données structurées (offres, CVs, users)           │
│  │   └── pgvector — embeddings 1536 dims (HNSW)             │
│  └── Azure Blob Storage (fichiers CVs, offres brutes)       │
├─────────────────────────────────────────────────────────────┤
│  Infrastructure                                             │
│  ├── Compute   : Azure Container Apps (Container App Jobs + Container Apps) │
│  ├── Images    : Azure Container Registry (Basic)           │
│  ├── Messaging : Azure Service Bus                          │
│  ├── Secrets   : Azure Key Vault                            │
│  └── Région    : francecentral                              │
├─────────────────────────────────────────────────────────────┤
│  CI/CD & IaC                                                │
│  ├── Terraform (modules : network, compute, data, ai, msg)  │
│  ├── GitHub Actions (Plan sur PR, Apply sur merge)          │
│  ├── Migrations : Alembic (alembic upgrade head au boot)    │
│  └── Reviewer  : Claude API via reviewerAgent.yml           │
└─────────────────────────────────────────────────────────────┘
```

---

## Budget mensuel estimé (v0.5.0 — dev)

| Service | Coût estimé |
|---------|-------------|
| PostgreSQL Flexible Server (B1ms) | ~13 €/mois |
| Azure Container Registry (Basic) | ~5 €/mois |
| Azure Service Bus (Standard) | ~10 €/mois |
| Azure OpenAI | Pay-per-token (~5-15 € en dev) |
| Azure Container Apps (scale to zero) | ~0 € |
| **Total actuel** | **~33-43 €/mois** |

---

## Stack technique complète

| Couche | Technologie | ADR |
|--------|-------------|-----|
| Cloud | Azure — francecentral | — |
| IaC | Terraform ~> 4.0 (azurerm) | — |
| CI/CD | GitHub Actions + OIDC | — |
| Compute | Azure Container Apps + Container App Jobs | ADR-002 |
| Registry | Azure Container Registry (Basic) | ADR-005 |
| Base de données | PostgreSQL Flexible Server (B1ms) | ADR-001 |
| Recherche vectorielle | pgvector (extension PostgreSQL) | ADR-003 |
| Migrations | Alembic + SQLAlchemy | ADR-004 |
| Messaging | Azure Service Bus (Standard) | ADR-007 |
| LLM | Azure OpenAI GPT-4o-mini | ADR-006 |
| Embeddings | Azure OpenAI text-embedding-3-small | ADR-008 |
| API | FastAPI + uvicorn | ADR-009 |
| Source offres | France Travail API (REST, OAuth2) | ADR-010 |
| Authentification | Microsoft Entra External ID | ADR-011 |
| Monitoring | Azure Monitor + Application Insights | ADR-012, ADR-017 |
| Frontend | Next.js 14 — TypeScript, Tailwind, Framer Motion | ADR-015 |
| Tests | pytest unitaire (cleanup, auth, CV upload) | ADR-016 |
| Reviewer CI | Anthropic API (Claude Sonnet) | — |

---

## État du projet

**Version actuelle :** v0.5.0 (2026-06-02)

- ✅ M0 — Fondations Azure, CI/CD, reviewer agent
- ✅ M1 — Data layer (PostgreSQL, Service Bus, OpenAI, Application Insights)
- ✅ M2 — Agents Python (offer-fetching, matching, cleanup)
- ✅ M3 — FastAPI webapp, Entra External ID, Container App, pipeline CI/CD
- 🎯 M4 — Frontend Next.js + agent cv-analysis + agent cv-review (en cours)
