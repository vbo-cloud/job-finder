# ADR-013 : Stratégie Git, Terraform et CI/CD

**Statut :** Accepté
**Date :** 2026-05-03
**Décideur :** Vincent Boutin

---

## Contexte

Job-finder est un projet portfolio solo sur Azure. Architecture actuelle : Gitflow (`feature/*` → `dev` → `main`), 4 dossiers Terraform (`lz-dev`, `dev`, `lz-prod`, `prod`), CI/CD GitHub Actions en matrix. Deux problèmes identifiés :

1. `main` représente la production — y merger des features directement ou de façon granulaire contredit ce principe. Il manque une étape de validation complète avant mise en prod.
2. La structure Terraform monolithique par environnement (`dev/` = un seul state) offre peu de visibilité sur ce qui change, et le blast radius d'un `terraform apply` couvre l'ensemble de l'infrastructure.

---

## Décision

**Architecture en deux parties, implémentée en deux temps :**

1. **Release branch + environnement éphémère de validation** — miroir de prod créé et détruit automatiquement par CI/CD *(implémenté en transition M1 → M2)*
2. **Structure Terraform par composants** — chaque couche (landing-zone, network, data, ai, messaging, compute, monitoring) est un dossier indépendant avec son propre state file *(implémenté en transition M1 → M2)*

---

## Décision détaillée

### Partie 1 : Git flow cible

```
feature/xxx ──→ dev ──→ release/vX.X.X ──→ [staging éphémère] ──→ main (tag vX.X.X)
                  ↑                              ↑
              intégration                  validation complète
              CI: plan                  terraform apply + smoke tests
                                           terraform destroy après merge
```

`main` ne reçoit que des releases validées par un environnement miroir de prod. Chaque merge sur `main` = une version déployée en prod, tagguée `vX.X.X`.

### Partie 2 : Structure Terraform par composants

```
envs/
├── dev/
│   ├── landing-zone/    → state: dev-landing-zone.tfstate  (déployé en 1er)
│   ├── network/         → state: dev-network.tfstate
│   ├── data/            → state: dev-data.tfstate
│   ├── ai/              → state: dev-ai.tfstate
│   ├── messaging/       → state: dev-messaging.tfstate
│   ├── compute/         → state: dev-compute.tfstate
│   └── monitoring/      → state: dev-monitoring.tfstate
├── staging/             → même structure — ÉPHÉMÈRE (créé/détruit par CI)
│   ├── landing-zone/
│   ├── network/
│   └── ...
└── prod/
    ├── landing-zone/    → state: prod-landing-zone.tfstate
    ├── network/
    ├── data/
    ├── ai/
    ├── messaging/
    ├── compute/
    └── monitoring/
```

La Landing Zone devient `landing-zone/` à l'intérieur de chaque environnement — elle reste le premier composant déployé, mais la contrainte d'ordre est gérée par `needs:` en CI/CD, pas par la structure des dossiers.

---

## Options considérées

### Option A : Architecture actuelle — 4 dossiers monolithiques

| Dimension | Évaluation |
|---|---|
| Valeur portfolio | Bonne |
| Séparation main/prod | ⚠️ Pas de validation pré-prod dédiée |
| Blast radius | ⚠️ Un apply touche toute l'infra de l'env |
| Visibilité CI/CD | ⚠️ Un seul check "plan (dev)" pour tout |
| Complexité | Faible |

**Contre :** `main` reçoit des features sans validation dans un environnement miroir. Un seul state par environnement = impossible de savoir d'un coup d'œil dans la CI ce qui a réellement changé.

---

### Option B : Release branch + composants (recommandée)

| Dimension | Évaluation |
|---|---|
| Valeur portfolio | ✅ Excellente — GitOps + IaC lifecycle + component isolation |
| Séparation main/prod | ✅ Totale — main ne reçoit que du validé |
| Blast radius | ✅ Minimal — un apply = un composant |
| Visibilité CI/CD | ✅ `plan (dev/data)`, `plan (dev/compute)`... immédiatement lisible |
| Complexité | Moyenne — remote state references + pipeline ordering |

**Pour :** Chaque composant est isolé. Une PR qui touche `data/` ne déclenche que le pipeline `data`. La CI/CD montre exactement ce qui change. L'environnement éphémère valide la release complète avant prod.

---

### Option C : Terraform Workspaces

| Dimension | Évaluation |
|---|---|
| Valeur portfolio | ❌ Anti-pattern reconnu en production |
| Isolation des envs | ❌ State partagé = risque de toucher prod par erreur |

**Contre :** HashiCorp recommande explicitement des dossiers séparés pour les environnements critiques. Écarté.

---

## Architecture CI/CD cible

### Pipelines par composant

```yaml
# terraformPlan.yml — déclenché sur PR vers dev
# path filter : ne tourne que si le composant a changé
on:
  pull_request:
    paths:
      - 'JobFinder/Terraform/envs/dev/data/**'
```

Checks visibles sur chaque PR :
```
✅ plan (dev/landing-zone)
✅ plan (dev/network)
✅ plan (dev/data)          ← seul celui-ci tourne si seul data/ a changé
— plan (dev/ai)             ← skipped
— plan (dev/messaging)      ← skipped
```

### Ordre de déploiement (apply sur merge vers main)

```yaml
jobs:
  landing-zone: ...
  network:
    needs: landing-zone
  data:
    needs: network
  ai:
    needs: network
  messaging:
    needs: network
  compute:
    needs: [data, ai, messaging]
  monitoring:
    needs: compute
```

### Pipeline staging — release branch

```yaml
# terraformStaging.yml
on:
  push:
    branches: ['release/**']          # → terraform apply sur staging/
  pull_request:
    types: [closed]
    branches: ['main']                # → terraform destroy sur staging/
```

### Protection de branches

```
main :
  ✅ Require PR
  ✅ Status checks : staging-apply, smoke-tests
  ✅ Review : reviewer-agent (Claude)
  ✅ No force push, no deletion

dev :
  ✅ Require PR
  ✅ Status checks : plan (composants modifiés)
  ✅ No force push

release/* :
  ✅ Status checks : staging-apply, smoke-tests
  → merge vers main bloqué si staging échoue
```

---

## Remote state references

Les composants qui dépendent d'autres composants lisent leurs outputs via `terraform_remote_state` :

```hcl
# Dans envs/dev/compute/main.tf
data "terraform_remote_state" "network" {
  backend = "azurerm"
  config = {
    resource_group_name  = "rg-jf-tf-state"
    storage_account_name = "stjftfstatefrc"
    container_name       = "tfstate"
    key                  = "dev-network.tfstate"
  }
}

resource "azurerm_container_app" "api" {
  subnet_id = data.terraform_remote_state.network.outputs.app_subnet_id
}
```

Chaque composant doit exposer ses outputs dans `outputs.tf`. Convention : tout ce qu'un autre composant pourrait consommer doit être en output.

---

## Gestion des données dans staging

L'environnement éphémère valide l'**infrastructure**, pas les données fonctionnelles. La base de données staging démarre vide.

```
Staging valide ✅ :
  - terraform apply passe sans erreur
  - Containers démarrent et se connectent à PostgreSQL
  - API répond sur /health
  - Azure OpenAI répond à un appel de test
  - Service Bus reçoit et distribue un message de test

Staging ne valide pas :
  - Qualité des recommandations IA
  - Performances sous charge réelle
```

---

## Conséquences

- ✅ `main` = production, toujours propre, uniquement des releases validées
- ✅ Blast radius minimal — un apply par composant, isolation totale entre couches
- ✅ CI/CD lisible : le nom du check indique exactement ce qui a changé
- ✅ Un `terraform apply` en prod qui échoue devient quasi-impossible (déjà validé en staging)
- ✅ `terraform destroy` automatique sur staging = pas de coût résiduel
- ✅ Valeur portfolio maximale : GitOps, IaC lifecycle, component isolation, ephemeral environments
- ⚠️ Coût staging : ~20-30€ par release (quelques jours d'environnement actif)
- ⚠️ `staging/` doit rester synchronisé avec `prod/` — toute modification `prod/` = modification `staging/`
- ⚠️ Remote state references : si un output change dans `network/`, vérifier tous les consommateurs

---

## Séquence d'implémentation

Ce changement n'est pas prioritaire tant que l'infra applicative n'existe pas.
**Implémentation prévue : transition Milestone 1 → Milestone 2.**

À ce moment :
- Les modules Terraform de M1 sont écrits et déployés sur dev
- Aucun composant applicatif (agents, API) n'existe encore — refactoring minimal
- La nouvelle structure est en place avant d'ajouter la complexité des agents Python

### Étapes de migration

1. Créer la nouvelle structure de dossiers (`dev/landing-zone/`, `dev/network/`, etc.)
2. Déplacer le code Terraform existant dans les bons composants
3. Mettre à jour les state files (migration `terraform state mv` si des ressources existent)
4. Ajouter les `outputs.tf` dans chaque composant
5. Câbler les `terraform_remote_state` dans les composants dépendants
6. Réécrire `terraformPlan.yml` avec path filters et jobs par composant
7. Créer `terraformStaging.yml`
8. Créer `envs/staging/` (copie de `prod/` avec tfvars staging)
9. Mettre à jour les branch protection rules (ajouter `release/*`, checks staging)

---

## Actions suivantes (Milestone 1 → Milestone 2)

- [ ] Créer la structure `dev/landing-zone/`, `dev/network/`, `dev/data/`, `dev/ai/`, `dev/messaging/`, `dev/compute/`, `dev/monitoring/`
- [ ] Idem pour `prod/` et `staging/`
- [ ] Ajouter les `outputs.tf` dans chaque composant de `landing-zone/` et `network/`
- [ ] Réécrire `terraformPlan.yml` avec path filters par composant et `needs:` ordering
- [ ] Créer `terraformStaging.yml` (apply sur `release/**`, destroy sur merge vers `main`)
- [ ] Mettre à jour les branch protection rules (`release/*`, checks staging sur `main`)
- [ ] Documenter dans `DOC.md`
