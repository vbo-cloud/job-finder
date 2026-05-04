# ADR-005 : Container Registry pour les images Docker

**Statut :** Proposé
**Date :** 2026-05-01
**Décideur :** Vincent Boutin

---

## Contexte

Chaque agent et l'API FastAPI de job-finder seront packagés en images Docker. Ces images doivent être stockées dans un registry accessible depuis AKS (et Container Apps en Milestone 1). Deux options : Azure Container Registry (ACR), natif Azure, ou GitHub Container Registry (GHCR), natif GitHub Actions.

---

## Décision

**Azure Container Registry (ACR)**, tier Basic.

---

## Options considérées

### Option A : Azure Container Registry (ACR)

| Dimension | Évaluation |
|---|---|
| Coût | ~5 €/mois (tier Basic, 10 Go inclus) |
| Complexité | Faible — intégration native AKS via managed identity |
| Authentification | Managed identity — pas de secrets à gérer |
| Intégration Azure | Native — pull direct depuis AKS sans configuration d'imagePullSecret |
| Valeur portfolio | Forte — ACR est la solution standard dans les architectures Azure |

**Pour :** AKS peut puller des images ACR via managed identity sans aucun secret (`az aks update --attach-acr`), réseau privé possible via private endpoint, géré par Terraform, scanning de vulnérabilités intégré (Microsoft Defender), cohérent avec le reste de la stack Azure.

**Contre :** coût mensuel (~5 €), une ressource de plus à provisionner.

---

### Option B : GitHub Container Registry (GHCR)

| Dimension | Évaluation |
|---|---|
| Coût | Gratuit pour les repos publics, inclus dans GitHub Actions pour les privés |
| Complexité | Moyenne — AKS nécessite un `imagePullSecret` pour s'authentifier |
| Authentification | PAT ou GITHUB_TOKEN — secret à stocker dans AKS |
| Intégration Azure | Indirecte — AKS doit être configuré pour puller depuis ghcr.io |
| Valeur portfolio | Correcte, mais moins pertinente dans un contexte Azure pur |

**Pour :** gratuit, déjà dans l'écosystème GitHub Actions, pas de ressource Azure supplémentaire.

**Contre :** introduit une dépendance externe dans une stack 100 % Azure, nécessite un `imagePullSecret` dans chaque namespace AKS (secret à gérer, rotater), moins cohérent pour un portfolio Azure.

---

## Analyse des compromis

5 €/mois est le seul argument en faveur de GHCR. Ce coût est négligeable au regard de la valeur apportée par ACR : zéro secret à gérer pour l'authentification AKS (managed identity), réseau privé natif, scanning de sécurité, et cohérence totale avec la stack Azure déjà en place.

Pour un portfolio ciblant des rôles Cloud/DevOps Azure, utiliser GHCR serait un signal incohérent — ACR est ce qu'un architecte Azure mettrait en place systématiquement.

---

## Conséquences

- ✅ Authentification AKS → ACR via managed identity, zéro secret
- ✅ Cohérence complète avec la stack Azure (même région, même Terraform, même RBAC)
- ✅ Scanning de vulnérabilités sur les images inclus
- ✅ Nommage cohérent : `crjfdevfrc.azurecr.io/agent-collector:latest` (sans tirets, max 24 chars → `crjfdevfrc`)
- ⚠️ ~5 €/mois de coût fixe dès la Milestone 1
- ⚠️ Attacher ACR à AKS nécessite un role assignment Terraform : `AcrPull` sur le managed identity du kubelet

---

## Actions suivantes

- [ ] Créer le module Terraform `data/container-registry` (`azurerm_container_registry`, tier Basic)
- [ ] Ajouter le role assignment `AcrPull` sur le managed identity AKS dans le module `compute/aks`
- [ ] Configurer le push d'images dans les workflows CI/CD : build → tag → push vers ACR après apply
- [ ] Nommage ACR : `crjf{env}frc` (ex: `crjfdevfrc`) — sans tirets, cohérent avec la convention storage accounts
