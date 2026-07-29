# ADR-001 : Moteur de base de données pour le data layer de job-finder

**Statut :** Accepté
**Date :** 2026-05-01
**Décideur :** Vincent Boutin

---

## Contexte

Le projet job-finder nécessite un data layer capable de stocker des offres d'emploi structurées, des profils utilisateurs, et des vecteurs d'embeddings pour la recherche sémantique. La stack cible est Azure (France Central) + AKS. Le budget est modéré (~20 €/mois), il n'y a pas d'expérience préalable avec les bases de données relationnelles ou NoSQL, et le projet vise une mise en production réelle (pas seulement une démo).

---

## Décision

**PostgreSQL via Azure Database for PostgreSQL Flexible Server**, avec Azure AI Search pour la recherche vectorielle.

---

## Options considérées

### Option A : PostgreSQL Flexible Server

| Dimension | Évaluation |
|---|---|
| Coût | ~13 €/mois (SKU Burstable B1ms) — dans le budget |
| Complexité | Faible — SQL standard, bien documenté |
| Scalabilité | Suffisante pour une production réelle à l'échelle d'un projet solo |
| Familiarité | Aucune, mais SQL est la courbe d'apprentissage la plus douce |
| Intégration Azure | Native — VNet injection (subnet délégué), RBAC, Key Vault pour les credentials |

**Pour :** coût maîtrisé, SQL universel et transférable, extension `pgvector` disponible si besoin, pas de vendor lock-in fort, fonctionne nativement avec AKS via connection string standard.

**Contre :** nécessite de gérer les migrations de schéma, moins adapté si les données deviennent vraiment hétérogènes à grande échelle.

---

### Option B : Azure Cosmos DB (NoSQL)

| Dimension | Évaluation |
|---|---|
| Coût | ~25 €/mois minimum en serverless, peut monter vite — hors budget |
| Complexité | Haute — partition keys, RU/s, niveaux de cohérence à maîtriser |
| Scalabilité | Excellente, conçu pour millions d'utilisateurs simultanés |
| Familiarité | Aucune + concepts spécifiques à Cosmos = double apprentissage |
| Intégration Azure | Native, mais surpuissant pour ce cas d'usage |

**Pour :** scalabilité mondiale, multi-modèle, latence très faible.

**Contre :** surdimensionné pour un projet solo en production, coût imprévisible, courbe d'apprentissage élevée sans expérience préalable.

---

## Analyse des compromis

CosmosDB brille à très grande échelle et en distribution géographique — des contraintes que job-finder n'a pas aujourd'hui. Son coût et sa complexité sont des surcoûts injustifiés à ce stade. PostgreSQL couvre 100 % des besoins actuels (données structurées, relations, embeddings via pgvector), reste dans le budget, et sa connaissance est directement réutilisable sur n'importe quel projet futur. La recherche vectorielle lourde est déléguée à Azure AI Search, qui est prévu dans la roadmap et conçu pour ça.

---

## Conséquences

- ✅ Budget maîtrisé dès le départ
- ✅ SQL appris une fois, utile partout
- ✅ Architecture claire : PostgreSQL pour les données structurées, Blob Storage pour les fichiers, Azure AI Search pour les vecteurs
- ⚠️ Les migrations de schéma devront être gérées proprement (à intégrer dans le workflow Terraform + CI/CD)
- ⚠️ Si le projet devait passer à des millions d'utilisateurs, une migration vers Cosmos serait à envisager

---

## Actions suivantes

- [ ] Créer le module Terraform `data/postgresql` dans `JobFinder/Terraform/modules/data/`
- [ ] Provisionner le Flexible Server en dev (SKU Burstable B1ms)
- [ ] Configurer l'accès réseau privé (VNet injection dans un subnet délégué + zone DNS privée) + credentials dans Key Vault
- [ ] Ouvrir une PR feature/data-postgresql-dev → review par le reviewer agent
