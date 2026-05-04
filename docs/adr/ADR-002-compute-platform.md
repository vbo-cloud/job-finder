# ADR-002 : Plateforme de compute/orchestration pour job-finder

**Statut :** Proposé
**Date :** 2026-05-01
**Décideur :** Vincent Boutin

---

## Contexte

Job-finder est une plateforme multi-agents (collecte d'offres → analyse LLM → matching → recommandations) qui cible une mise en production réelle sur Azure France Central. C'est aussi un projet portfolio dont la valeur formative est un critère explicite. Le budget est modéré. Cinq options sont en jeu : Docker, AKS, Container Apps, Container Instances, et VMSS.

---

## Décision

**AKS (Azure Kubernetes Service)** pour l'orchestration des agents et de l'API, avec Docker comme couche de packaging commune à toutes les options.

Stratégie en deux temps :
1. **Milestone 1** → Azure Container Apps (démarrage rapide, scale to zero, coût minimal)
2. **Milestone 3** → Migration vers AKS (charge multi-agents réelle, apprentissage K8s justifié)

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

**Pour :** Kubernetes est demandé dans ~80% des offres DevOps/Cloud. L'architecture multi-agents (un agent = un Deployment) s'exprime naturellement. Terraform gère AKS nativement. C'est déjà la cible écrite dans le CLAUDE.md.

**Contre :** Coût non négligeable en dev, courbe d'apprentissage réelle, overhead opérationnel pour un seul développeur.

---

### Option B : Azure Container Apps (ACA)

| Dimension | Évaluation |
|---|---|
| Coût | ~5–20 €/mois (serverless, scale to zero) |
| Complexité opérationnelle | Faible — Kubernetes abstrait, KEDA intégré |
| Valeur portfolio | Bonne, mais moins différenciante que K8s |
| Scalabilité | Très bonne — scale to zero, KEDA pour event-driven |
| Intégration Azure | Excellente — Dapr intégré, service discovery natif |

**Pour :** Idéal pour démarrer rapidement. Coût quasi nul en dev (scale to zero). Dapr est un excellent pattern pour les architectures multi-agents.

**Contre :** Cache la complexité Kubernetes — moins formateur pour comprendre ce qui se passe sous le capot. Moins différenciant sur un CV.

---

### Option C : Azure Container Instances (ACI)

| Dimension | Évaluation |
|---|---|
| Coût | Très faible (~2–5 €/mois) |
| Complexité opérationnelle | Très faible |
| Valeur portfolio | Faible — pas d'orchestration |
| Scalabilité | Nulle — pas de load balancing natif |

**Pour :** Parfait pour des tâches ponctuelles (jobs de scraping, tests one-shot).

**Contre :** Pas un outil d'orchestration. Inutilisable pour une architecture multi-agents en production.

---

### Option D : VMSS — Virtual Machine Scale Sets

| Dimension | Évaluation |
|---|---|
| Coût | Élevé (~80–150 €/mois) |
| Complexité opérationnelle | Très haute — gestion des VMs, OS, patchs |
| Valeur portfolio | Faible dans un contexte cloud-native |
| Scalabilité | Bonne, mais manuelle à configurer |

**Pour :** Utile si on a besoin de contrôle bas niveau sur l'OS.

**Contre :** Anti-pattern cloud-native en 2026. AKS utilise VMSS en dessous — autant travailler directement avec AKS. Aucune raison de choisir VMSS pour ce projet.

---

## Analyse des compromis

La vraie décision est entre AKS et Container Apps. VMSS et ACI sont éliminés d'emblée.

Le critère de valeur formative tranche en faveur d'AKS à terme : Kubernetes est omniprésent sur le marché et la compréhension des concepts (Pod, Service, Ingress, RBAC, namespace) ne s'acquiert pas en utilisant Container Apps.

La stratégie en deux temps évite de payer AKS pendant des mois sans charge réelle, tout en garantissant que K8s est atteint quand ça fait du sens (agents réels à orchestrer).

---

## Conséquences

- ✅ Coût maîtrisé en phase de développement (Container Apps ~scale to zero)
- ✅ Kubernetes appris au bon moment, sur une vraie charge multi-agents
- ✅ Docker comme base commune — compétence immédiatement transférable
- ⚠️ Migration Container Apps → AKS à planifier (Terraform, workflows CI/CD) — à anticiper dès le design pour éviter la dette architecturale
- ⚠️ AKS en dev : préférer 1 seul node System Pool + spot nodes pour limiter les coûts

---

## Actions suivantes

- [ ] Ajouter Docker à la stack de dev local (Dockerfile par agent)
- [ ] Créer le module Terraform `compute/container-apps` pour la Milestone 1
- [ ] Prévoir le module `compute/aks` pour la Milestone 3 (structurer sans implémenter)
- [ ] Documenter la stratégie de migration ACA → AKS dans `DOC.md`
