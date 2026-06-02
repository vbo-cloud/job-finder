# ADR-002 : Plateforme de compute/orchestration pour job-finder

**Statut :** Accepté
**Date :** 2026-05-01
**Décideur :** Vincent Boutin
**Mise à jour :** 2026-06-02 — Migration AKS abandonnée ; Container Apps retenu définitivement

---

## Contexte

Job-finder est une plateforme multi-agents (collecte d'offres → analyse LLM → matching → recommandations) qui cible une mise en production réelle sur Azure France Central. C'est aussi un projet portfolio dont la valeur formative est un critère explicite. Le budget est modéré. Cinq options sont en jeu : Docker, AKS, Container Apps, Container Instances, et VMSS.

---

## Décision

**Azure Container Apps (ACA)** pour l'ensemble des workloads — agents (Container App Jobs) et webapp FastAPI (Container App permanent).

La stratégie initiale prévoyait une migration vers AKS en Milestone 3. Cette migration a été explicitement abandonnée lors du Milestone 3.

---

## Options considérées

### Option 0 : Docker (seul)

Docker n'est pas une plateforme de déploiement Azure — c'est l'outil de packaging qui s'utilise *avec* toutes les autres options. Il est obligatoire dans tous les cas et constitue le prérequis à tout le reste.

---

### Option A : AKS — Azure Kubernetes Service

| Dimension | Évaluation |
|---|---|
| Coût | ~60–90 €/mois (cluster dev avec 1 node Standard_B2s + free tier control plane) |
| Complexité opérationnelle | Haute — Pods, Services, Deployments, Ingress, RBAC K8s |
| Valeur portfolio | Maximale — Kubernetes est le standard de l'industrie |
| Scalabilité | Excellente — autoscaling natif, multi-agents naturel |
| Intégration Azure | Native — OIDC, Key Vault CSI driver, ACR, Azure Monitor |

**Pour :** Kubernetes est demandé dans ~80% des offres DevOps/Cloud. L'architecture multi-agents (un agent = un Deployment) s'exprime naturellement.

**Contre :** Coût non négligeable en dev, courbe d'apprentissage réelle, overhead opérationnel pour un seul développeur.

---

### Option B : Azure Container Apps (ACA) ✅ Retenu

| Dimension | Évaluation |
|---|---|
| Coût | ~5–20 €/mois (serverless, scale to zero) |
| Complexité opérationnelle | Faible — Kubernetes abstrait, KEDA intégré |
| Valeur portfolio | Bonne — Container Apps, KEDA, Managed Identity, ingress HTTP |
| Scalabilité | Très bonne — scale to zero, KEDA pour event-driven |
| Intégration Azure | Excellente — service discovery natif, identités managées |

**Pour :** Idéal pour démarrer rapidement. Coût quasi nul en dev (scale to zero). KEDA couvre le scaling event-driven sans configuration Kubernetes manuelle.

---

### Option C : Azure Container Instances (ACI)

**Contre :** Pas un outil d'orchestration. Inutilisable pour une architecture multi-agents en production.

---

### Option D : VMSS — Virtual Machine Scale Sets

**Contre :** Anti-pattern cloud-native en 2026. Overhead opérationnel sans bénéfice justifiable.

---

## Analyse des compromis

La vraie décision était entre AKS et Container Apps.

**Pourquoi la migration AKS a été abandonnée en Milestone 3 :**

Container Apps a couvert l'ensemble des besoins sans friction :
- Les agents batch (offer-fetching, matching, cleanup) tournent en Container App Jobs avec triggers timer et queue KEDA — exactement le pattern event-driven voulu.
- La webapp FastAPI tourne en Container App permanent avec ingress HTTP, scale-to-zero, et identité managée.
- L'intégration Azure (Service Bus, ACR, Key Vault, Application Insights) est native et sans configuration supplémentaire.

Migrer vers AKS aurait ajouté : un cluster (~60–90€/mois), des concepts K8s à maîtriser (Deployments, Services, Ingress, ConfigMaps, Secrets), et des modules Terraform AKS à écrire — sans que le projet en ait réellement besoin. La valeur portfolio de Container Apps est suffisante : KEDA, Managed Identity, Container App Jobs, ingress HTTP, et Terraform azurerm sont des compétences directement transférables.

**La valeur formative est couverte autrement :**
- Architecture multi-agents avec Service Bus, KEDA, et identités managées
- Terraform complet : modules réutilisables, state distant, CI/CD OIDC
- GitHub Actions avec build Docker, push ACR, et déploiement automatisé

---

## Conséquences

- ✅ Coût maîtrisé (Container Apps ~scale to zero, ~5–20€/mois en dev)
- ✅ Agents batch et webapp déployés en production sur Container Apps
- ✅ KEDA pour les triggers event-driven (Service Bus) et timer
- ✅ Identités managées (UAMI) pour l'accès ACR, Service Bus, Key Vault
- ✅ Docker comme base commune — compétence immédiatement transférable
- ❌ AKS non utilisé — la connaissance opérationnelle de Kubernetes reste à compléter via un projet dédié ou une certification (AZ-104 acquis, CKA possible)

---

## Actions réalisées

- [x] Dockerfiles pour tous les agents (matching, cleanup, offer-fetching, webapp)
- [x] Module Terraform `modules/container_app_environment/` et `modules/container_app_job/`
- [x] Module Terraform `modules/container_app/` pour le service HTTP permanent
- [x] VNet injection du CAE (`infrastructure_subnet_id`)
- [x] CI/CD build Docker → ACR → mise à jour Container App Jobs et Container App
