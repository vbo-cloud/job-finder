# ADR-015 : Framework frontend

**Statut :** Accepté
**Date :** 2026-06-02
**Décideur :** Vincent Boutin

---

## Contexte

Job-finder a besoin d'une interface web permettant aux candidats de se connecter via Microsoft Entra External ID, d'uploader leur CV, et de consulter leurs recommandations d'offres d'emploi. Le frontend doit être visuellement impressionnant dès la première visite. Le projet est un portfolio Azure/Cloud/AI : la stack technique doit être cohérente avec la stack backend (Azure, Container Apps, TypeScript si possible) et valorisante sur un CV.

Contraintes :
- Authentification via MSAL (Microsoft Authentication Library) pour Entra External ID
- Appels API vers FastAPI (JWT Bearer dans chaque requête)
- Animations riches (sphères gravitantes, transitions fluides)
- Responsive mobile dès la conception
- Déployé sur Azure Container Apps (Node.js server disponible)
- Pas d'expérience frontend préalable du développeur

---

## Décision

**Next.js 14 (App Router)** avec TypeScript et Tailwind CSS.

---

## Options considérées

### Option A : Next.js 14

| Dimension | Évaluation |
|---|---|
| Complexité initiale | Moyenne — App Router requiert une prise en main |
| SSR / SSG | ✅ — rendu serveur natif |
| SEO | ✅ — HTML pré-rendu |
| Valeur portfolio | Très forte — Next.js est le standard de l'industrie React |
| Intégration MSAL | ✅ — `next-auth` ou MSAL.js directement |
| Animations | ✅ — Framer Motion, Three.js, GSAP compatibles |
| Déploiement Azure | ✅ — Container App Node.js, ou Static Web Apps |
| Ecosystem | Très riche — Vercel, large communauté |

**Pour :** Standard de facto pour les apps React en production. SSR améliore le temps de premier affichage. Démontre une compétence directement transférable. Tailwind CSS intégré nativement. Support TypeScript natif.

**Contre :** App Router introduit des concepts nouveaux (Server Components, Client Components) qui peuvent dérouter un développeur sans expérience frontend.

---

### Option B : React SPA (Vite + React)

| Dimension | Évaluation |
|---|---|
| Complexité initiale | Faible — setup minimal, tout côté client |
| SSR / SSG | ❌ — rendu client uniquement |
| SEO | ❌ — HTML vide au chargement |
| Valeur portfolio | Bonne, mais moins différenciante |
| Intégration MSAL | ✅ — MSAL.js fonctionne bien en SPA |
| Animations | ✅ — mêmes librairies disponibles |
| Déploiement Azure | ✅ — Static Web Apps (fichiers statiques) |

**Pour :** Plus simple à démarrer, pas de concepts serveur/client à gérer.

**Contre :** SEO inexistant (peu important pour une app authentifiée, mais mauvaise pratique). Moins valorisant sur un CV. `create-react-app` est déprécié, Vite est la seule option viable mais l'écosystème est plus fragmenté.

---

### Option C : Vue.js / Nuxt

| Dimension | Évaluation |
|---|---|
| Valeur portfolio (marché FR) | Bonne — Vue.js est populaire en France |
| Courbe d'apprentissage | Similaire à React |
| Ecosystem | Plus petit que React |

**Contre :** La stack backend est déjà React-adjacent (TypeScript, JSON). Moins de ressources d'apprentissage. Moins demandé en contexte Cloud/AI que React/Next.js.

---

### Option D : SvelteKit

| Dimension | Évaluation |
|---|---|
| Performance | Excellente — pas de Virtual DOM |
| Courbe d'apprentissage | Facile |
| Valeur portfolio | Faible — niche, peu demandé |

**Contre :** Très peu présent dans les offres d'emploi Cloud/AI. Incompatible avec l'objectif portfolio.

---

## Analyse des compromis

Next.js vs React SPA est la vraie décision. Le SEO est peu pertinent pour une app avec authentification, mais la valeur portfolio de Next.js est significativement supérieure. La complexité du App Router est réelle mais compensée par une meilleure architecture long terme (Server Components pour les données statiques, Client Components pour les interactions).

Le déploiement sur Container Apps (Node.js) est naturel pour Next.js — cohérent avec l'infrastructure existante. Une alternative serait Azure Static Web Apps pour une SPA, mais elle sort de l'écosystème Container Apps.

---

## Conséquences

- ✅ Next.js sur le CV — compétence directement valorisable
- ✅ TypeScript de bout en bout (FastAPI → OpenAPI → types générés → Next.js)
- ✅ Framer Motion pour les animations (sphères gravitantes, transitions fluides)
- ✅ Tailwind CSS pour le responsive mobile
- ✅ Déployé comme Container App Node.js dans le CAE existant
- ⚠️ App Router requiert de distinguer Server Components et Client Components — tout ce qui utilise MSAL ou des hooks React doit être `"use client"`
- ⚠️ Première expérience frontend — prévoir une courbe d'apprentissage sur les concepts React/Next.js

---

## Stack technique retenue

| Couche | Technologie | Raison |
|---|---|---|
| Framework | Next.js 14 (App Router) | SSR, portfolio, standard industrie |
| Langage | TypeScript | Cohérence, sécurité des types |
| Style | Tailwind CSS | Utility-first, responsive natif |
| Animations | Framer Motion | Transitions fluides, sphères gravitantes |
| Auth | MSAL.js (@azure/msal-browser) | Intégration native Entra External ID |
| HTTP client | Axios ou fetch natif | Appels FastAPI avec JWT |
| Déploiement | Azure Container Apps (Node.js) | Cohérence infrastructure |

---

## Actions suivantes

- [ ] Créer le projet Next.js dans `frontend/` à la racine du repo
- [ ] Configurer MSAL pour Entra External ID (tenant jobfinderapp)
- [ ] Créer le module Terraform `container_app` pour le frontend (réutiliser le module existant)
- [ ] Ajouter le build de l'image frontend dans `buildAgents.yml`
- [ ] ADR-016 : Stratégie de test frontend (Jest, Playwright, ou déféré)
