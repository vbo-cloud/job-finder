# ADR-004 : Outil de migration de schéma PostgreSQL

**Statut :** Accepté
**Date :** 2026-05-01
**Décideur :** Vincent Boutin

---

## Contexte

Le schéma PostgreSQL de job-finder évoluera au fil des milestones — ajout de tables, nouvelles colonnes, index pgvector, contraintes. Ces changements doivent être versionnés, reproductibles et appliqués automatiquement en CI/CD sans intervention manuelle sur la base. Trois outils sont en lice : Alembic (Python), Flyway (Java/CLI), et Liquibase (Java/CLI).

---

## Décision

**Alembic**, couplé à SQLAlchemy.

---

## Options considérées

### Option A : Alembic

| Dimension | Évaluation |
|---|---|
| Coût | Gratuit, open source |
| Complexité | Faible — intégré nativement dans les projets Python/FastAPI |
| Langage | Python — cohérent avec la stack agents + API |
| Migrations | Scripts Python ou SQL brut, auto-génération depuis les modèles SQLAlchemy |
| Intégration CI/CD | `alembic upgrade head` au démarrage du container |

**Pour :** même langage que les agents et l'API (Python), auto-génération des migrations depuis les modèles SQLAlchemy (`alembic revision --autogenerate`), pas de runtime Java requis, communauté très active dans l'écosystème IA/FastAPI.

**Contre :** nécessite SQLAlchemy comme ORM (légère dépendance supplémentaire, mais qui sera de toute façon utile pour l'API).

---

### Option B : Flyway

| Dimension | Évaluation |
|---|---|
| Coût | Gratuit (Community) — fonctionnalités avancées payantes |
| Complexité | Moyenne — CLI Java, configuration séparée de la stack Python |
| Langage | SQL pur (fichiers versionnés `V1__init.sql`, `V2__add_column.sql`) |
| Intégration CI/CD | CLI ou image Docker dédiée |

**Pour :** SQL pur lisible par n'importe qui, très mature, largement adopté en entreprise.

**Contre :** runtime Java dans un projet 100 % Python — incohérence de stack, image Docker plus lourde, pas d'auto-génération depuis des modèles Python.

---

### Option C : Liquibase

| Dimension | Évaluation |
|---|---|
| Coût | Gratuit (Community) — fonctionnalités avancées payantes |
| Complexité | Haute — XML/YAML/JSON de configuration, courbe d'apprentissage élevée |
| Langage | XML, YAML, JSON ou SQL |
| Intégration CI/CD | CLI Java ou image Docker |

**Pour :** très puissant, multi-base de données, rollback natif.

**Contre :** complexité disproportionnée pour ce projet, runtime Java, format de configuration verbeux. Conçu pour des équipes larges avec des besoins de gouvernance avancés.

---

## Analyse des compromis

La stack de job-finder est Python de bout en bout (agents, API FastAPI). Introduire un runtime Java pour Flyway ou Liquibase crée une incohérence sans contrepartie réelle — ces outils brillent dans des environnements Java ou polyglotte, pas dans un projet Python solo.

Alembic est le standard de facto dans l'écosystème Python/FastAPI/SQLAlchemy. L'auto-génération des migrations (`--autogenerate`) réduit considérablement l'effort : Alembic compare les modèles Python avec l'état réel de la base et génère le diff SQL automatiquement. C'est particulièrement utile en début de projet quand le schéma évolue vite.

---

## Conséquences

- ✅ Cohérence de stack — tout en Python, un seul runtime
- ✅ Auto-génération des migrations depuis les modèles SQLAlchemy
- ✅ Application automatique au démarrage du container : `alembic upgrade head`
- ✅ Historique des migrations versionné dans Git comme n'importe quel fichier
- ⚠️ SQLAlchemy devient une dépendance obligatoire — à anticiper dans le `requirements.txt` de l'API
- ⚠️ Les migrations pgvector (`CREATE EXTENSION vector`, index HNSW) ne sont pas auto-générées et devront être écrites manuellement en SQL brut dans les scripts Alembic

---

## Actions suivantes

- [ ] Ajouter `alembic` et `sqlalchemy` au `requirements.txt` de l'API
- [ ] Initialiser Alembic dans le repo : `alembic init migrations`
- [ ] Écrire la migration initiale (`V001`) : création des tables `job_offers`, `user_profiles` + activation de pgvector
- [ ] Ajouter `alembic upgrade head` comme étape de démarrage dans le Dockerfile de l'API
