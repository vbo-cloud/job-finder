# ADR-012 : Monitoring et observabilité

**Statut :** Proposé
**Date :** 2026-05-01
**Décideur :** Vincent Boutin

---

## Contexte

Job-finder repose sur une architecture distribuée — 4 agents Python, une API FastAPI, PostgreSQL, Azure Service Bus, Azure OpenAI. Sans observabilité, diagnostiquer une panne ou une dégradation de performance est quasi-impossible. Les besoins : métriques d'infrastructure (CPU, mémoire, latence), traces des appels entre agents, logs des erreurs, et alertes proactives. Trois approches : Azure Monitor + Application Insights (natif Azure), Datadog, ou Grafana + Prometheus (self-hosted).

---

## Décision

**Azure Monitor + Application Insights** comme stack d'observabilité.

---

## Options considérées

### Option A : Azure Monitor + Application Insights

| Dimension | Évaluation |
|---|---|
| Coût | 5 Go/mois de logs gratuits — suffisant pour un projet portfolio |
| Intégration Azure | ✅ Native — métriques infra automatiques sans configuration |
| Traces distribuées | ✅ — `azure-monitor-opentelemetry` pour les agents Python |
| Alertes | ✅ — Azure Monitor Alerts sur n'importe quelle métrique |
| Dashboards | ✅ — Azure Dashboards + Workbooks |
| Valeur portfolio | Très forte — Azure Monitor est incontournable dans tout projet Azure |

**Pour :** zéro configuration pour les métriques infrastructure — AKS, Container Apps, Service Bus, PostgreSQL Flexible Server remontent automatiquement leurs métriques dans Azure Monitor. Application Insights ajoute la couche applicative (traces, exceptions, latence des endpoints). Le SDK `azure-monitor-opentelemetry` instrumente les agents Python en quelques lignes. Gratuit à l'échelle du projet.

**Contre :** l'interface Azure Monitor est moins intuitive que Datadog ou Grafana pour l'exploration ad hoc.

---

### Option B : Datadog

| Dimension | Évaluation |
|---|---|
| Coût | ~15 €/host/mois — ~45-75 €/mois pour 3-5 nœuds AKS |
| Intégration Azure | ✅ — bonne intégration via l'agent Datadog |
| Traces distribuées | ✅ — APM excellent |
| Alertes | ✅ — très puissant |
| Dashboards | ✅ — meilleure UX que Azure Monitor |
| Valeur portfolio | Bonne, mais hors-stack Azure |

**Pour :** UX supérieure, APM très mature, alertes très flexibles, standard dans les startups tech.

**Contre :** ~45-75 €/mois pour un projet AKS (pricing par host). Complètement disproportionné pour un projet portfolio. Ajoute une dépendance externe hors écosystème Azure. La valeur portfolio est moindre pour un projet centré Azure/Cloud.

---

### Option C : Grafana + Prometheus (self-hosted)

| Dimension | Évaluation |
|---|---|
| Coût | ~0 € de licence — coût en VM/storage pour l'hébergement |
| Intégration Azure | ⚠️ — Prometheus scrappe les métriques, mais les métriques Azure sont moins accessibles |
| Traces distribuées | ✅ — Grafana Tempo pour les traces |
| Alertes | ✅ — Grafana Alerting |
| Charge opérationnelle | Élevée — maintenir Prometheus + Grafana + Tempo sur AKS |
| Valeur portfolio | Bonne pour un profil DevOps/SRE |

**Pour :** open source, contrôle total, dashboards Grafana excellents.

**Contre :** déployer et maintenir Prometheus + Grafana + Tempo sur AKS est un projet en soi. Scrapper les métriques Azure natives (Service Bus, PostgreSQL Flexible Server) est plus complexe qu'avec Azure Monitor. Pour un projet solo, la charge opérationnelle est disproportionnée. Azure offre Managed Grafana si les dashboards Grafana sont souhaités plus tard.

---

## Analyse des compromis

Azure Monitor + Application Insights est la solution évidente pour un projet Azure-natif : l'infrastructure est monitorée automatiquement dès le déploiement, sans agent supplémentaire à gérer. L'instrumentation applicative se fait via le SDK OpenTelemetry standard, ce qui garantit la portabilité si le projet migre vers un autre provider.

**Ce qu'on monitore :**
```
API FastAPI          → Application Insights (latence endpoints, exceptions, taux d'erreur)
Agents Python        → Application Insights (traces distribuées, durée des traitements LLM)
Azure Service Bus    → Azure Monitor (profondeur des queues, dead-letter count, throughput)
PostgreSQL           → Azure Monitor (CPU, connexions, query latency)
AKS / Container Apps → Azure Monitor (CPU/RAM pods, restarts, scaling events)
Azure OpenAI         → Azure Monitor (tokens consommés, latence, throttling)
```

**Alertes critiques à configurer :**
- Taux d'erreur API > 5% → alerte email
- Dead-letter queue > 0 messages → alerte email (message perdu = bug à investiguer)
- CPU PostgreSQL > 80% → alerte email
- Disponibilité API < 99% → alerte email

---

## Conséquences

- ✅ 5 Go/mois de logs gratuits — suffisant pour le projet
- ✅ Métriques infrastructure automatiques — aucune configuration pour AKS, Service Bus, PostgreSQL
- ✅ Traces distribuées via `azure-monitor-opentelemetry` (standard OpenTelemetry)
- ✅ Alertes sur toutes les métriques Azure Monitor
- ✅ Valeur portfolio : Azure Monitor est central dans tout projet Azure cloud
- ✅ Cohérence stack totale — pas de dépendance externe supplémentaire
- ⚠️ UX moins intuitive que Datadog pour l'exploration ad hoc — acceptable pour un projet portfolio
- ⚠️ Au-delà de 5 Go/mois de logs, coût ~2 €/Go — à surveiller en production

---

## Actions suivantes

- [ ] Créer le module Terraform `monitoring/application-insights` (`azurerm_application_insights` lié au `azurerm_log_analytics_workspace`)
- [ ] Ajouter `azure-monitor-opentelemetry` aux `requirements.txt` des agents et de l'API
- [ ] Configurer les alertes critiques : erreur rate API, dead-letter queue, CPU PostgreSQL
- [ ] Créer un dashboard Azure Monitor couvrant : API health, Service Bus queues, PostgreSQL, coût OpenAI tokens
- [ ] Stocker `APPLICATIONINSIGHTS_CONNECTION_STRING` dans Key Vault
