# ADR-009 : Framework API pour les endpoints job-finder

**Statut :** Accepté
**Date :** 2026-05-01
**Décideur :** Vincent Boutin

---

## Contexte

La couche API de job-finder doit exposer les endpoints `/jobs`, `/match`, `/recommend` consommés par le frontend ou des clients tiers. L'API est écrite en Python (cohérent avec les agents). Trois candidats : FastAPI, Flask, et Django REST Framework.

---

## Décision

**FastAPI**.

---

## Options considérées

### Option A : FastAPI

| Dimension | Évaluation |
|---|---|
| Coût | Gratuit, open source |
| Complexité | Faible — syntaxe concise, conventions claires |
| Performance | Très haute — async natif, comparable à Node.js |
| Documentation auto | ✅ — Swagger UI et ReDoc générés automatiquement |
| Écosystème IA | Standard de fait — LangChain, SQLAlchemy, Pydantic, tous compatibles |

**Pour :** async natif (idéal pour des appels Azure OpenAI non bloquants), validation automatique des données via Pydantic, documentation OpenAPI générée sans effort, typage Python strict, démarrage en quelques lignes. Standard de fait pour les projets IA/ML Python en 2024-2025.

**Contre :** nécessite de comprendre les concepts async/await — courbe d'apprentissage légère mais réelle.

---

### Option B : Flask

| Dimension | Évaluation |
|---|---|
| Performance | Moyenne — synchrone par défaut |
| Complexité | Très faible — minimaliste |
| Documentation auto | ❌ — nécessite des extensions tierces |
| Écosystème IA | Correct mais daté par rapport à FastAPI |

**Pour :** très simple, énorme base de tutoriels.

**Contre :** synchrone par défaut — chaque appel Azure OpenAI bloque un thread. Pour une API qui fait de l'inférence LLM, c'est un goulot d'étranglement réel. Pas de validation automatique ni de documentation auto native.

---

### Option C : Django REST Framework (DRF)

| Dimension | Évaluation |
|---|---|
| Performance | Faible pour une API légère |
| Complexité | Haute — Django est un framework full-stack |
| Documentation auto | Partielle |
| Écosystème IA | Inadapté |

**Pour :** très complet, auth intégrée, admin interface.

**Contre :** surdimensionné pour une API de microservices. L'ORM Django entrerait en conflit avec SQLAlchemy (ADR-004). Complexité de configuration disproportionnée.

---

## Analyse des compromis

FastAPI a été conçu exactement pour ce cas d'usage — une API Python async qui fait des appels I/O intensifs (base de données, LLM). L'async natif est particulièrement important ici : un endpoint `/match` fait en parallèle une requête pgvector + un appel Azure OpenAI. Avec Flask synchrone, ces appels se font séquentiellement et bloquent le serveur. Avec FastAPI async, ils sont non bloquants et l'API reste réactive sous charge.

La documentation Swagger auto-générée est un bonus portfolio non négligeable — un recruteur peut explorer l'API directement depuis le navigateur sur `/docs`.

---

## Conséquences

- ✅ Async natif — appels LLM et PostgreSQL non bloquants
- ✅ Validation Pydantic automatique sur tous les endpoints
- ✅ Documentation OpenAPI (Swagger) générée automatiquement sur `/docs`
- ✅ Cohérence stack : FastAPI + SQLAlchemy + Alembic + Pydantic = écosystème Python moderne unifié
- ⚠️ Les concepts async/await sont nouveaux si Python est récent pour toi — à prendre en compte dans la courbe d'apprentissage

---

## Actions suivantes

- [ ] Créer la structure du projet API : `app/main.py`, `app/routers/`, `app/models/`, `app/schemas/`
- [ ] Ajouter `fastapi`, `uvicorn`, `pydantic` au `requirements.txt`
- [ ] Implémenter les 3 endpoints de base : `GET /jobs`, `POST /match`, `GET /recommend/{user_id}`
- [ ] Dockeriser l'API avec `uvicorn app.main:app --host 0.0.0.0 --port 8000`
