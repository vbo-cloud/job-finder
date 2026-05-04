# ADR-011 : Authentification utilisateur

**Statut :** Proposé
**Date :** 2026-05-01
**Décideur :** Vincent Boutin

---

## Contexte

Job-finder a besoin d'un système d'authentification pour les utilisateurs finaux (candidats qui uploadent leur CV et consultent leurs recommandations). Les exigences : login social (Google, Microsoft), sécurité solide, conformité RGPD (données en Europe), et coût minimal pour un projet en phase portfolio. Trois approches : Azure AD B2C (CIAM managé), Auth0, ou une solution JWT custom.

---

## Décision

**Azure AD B2C** comme Identity Provider.

---

## Options considérées

### Option A : Azure AD B2C

| Dimension | Évaluation |
|---|---|
| Coût | Gratuit jusqu'à 50 000 MAU — largement suffisant pour un portfolio |
| Souveraineté des données | ✅ EU — tenant B2C déployable en Europe |
| Login social | ✅ — Google, Microsoft, Facebook configurables nativement |
| MFA | ✅ — intégré, configurable par user flow |
| Intégration FastAPI | ✅ — JWT validé via JWKS endpoint, bibliothèque `python-jose` |
| Valeur portfolio | Très forte — Azure AD B2C est la solution enterprise standard Azure pour le CIAM |

**Pour :** gratuit jusqu'à 50K MAU, données en EU (RGPD), login social natif, MFA intégré, tokens JWT standards facilement validables dans FastAPI. Terraform supporte nativement (`azuread` provider). Cohérent avec le reste de la stack Azure.

**Contre :** configuration des user flows B2C plus complexe que Auth0 ; tenant B2C séparé du tenant principal Azure AD.

---

### Option B : Auth0

| Dimension | Évaluation |
|---|---|
| Coût | Gratuit jusqu'à 7 500 MAU — limite plus basse |
| Souveraineté des données | ⚠️ — région US par défaut, EU disponible en plan payant |
| Login social | ✅ — très simple à configurer |
| MFA | ✅ — intégré |
| Intégration FastAPI | ✅ — excellent SDK Python |
| Valeur portfolio | Bonne, mais hors-stack Azure |

**Pour :** DX (Developer Experience) excellente, documentation très accessible, onboarding rapide.

**Contre :** limite de 7 500 MAU gratuits (vs 50 000 pour B2C). Données aux US par défaut — problème RGPD pour un projet traitant des CVs. Ajoute une dépendance externe hors écosystème Azure alors que tout le reste est Azure-natif.

---

### Option C : Solution JWT custom

| Dimension | Évaluation |
|---|---|
| Coût | ~0 € de licence — coût en temps de développement |
| Souveraineté des données | ✅ — contrôle total |
| Login social | ❌ — à implémenter manuellement via OAuth2 |
| MFA | ❌ — à implémenter |
| Sécurité | ⚠️ — risque élevé de failles si mal implémenté |
| Valeur portfolio | Faible — réinventer la roue n'est pas valorisé |

**Pour :** contrôle total, zéro dépendance externe.

**Contre :** implémenter correctement l'auth (hachage des mots de passe, refresh tokens, révocation, MFA, login social) est un projet à part entière. Les erreurs de sécurité sont courantes et coûteuses. Pour un projet portfolio, démontrer l'intégration d'un CIAM enterprise est plus valorisant que de réinventer une roue imparfaite.

---

## Analyse des compromis

Azure AD B2C résout tous les problèmes simultanément : RGPD (données en EU), gratuité à l'échelle du projet (50K MAU), login social natif, et cohérence totale avec la stack Azure. La limite de Auth0 à 7 500 MAU gratuits et la localisation US des données en font un mauvais choix pour ce contexte.

**Architecture d'authentification :**
```
Utilisateur → Azure AD B2C (user flow "Sign up / Sign in")
           → JWT émis (access token + refresh token)
           → FastAPI valide le JWT via JWKS endpoint B2C
           → Claims extraits (user_id, email) → requêtes PostgreSQL
```

---

## Conséquences

- ✅ Gratuit jusqu'à 50 000 utilisateurs actifs mensuels
- ✅ Données utilisateurs stockées en EU — conformité RGPD
- ✅ Login social (Google, Microsoft) sans développement custom
- ✅ MFA intégré et configurable par user flow
- ✅ JWT standards validables avec `python-jose` dans FastAPI
- ✅ Valeur portfolio : Azure AD B2C = solution CIAM enterprise Azure standard
- ⚠️ Configuration des user flows B2C requiert une prise en main initiale
- ⚠️ Tenant B2C séparé du tenant Azure principal — à documenter dans GETTING_STARTED

---

## Actions suivantes

- [ ] Créer le tenant Azure AD B2C (région West Europe)
- [ ] Configurer le user flow "Sign up and sign in" avec Google et Microsoft comme IdP sociaux
- [ ] Enregistrer l'application FastAPI dans B2C (`client_id`, scope `openid profile email`)
- [ ] Implémenter la validation JWT dans FastAPI via `python-jose` + JWKS endpoint B2C
- [ ] Créer le module Terraform `auth/b2c` (`azuread_b2c_directory`)
- [ ] Stocker `B2C_CLIENT_ID`, `B2C_TENANT_NAME` dans Key Vault
