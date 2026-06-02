# ADR-008 : Modèle d'embedding pour la vectorisation des offres et CVs

**Statut :** Accepté
**Date :** 2026-05-01
**Décideur :** Vincent Boutin

---

## Contexte

Le système de matching de job-finder repose sur la conversion des offres d'emploi et des CVs en vecteurs numériques (embeddings) qui seront stockés dans PostgreSQL via pgvector (ADR-003). Le choix du modèle d'embedding détermine la qualité du matching, le coût à l'échelle, et la dimension des vecteurs à stocker. Les modèles disponibles via Azure OpenAI (ADR-006) sont : `text-embedding-3-small`, `text-embedding-3-large`, et `text-embedding-ada-002` (legacy).

---

## Décision

**`text-embedding-3-small`** via Azure OpenAI, avec vecteurs à 1536 dimensions.

---

## Options considérées

### Option A : text-embedding-3-small

| Dimension | Évaluation |
|---|---|
| Coût | ~0,02 $/million de tokens — le moins cher des trois |
| Qualité | Très bonne — meilleure que ada-002 sur tous les benchmarks |
| Dimensions | 1536 (configurable de 256 à 1536) |
| Latence | Faible — modèle léger |
| Compatibilité pgvector | ✅ — `vector(1536)` déjà planifié dans ADR-003 |

**Pour :** excellent rapport qualité/coût, surpasse ada-002 malgré un prix 5x inférieur, dimensions réduites disponibles si besoin d'optimiser le stockage, standard de fait pour les nouveaux projets RAG en 2024-2025.

**Contre :** légèrement inférieur à text-embedding-3-large sur des tâches de matching très nuancées.

---

### Option B : text-embedding-3-large

| Dimension | Évaluation |
|---|---|
| Coût | ~0,13 $/million de tokens — 6x plus cher que small |
| Qualité | Meilleure sur les benchmarks — différence marginale pour du texte RH |
| Dimensions | 3072 (configurable de 256 à 3072) |
| Latence | Plus élevée — modèle plus lourd |
| Compatibilité pgvector | ✅ — mais nécessite de changer `vector(1536)` en `vector(3072)` |

**Pour :** meilleure qualité absolue, plus de nuances dans les embeddings.

**Contre :** 6x plus cher pour une différence de qualité imperceptible sur du texte RH. Double les besoins de stockage PostgreSQL.

---

### Option C : text-embedding-ada-002 (legacy)

| Dimension | Évaluation |
|---|---|
| Coût | ~0,10 $/million de tokens |
| Qualité | Inférieure à text-embedding-3-small |
| Dimensions | 1536 (fixe) |

**Pour :** très répandu dans les tutoriels et exemples de code existants.

**Contre :** modèle legacy — OpenAI recommande explicitement de migrer vers text-embedding-3-small. Plus cher que small pour une qualité moindre. Aucune raison de le choisir pour un nouveau projet.

---

## Analyse des compromis

Pour le matching CV/offre d'emploi, `text-embedding-3-small` atteint largement le seuil de qualité nécessaire pour capturer la sémantique des compétences, titres de poste et secteurs d'activité. La différence avec `large` ne sera pas perceptible sur ce type de contenu RH.

À 10 000 offres vectorisées + 1 000 CVs + re-vectorisations périodiques, `text-embedding-3-small` coûte quelques centimes. `text-embedding-3-large` coûterait ~6x plus pour un résultat indiscernable. La dimension 1536 est également la valeur déjà planifiée dans ADR-003 — cohérence totale sans ajustement.

---

## Conséquences

- ✅ Coût d'embedding quasi nul à l'échelle du projet (~quelques centimes pour 10K offres)
- ✅ Cohérence avec ADR-003 : `vector(1536)` déjà défini pour pgvector
- ✅ Déployable via Azure OpenAI (même ressource que GPT-4o-mini)
- ✅ Compatible LangChain, LlamaIndex, et tous les frameworks Python IA
- ⚠️ Si la qualité du matching s'avère insuffisante, migration vers `text-embedding-3-large` possible — juste la dimension du vecteur et un re-embedding des données existantes

---

## Actions suivantes

- [ ] Déployer `text-embedding-3-small` dans la ressource Azure OpenAI (même `azurerm_cognitive_account` que GPT-4o-mini)
- [ ] Confirmer la dimension : `vector(1536)` dans le schéma PostgreSQL (ADR-003 ✅)
- [ ] Implémenter la fonction d'embedding dans un module Python partagé entre les agents : `embed(text: str) -> list[float]`
