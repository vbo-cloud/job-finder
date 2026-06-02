# ADR-017 : Stratégie de monitoring et alerting

**Statut :** Accepté
**Date :** 2026-06-02
**Décideur :** Vincent Boutin

---

## Contexte

ADR-012 a décidé d'utiliser Azure Monitor + Application Insights comme stack d'observabilité. Ce document précise **ce qu'on monitore**, **comment** (requêtes KQL), et **quand on alerte** — pour chaque couche de l'architecture job-finder.

L'objectif est double : détecter les pannes rapidement, et démontrer une maîtrise de l'observabilité dans un contexte Azure (valeur portfolio).

Architecture à monitorer :
- FastAPI webapp (Container App)
- 3 agents Python (Container App Jobs : fetch, matching, cleanup)
- PostgreSQL Flexible Server
- Azure Service Bus (queues offer-ready, match-ready)
- Azure OpenAI (GPT-4o-mini + text-embedding-3-small)
- Azure Blob Storage (CVs)

---

## Décision

**Application Insights** pour les métriques applicatives (logs structurés, traces, exceptions), **Azure Monitor Alerts** pour les alertes proactives, **requêtes KQL** pour l'investigation.

---

## Ce qu'on monitore par couche

### FastAPI webapp

**Métriques clés :**
- Taux d'erreur 5xx par endpoint
- Latence P95 de `POST /cv/upload` (inclut extraction PDF + embedding + blob upload)
- Taux d'échec d'authentification JWT (401)
- Nombre d'uploads CV par heure

**Requêtes KQL utiles :**
```kusto
-- Taux d'erreur 5xx sur les 24 dernières heures
requests
| where timestamp > ago(24h)
| where resultCode startswith "5"
| summarize count() by bin(timestamp, 1h), name
| order by timestamp desc

-- Latence P95 par endpoint
requests
| where timestamp > ago(24h)
| summarize percentile(duration, 95) by name
| order by percentile_duration_95 desc

-- Erreurs JWT (401)
requests
| where timestamp > ago(24h)
| where resultCode == "401"
| summarize count() by bin(timestamp, 1h)
```

---

### Agents Python (structlog → Application Insights)

**Métriques clés :**
- Durée d'exécution de chaque agent (offer_fetch, matching, cleanup)
- Nombre d'offres fetchées / embeddées par run
- Nombre de matches générés par run
- Erreurs OpenAI (timeout, quota dépassé)
- Erreurs Service Bus (send/receive)

**Requêtes KQL utiles :**
```kusto
-- Durée des runs d'agents
customEvents
| where timestamp > ago(7d)
| where name in ("offer_fetch_run_completed", "matching_run_completed", "cleanup_completed")
| extend duration = todouble(customDimensions["duration_seconds"])
| summarize avg(duration), max(duration) by name, bin(timestamp, 1d)

-- Erreurs OpenAI
exceptions
| where timestamp > ago(24h)
| where outerMessage contains "openai"
| summarize count() by bin(timestamp, 1h), outerMessage

-- Offres fetchées par run
customEvents
| where name == "offer_fetch_run_completed"
| extend new_offers = toint(customDimensions["new_offers_count"])
| summarize sum(new_offers) by bin(timestamp, 1d)
```

---

### Azure Service Bus

**Métriques clés :**
- Profondeur des queues `offer-ready` et `match-ready`
- Dead-letter count (message impossible à traiter)
- Throughput (messages/heure)

**Requêtes KQL utiles :**
```kusto
-- Dead-letter count en temps réel
AzureMetrics
| where ResourceType == "MICROSOFT.SERVICEBUS/NAMESPACES"
| where MetricName == "DeadletteredMessages"
| where TimeGenerated > ago(1h)
| summarize max(Maximum) by bin(TimeGenerated, 5m), Resource
```

---

### PostgreSQL Flexible Server

**Métriques clés :**
- CPU utilization (alerte si > 80%)
- Connexions actives (max ~50 pour B1ms)
- Query latency (slow queries > 1s)
- Storage utilization

---

### Azure OpenAI

**Métriques clés :**
- Tokens consommés par heure (TPM utilisés vs quota 1M)
- Taux de throttling (429)
- Latence des appels embedding

---

## Alertes configurées

| Alerte | Condition | Sévérité | Action |
|---|---|---|---|
| API erreurs 5xx | Taux > 5% sur 5 min | Critique | Email |
| Dead-letter queue | Count > 0 | Haute | Email |
| CPU PostgreSQL | > 80% sur 10 min | Haute | Email |
| Quota OpenAI | TPM > 80% du quota | Moyenne | Email |
| Agent fetch absent | Pas de run depuis 25h | Haute | Email |
| Webapp indisponible | Availability < 99% sur 5 min | Critique | Email |

---

## Dashboard Azure Monitor

Un dashboard couvrant en temps réel :

```
┌──────────────────────────────────────────────┐
│  job-finder — Dashboard opérationnel          │
├──────────────┬───────────────────────────────┤
│ API Health   │ Requests/min | Error rate      │
│              │ P95 latency  | Active users    │
├──────────────┼───────────────────────────────┤
│ Agents       │ Last fetch run | Offers today  │
│              │ Matches today  | Last cleanup  │
├──────────────┼───────────────────────────────┤
│ Service Bus  │ offer-ready depth | DLQ count  │
│              │ match-ready depth             │
├──────────────┼───────────────────────────────┤
│ PostgreSQL   │ CPU | Connections | Storage    │
├──────────────┼───────────────────────────────┤
│ OpenAI       │ TPM used | Throttling rate     │
└──────────────┴───────────────────────────────┘
```

---

## Instrumentation Python

Les agents utilisent `structlog` avec des champs structurés — Application Insights ingère ces logs via la variable `APPLICATIONINSIGHTS_CONNECTION_STRING`.

Chaque agent log ses métriques métier à la fin de chaque run :

```python
logger.info(
    "offer_fetch_run_completed",
    run_date=run_date,
    new_offers_count=total_new,
    embedded_count=embedded_count,
    duration_seconds=elapsed,
)
```

Ces événements sont queryables en KQL via `customEvents`.

---

## Conséquences

- ✅ Visibilité complète sur chaque couche sans infrastructure supplémentaire
- ✅ Alertes proactives — pannes détectées avant que les utilisateurs les signalent
- ✅ KQL requêtes réutilisables — investigation rapide en cas d'incident
- ✅ Dashboard portfolio — démontre la maîtrise de l'observabilité Azure
- ⚠️ `APPLICATIONINSIGHTS_CONNECTION_STRING` doit être injecté dans tous les agents et la webapp
- ⚠️ Les agents n'ont pas encore de champ `duration_seconds` — à ajouter lors de l'implémentation

---

## Actions suivantes

- [ ] Stocker `APPLICATIONINSIGHTS_CONNECTION_STRING` dans Key Vault (`appinsights-connection-string`)
- [ ] Injecter la variable dans tous les Container App Jobs et le Container App webapp
- [ ] Configurer les 6 alertes dans Terraform (`azurerm_monitor_metric_alert`)
- [ ] Créer le dashboard Azure Monitor
- [ ] Ajouter `duration_seconds` dans les logs de fin de run de chaque agent
