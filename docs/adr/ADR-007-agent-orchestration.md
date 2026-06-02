# ADR-007 : Orchestration des agents de job-finder

**Statut :** Accepté
**Date :** 2026-05-01
**Décideur :** Vincent Boutin

---

## Contexte

Job-finder repose sur 4 agents spécialisés : collecte d'offres, analyse LLM, matching CV, recommandations. Ces agents doivent se coordonner — un agent déclenche le suivant, les erreurs doivent être gérées, et le traitement doit être asynchrone (analyser 1000 offres ne doit pas bloquer une requête utilisateur). Trois approches : Azure Service Bus (messagerie asynchrone managée), HTTP direct entre agents, ou Dapr (abstraction d'orchestration intégrée dans Container Apps).

---

## Décision

**Azure Service Bus** (tier Basic → Standard selon le volume).

---

## Options considérées

### Option A : Azure Service Bus

| Dimension | Évaluation |
|---|---|
| Coût | ~10 €/mois (tier Standard, nécessaire pour les topics) |
| Complexité | Moyenne — SDK Python simple, concepts queue/topic/subscription |
| Découplage | Total — les agents ne se connaissent pas, communiquent via messages |
| Résilience | Excellente — retry automatique, dead-letter queue, messages persistants |
| Valeur portfolio | Très forte — Service Bus est central dans les architectures Azure enterprise |

**Pour :** les agents sont totalement découplés — si l'agent d'analyse tombe, les messages s'accumulent dans la queue et sont traités au redémarrage sans perte. Retry automatique avec backoff exponentiel. Dead-letter queue pour inspecter les messages en erreur. Pattern naturel pour les architectures event-driven multi-agents. Terraform le provisionne nativement (`azurerm_servicebus_namespace`).

**Contre :** ~10 €/mois supplémentaires, introduit un nouveau concept (messagerie asynchrone) à maîtriser.

---

### Option B : HTTP direct entre agents

| Dimension | Évaluation |
|---|---|
| Coût | ~0 € supplémentaire |
| Complexité | Faible en apparence — appels REST entre services |
| Découplage | Nul — couplage fort, si un agent est indisponible tout s'arrête |
| Résilience | Faible — une erreur réseau = perte de la requête |
| Valeur portfolio | Faible — anti-pattern pour une architecture multi-agents sérieuse |

**Pour :** simplicité initiale, pas de nouveau service à gérer.

**Contre :** couplage fort entre agents — si l'agent d'analyse est lent ou en erreur, l'agent de collecte attend ou échoue. Pas de retry natif, pas de persistance des messages, impossible de traiter 1000 offres en parallèle sans surcharger les agents en aval.

---

### Option C : Dapr

| Dimension | Évaluation |
|---|---|
| Coût | ~0 € (inclus dans Container Apps) — mais couplé à Container Apps |
| Complexité | Moyenne — abstraction intéressante mais une couche de plus |
| Découplage | Bon — Dapr abstrait le broker de messages sous-jacent |
| Résilience | Bonne — retry, circuit breaker intégrés |
| Valeur portfolio | Bonne, mais très liée à Container Apps |

**Pour :** intégré nativement dans Container Apps, abstrait le broker, pattern actor model utile pour les agents.

**Contre :** fortement couplé à Container Apps — lors de la migration vers AKS (ADR-002), Dapr devra être installé et configuré séparément. Ajoute une couche d'abstraction qui complique le debugging. Pour un projet solo, la complexité ajoutée n'est pas justifiée quand Service Bus fait le travail directement.

---

## Analyse des compromis

Le choix entre Service Bus et HTTP direct est en réalité le choix entre une architecture résiliente et une architecture fragile. Pour 4 agents qui se passent des milliers d'offres à traiter, HTTP direct créera inévitablement des problèmes de timeouts, de perte de données et de cascades d'erreurs.

Service Bus apporte trois choses fondamentales que HTTP ne peut pas donner : la **persistance** (un message survit au redémarrage d'un agent), le **découplage temporel** (l'agent de collecte peut envoyer 1000 messages sans attendre que l'agent d'analyse les traite), et la **résilience** (dead-letter queue pour les messages en erreur, retry automatique).

**Architecture des messages :**
```
Agent Collecte → Queue "offers-collected" → Agent Analyse
Agent Analyse  → Queue "offers-analyzed"  → Agent Matching
Agent Matching → Queue "matches-ready"    → Agent Recommandations
```

---

## Conséquences

- ✅ Agents totalement découplés — chacun peut scaler indépendamment
- ✅ Traitement asynchrone natif — collecter 1000 offres sans bloquer l'API utilisateur
- ✅ Dead-letter queue — inspecter et rejouer les messages en erreur
- ✅ Persistance — aucun message perdu en cas de redémarrage d'un agent
- ✅ Valeur portfolio : Service Bus + architecture event-driven très recherchés sur les offres DevOps/Cloud Azure
- ⚠️ ~10 €/mois (tier Standard requis pour les topics pub/sub)
- ⚠️ Tier Basic ne supporte que les queues simples — passer au Standard dès que le pattern pub/sub est nécessaire

---

## Actions suivantes

- [ ] Créer le module Terraform `messaging/servicebus` (`azurerm_servicebus_namespace` + queues)
- [ ] Tier Basic pour démarrer, Standard si topics nécessaires
- [ ] Intégrer le SDK Python `azure-servicebus` dans les agents
- [ ] Authentification via managed identity (pas de connection string stockée)
- [ ] Documenter le schéma des messages entre agents dans `docs/architecture/`
