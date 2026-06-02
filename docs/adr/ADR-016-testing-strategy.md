# ADR-016 : Stratégie de test

**Statut :** Accepté
**Date :** 2026-06-02
**Décideur :** Vincent Boutin

---

## Contexte

Job-finder est un projet portfolio solo avec une deadline v1.0.0 en septembre 2026. Le projet couvre trois couches testables : agents Python (backend), API FastAPI, et frontend Next.js. Les ressources de développement sont limitées (un seul développeur, délai contraint). Les tests doivent apporter une valeur réelle sans devenir un frein à la livraison.

Contraintes :
- Développeur solo, pas d'équipe QA
- Timeline serrée — septembre 2026
- Stack hétérogène : Python (agents), Python (FastAPI), TypeScript (Next.js)
- Pas d'expérience frontend préalable — tests frontend complexes à écrire
- Projet portfolio — démontrer la connaissance des bonnes pratiques suffit

---

## Décision

**Tests unitaires Python ciblés** sur la logique métier critique, **pas de tests frontend automatisés pour v1.0.0**, **tests e2e différés à v1.1.0**.

---

## Options considérées

### Option A : Couverture complète (unit + integration + e2e)

| Dimension | Évaluation |
|---|---|
| Couverture | Maximale |
| Temps d'implémentation | Très élevé — 3-4 semaines |
| Valeur portfolio | Très forte |
| Risque délai | Élevé — peut compromettre la livraison v1.0.0 |

**Pour :** Démontre une maîtrise complète du testing. Pytest + HTTPX pour FastAPI, Playwright pour e2e, Jest/Testing Library pour React.

**Contre :** Irréaliste dans le délai disponible. Les tests e2e sont particulièrement coûteux à maintenir sur une app avec authentification externe (Entra External ID).

---

### Option B : Tests unitaires Python uniquement (retenu)

| Dimension | Évaluation |
|---|---|
| Couverture | Ciblée sur la logique métier |
| Temps d'implémentation | Faible — 3-5 jours |
| Valeur portfolio | Bonne — démontre les bonnes pratiques |
| Risque délai | Nul |

**Pour :** Pytest est natif Python, facile à intégrer. La logique métier critique (cleanup, matching, extraction ROME, validation JWT) est bien délimitée et testable sans infrastructure Azure. Les mocks permettent de tester sans base de données ni API externe.

**Contre :** Pas de couverture frontend ni e2e.

---

### Option C : Aucun test

**Contre :** Incompatible avec l'objectif portfolio. Un recruteur technique qui lit le repo sans tests remet en question la rigueur du développeur.

---

## Analyse des compromis

L'option B est le meilleur compromis délai/valeur. Quelques tests unitaires bien écrits sur la logique critique démontrent la connaissance des bonnes pratiques sans bloquer la livraison. Les tests e2e avec authentification externe sont notoirement complexes à maintenir — les différer est une décision d'ingénierie valide, pas un raccourci.

---

## Périmètre retenu pour v1.0.0

### Tests unitaires Python (pytest)

| Module | Ce qu'on teste | Priorité |
|---|---|---|
| `agents/cleanup/main.py` | Logique cutoff, branche NULL ft_updated_at | Haute |
| `agents/webapp/routers/cv.py` | Validation content_type, magic bytes, taille | Haute |
| `agents/webapp/auth.py` | Validation JWT, expiration, mauvais issuer | Haute |
| `agents/webapp/rome_extractor.py` | Parsing JSON, validation format codes ROME | Moyenne |
| `shared/embedder.py` | Batching, gestion erreur OpenAI (mock) | Moyenne |
| `agents/offer_fetching/main.py` | Logique upsert, reset embedding conditionnel | Basse |

### Pas de tests pour v1.0.0
- Frontend Next.js — composants React
- Tests d'intégration FastAPI (HTTPX + base de données réelle)
- Tests e2e Playwright

### Différé à v1.1.0
- Tests e2e Playwright (login → upload CV → voir matches)
- Tests d'intégration FastAPI avec base de données de test
- Tests de composants React (Jest + Testing Library)

---

## Conséquences

- ✅ Tests unitaires sur la logique critique — filet de sécurité pour les refactors
- ✅ Pytest dans CI/CD — bloque le merge si un test échoue
- ✅ Mocks sur Azure OpenAI et Azure Blob Storage — tests rapides sans coût API
- ✅ Délai v1.0.0 respecté
- ⚠️ Pas de couverture frontend — les régressions UI sont détectées manuellement
- ⚠️ Pas de tests d'intégration FastAPI — les bugs d'interaction DB/API non couverts

---

## Actions suivantes

- [ ] Ajouter `pytest` et `pytest-mock` dans `requirements.txt` des agents concernés
- [ ] Créer `JobFinder/python/tests/` avec les tests prioritaires (cleanup, auth, cv upload)
- [ ] Ajouter une étape `pytest` dans le workflow CI/CD (sur PR, avant le plan Terraform)
- [ ] ADR-017 : Stratégie de monitoring et alerting (Application Insights queries, alertes sur erreurs 5xx)
