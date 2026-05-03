# ADR-003 : Moteur de recherche vectorielle pour job-finder

**Statut :** Proposé
**Date :** 2026-05-01
**Décideur :** Vincent Boutin

---

## Contexte

La couche IA de job-finder nécessite de vectoriser des offres d'emploi et des CVs (via un modèle d'embedding) puis d'effectuer des recherches de similarité pour le matching. Deux approches s'opposent : ajouter l'extension `pgvector` à PostgreSQL (déjà choisi en ADR-001), ou déployer Azure AI Search comme service dédié. La décision impacte directement le coût, la complexité de l'infra et la roadmap IA.

---

## Décision

**pgvector dans PostgreSQL**, avec une migration planifiée vers Azure AI Search si le volume ou la complexité de recherche le justifie à terme.

---

## Options considérées

### Option A : pgvector (extension PostgreSQL)

| Dimension | Évaluation |
|---|---|
| Coût | ~0 € supplémentaire — inclus dans le Flexible Server déjà provisionné |
| Complexité | Faible — une extension à activer, SQL standard pour les requêtes |
| Scalabilité | Bonne jusqu'à ~1M de vecteurs avec indexation HNSW |
| Intégration | Native — même connexion PostgreSQL, même Terraform, même stack |
| Valeur portfolio | Bonne — pgvector est très utilisé dans les stacks IA modernes |

**Pour :** gratuit, zéro infra supplémentaire, activation en une ligne (`CREATE EXTENSION vector`), supporte cosine similarity / L2 / inner product, compatible avec les frameworks Python IA (LangChain, LlamaIndex), recherche hybride possible en combinant avec le full-text search natif PostgreSQL.

**Contre :** moins performant qu'Azure AI Search sur des volumes massifs (>10M vecteurs), pas de faceting ni de filtrage avancé out-of-the-box, reranking plus limité.

---

### Option B : Azure AI Search

| Dimension | Évaluation |
|---|---|
| Coût | ~75 €/mois (tier Basic, le minimum viable) — hors budget à ce stade |
| Complexité | Haute — service séparé, index à définir, SDK spécifique, Terraform module dédié |
| Scalabilité | Excellente — conçu pour des millions de documents, RAG enterprise-grade |
| Intégration | Azure native, mais couche supplémentaire dans l'architecture |
| Valeur portfolio | Très bonne — service phare Azure pour les architectures RAG |

**Pour :** recherche hybride (texte + vecteurs) optimisée, reranking sémantique intégré, filtres et facettes avancés, latence très faible à grande échelle, intégration native Azure OpenAI.

**Contre :** coût ~75-250 €/mois selon le tier — disproportionné pour un volume de quelques milliers d'offres d'emploi. Ajoute une dépendance infra à gérer dès la Milestone 1 alors que la priorité est de faire fonctionner la couche data.

---

## Analyse des compromis

Pour un volume réaliste de job-finder en production initiale — quelques milliers d'offres d'emploi, quelques centaines de CVs — pgvector couvre 100 % des besoins de similarité vectorielle avec une indexation HNSW qui maintient des performances sub-100ms. Azure AI Search n'apporte une vraie valeur différenciante qu'au-delà de 100K documents ou quand le reranking sémantique avancé devient critique.

Le coût est le facteur décisif : 75 €/mois pour Azure AI Search représente 3-4x le coût du Flexible Server PostgreSQL, pour un gain qui ne sera perceptible qu'à une échelle que le projet n'atteindra pas en Milestone 1 ou 2.

**Stratégie en deux temps :**
1. **Maintenant** → pgvector dans PostgreSQL existant, zéro coût, démarrage immédiat
2. **Si et quand** le volume dépasse ~500K vecteurs ou que la qualité de recherche devient insuffisante → migration vers Azure AI Search. Les embeddings stockés dans PostgreSQL sont facilement ré-indexables via un script de migration.

---

## Conséquences

- ✅ Zéro coût supplémentaire — pgvector est inclus dans Azure Database for PostgreSQL Flexible Server
- ✅ Architecture simplifiée — une seule base de données pour les données structurées et les vecteurs
- ✅ Activation immédiate : `CREATE EXTENSION vector` + colonne `embedding vector(1536)` sur les tables
- ✅ Compatible LangChain, LlamaIndex, et la plupart des frameworks Python IA
- ⚠️ La recherche hybride (texte + vecteurs) nécessite d'écrire du SQL combinant `tsvector` et opérateurs pgvector — plus de code qu'avec Azure AI Search
- ⚠️ Si Azure AI Search est ajouté plus tard, prévoir un module Terraform `search/azure-ai-search` et un script de ré-indexation

---

## Actions suivantes

- [ ] Activer l'extension sur le Flexible Server : `CREATE EXTENSION IF NOT EXISTS vector`
- [ ] Ajouter une colonne `embedding vector(1536)` aux tables `job_offers` et `user_profiles`
- [ ] Créer un index HNSW : `CREATE INDEX ON job_offers USING hnsw (embedding vector_cosine_ops)`
- [ ] Documenter la décision dans `DOC.md` lors de la PR qui implémente le schéma initial
