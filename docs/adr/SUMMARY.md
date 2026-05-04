# Récapitulatif des ADRs — job-finder

Toutes les décisions d'architecture du projet, dans l'ordre de prise de décision.

---

## Vue d'ensemble

| ADR | Titre | Décision | Statut |
|-----|-------|----------|--------|
| [ADR-001](ADR-001-data-layer-database.md) | Base de données du data layer | PostgreSQL Flexible Server (B1ms) | Proposé |
| [ADR-002](ADR-002-compute-platform.md) | Plateforme de compute | Container Apps (M1) → AKS (M3) | Proposé |
| [ADR-003](ADR-003-vector-search.md) | Moteur de recherche vectorielle | pgvector dans PostgreSQL | Proposé |
| [ADR-004](ADR-004-schema-migration.md) | Outil de migration de schéma | Alembic + SQLAlchemy | Proposé |
| [ADR-005](ADR-005-container-registry.md) | Container Registry | Azure Container Registry (Basic) | Proposé |
| [ADR-006](ADR-006-llm-provider.md) | LLM Provider | Azure OpenAI (GPT-4o-mini) | Proposé |
| [ADR-007](ADR-007-agent-orchestration.md) | Orchestration des agents | Azure Service Bus | Proposé |
| [ADR-008](ADR-008-embedding-model.md) | Modèle d'embedding | text-embedding-3-small | Proposé |
| [ADR-009](ADR-009-api-framework.md) | Framework API | FastAPI | Proposé |
| [ADR-010](ADR-010-job-offer-collection.md) | Collecte des offres d'emploi | France Travail API | Proposé |
| [ADR-011](ADR-011-user-authentication.md) | Authentification utilisateur | Azure AD B2C | Proposé |
| [ADR-012](ADR-012-monitoring.md) | Monitoring et observabilité | Azure Monitor + Application Insights | Proposé |
| [ADR-013](ADR-013-git-terraform-cicd.md) | Stratégie Git, Terraform et CI/CD | Release branch + composants + staging éphémère | Proposé |

---

## Architecture cible résumée

```
┌─────────────────────────────────────────────────────────────┐
│                        job-finder                           │
├─────────────────────────────────────────────────────────────┤
│  API (FastAPI + uvicorn)                                    │
│  └── /jobs  /match  /recommend                              │
├─────────────────────────────────────────────────────────────┤
│  Agents (Python)                                            │
│  ├── Agent Collecte  →┐                                     │
│  ├── Agent Analyse   ←┘ Azure Service Bus                   │
│  ├── Agent Matching  ←──────────────────                    │
│  └── Agent Recommandations                                  │
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
│  ├── Compute   : Container Apps (M1) → AKS (M3)             │
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

## Budget mensuel estimé (Milestone 1)

| Service | Coût estimé |
|---------|-------------|
| PostgreSQL Flexible Server (B1ms) | ~13 €/mois |
| Azure Container Registry (Basic) | ~5 €/mois |
| Azure Service Bus (Basic) | ~0,05 €/million de messages |
| Azure OpenAI | Pay-per-token (~quelques € en dev) |
| Azure Container Apps | ~0 € (scale to zero) |
| **Total Milestone 1** | **~20-25 €/mois** |

---

## Stack technique complète

| Couche | Technologie | ADR |
|--------|-------------|-----|
| Cloud | Azure — francecentral | — |
| IaC | Terraform ~> 3.0 (azurerm) | — |
| CI/CD | GitHub Actions + OIDC | — |
| Compute (M1) | Azure Container Apps | ADR-002 |
| Compute (M3) | AKS (Kubernetes) | ADR-002 |
| Registry | Azure Container Registry | ADR-005 |
| Base de données | PostgreSQL Flexible Server | ADR-001 |
| Recherche vectorielle | pgvector (extension PostgreSQL) | ADR-003 |
| Migrations | Alembic + SQLAlchemy | ADR-004 |
| Messaging | Azure Service Bus | ADR-007 |
| LLM | Azure OpenAI GPT-4o-mini | ADR-006 |
| Embeddings | Azure OpenAI text-embedding-3-small | ADR-008 |
| API | FastAPI + uvicorn | ADR-009 |
| Source offres | France Travail API (REST, OAuth2) | ADR-010 |
| Authentification | Azure AD B2C | ADR-011 |
| Monitoring | Azure Monitor + Application Insights | ADR-012 |
| Reviewer CI | Anthropic API (Claude Sonnet) | — |

---

## Prochaines décisions à documenter

- ADR-014 : Stratégie de cache (Redis vs cache applicatif) — mise en cache des embeddings et des résultats de matching fréquents
- ADR-015 : Frontend (Next.js vs React SPA vs serveur-rendu) — interface candidat pour upload CV et consultation des recommandations
- ADR-016 : Stratégie de test (unit, integration, e2e) — couverture minimale et outils pour un projet solo
