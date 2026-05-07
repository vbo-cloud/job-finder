# ADR-006 : LLM Provider pour la couche IA de job-finder

**Statut :** Proposé
**Date :** 2026-05-01
**Décideur :** Vincent Boutin

---

## Contexte

La couche IA de job-finder a besoin d'un LLM pour analyser les offres d'emploi, scorer le matching CV/offre, et générer des recommandations. Trois options : Azure OpenAI Service (modèles OpenAI hébergés dans Azure), l'API Anthropic directement (Claude), ou des modèles open source auto-hébergés (Llama, Mistral). Le reviewer agent utilise déjà l'API Anthropic, mais ce choix a été fait dans un contexte différent — traitement de diffs de code, pas de données utilisateurs.

---

## Décision

**Azure OpenAI Service** pour la couche applicative de job-finder.

> **Note (2026-05-07) :** les modèles gpt-4o-mini et text-embedding-3-small ne sont pas disponibles en SKU Standard régional en francecentral — seul GlobalStandard est supporté. Le compute peut transiter hors francecentral mais reste sur l'infrastructure EU Azure. La facturation et la résidence des données restent en francecentral. À réévaluer quand Microsoft déploie Standard régional pour ces modèles.

---

## Options considérées

### Option A : Azure OpenAI Service

| Dimension | Évaluation |
|---|---|
| Coût | Pay-per-token — identique aux tarifs OpenAI, pas de surcoût Azure |
| Souveraineté des données | ✅ Données traitées et stockées en `francecentral` — ne quittent pas l'UE |
| Intégration Azure | Native — RBAC, Key Vault, managed identity, private endpoint |
| Modèles disponibles | GPT-4o, GPT-4o-mini, embeddings `text-embedding-3-small/large` |
| Valeur portfolio | Très forte — Azure OpenAI est la référence enterprise en contexte Azure |

**Pour :** les données des utilisateurs (CVs, historique de recherche) ne quittent jamais la région Azure `francecentral` — critique pour la conformité RGPD et la commercialisation future. Intégration native avec le reste de la stack : managed identity pour l'auth, Key Vault pour les clés, même réseau privé. GPT-4o-mini offre un excellent rapport qualité/coût pour le scoring et les recommandations.

**Contre :** pas d'accès aux modèles Claude dans Azure — si Claude est jugé plus performant pour certaines tâches, il faudra maintenir deux providers.

---

### Option B : API Anthropic (Claude)

| Dimension | Évaluation |
|---|---|
| Coût | Pay-per-token — tarifs comparables à OpenAI |
| Souveraineté des données | ❌ Données envoyées vers les serveurs Anthropic aux États-Unis |
| Intégration Azure | Indirecte — clé API dans Key Vault, appels HTTP sortants |
| Modèles disponibles | Claude Sonnet, Claude Haiku, Claude Opus |
| Valeur portfolio | Bonne, mais moins pertinente dans un contexte Azure pur |

**Pour :** déjà utilisé pour le reviewer agent, Claude est excellent pour le raisonnement et l'analyse de texte, API simple.

**Contre :** les données utilisateurs (CVs, offres) transitent vers des serveurs US — problématique pour le RGPD et toute commercialisation future en Europe. Incohérent avec une stack 100 % Azure. Introduit une dépendance externe alors qu'Azure OpenAI couvre exactement les mêmes besoins.

---

### Option C : Modèles open source auto-hébergés (Llama 3, Mistral)

| Dimension | Évaluation |
|---|---|
| Coût | ~150-300 €/mois (GPU VM sur AKS pour l'inférence) — hors budget |
| Souveraineté des données | ✅ Totale — tout reste dans Azure |
| Complexité | Très haute — déploiement, optimisation, mises à jour du modèle |
| Qualité | Inférieure à GPT-4o pour les tâches de raisonnement complexe |
| Valeur portfolio | Intéressante techniquement, mais disproportionnée pour ce projet |

**Pour :** contrôle total, zéro coût d'inférence à la requête après setup, indépendance totale.

**Contre :** coût GPU prohibitif, complexité opérationnelle élevée, qualité insuffisante pour le matching sémantique fin.

---

## Analyse des compromis

La souveraineté des données est le facteur décisif. Job-finder traite des CVs — des données personnelles sensibles au sens du RGPD. Envoyer ces données vers des serveurs aux États-Unis (Anthropic) créerait une contrainte légale majeure pour toute commercialisation en Europe.

Azure OpenAI résout ce problème élégamment : mêmes modèles OpenAI, même qualité, mais hébergés dans `francecentral`. La cohérence avec la stack Azure existante est un bonus — une seule managed identity pour s'authentifier, le même Key Vault pour les clés, le même réseau privé.

**Répartition recommandée des LLMs par usage :**
- **Azure OpenAI (GPT-4o-mini)** → analyse d'offres, scoring CV, recommandations (données utilisateurs)
- **Azure OpenAI (text-embedding-3-small)** → génération des embeddings pour pgvector
- **Anthropic API (Claude)** → reviewer agent CI/CD uniquement (pas de données utilisateurs, déjà en place)

---

## Conséquences

- ✅ Conformité RGPD — données utilisateurs traitées et stockées en France
- ✅ Cohérence totale avec la stack Azure (RBAC, Key Vault, réseau privé)
- ✅ GPT-4o-mini : excellent rapport qualité/coût pour le matching et les recommandations
- ✅ `text-embedding-3-small` : modèle d'embedding optimisé, 1536 dimensions, compatible pgvector
- ⚠️ Deux providers LLM coexistent (Azure OpenAI + Anthropic) — bien documenté pour éviter la confusion
- ⚠️ Azure OpenAI nécessite une demande d'accès explicite sur le portail Azure avant de pouvoir provisionner

---

## Actions suivantes

- [ ] Demander l'accès à Azure OpenAI sur le portail Azure (délai : 1-2 jours ouvrés)
- [ ] Créer le module Terraform `ai/openai` (`azurerm_cognitive_account` + `azurerm_cognitive_deployment`)
- [ ] Déployer `gpt-4o-mini` et `text-embedding-3-small` dans la ressource Azure OpenAI
- [ ] Stocker la clé API dans Key Vault, accessible via managed identity depuis les agents
- [ ] Mettre à jour `CLAUDE.md` pour documenter la répartition des providers LLM
