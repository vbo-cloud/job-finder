---
name: conventions-sql
description: Conventions SQL / SQLAlchemy / Alembic obligatoires du projet Job Finder — clés primaires UUID v4 (sauf tables cache/stats recalculées en bloc), nommage des tables et des contraintes (ix_/uq_/fk_), colonnes DateTime(timezone=True) obligatoires, une migration Alembic = un changement logique. Utilise ce skill avant d'écrire ou modifier un modèle SQLAlchemy, une migration Alembic, ou tout schéma touchant offers/cvs/matches/term_stats — même si l'utilisateur ne mentionne pas explicitement "base de données" ou "Alembic".
---

# SQL / Alembic Conventions

## Modèles SQLAlchemy
- Clés primaires : UUID v4 (`uuid.uuid4`) — jamais d'autoincrement
  - Exception : une table de type cache/statistiques entièrement recalculée et remplacée en bloc à
    chaque cycle (pas d'`ON CONFLICT`, pas de référence entrante depuis une autre table) peut utiliser
    sa clé naturelle comme clé primaire (ex. `term_stats.term`) — un UUID surrogate n'apporterait
    aucune valeur puisque la ligne est identifiée et retrouvée uniquement par cette valeur.
- Toutes les tables ont `created_at` (DateTime, default `utcnow`, `nullable=False`). Raison : l'audit et le debug des pipelines de fetch et de matching nécessitent de savoir quand chaque ligne a été créée.
- Nommage des tables : snake_case pluriel (`offers`, `cvs`, `matches`)
- `nullable=True` et `nullable=False` toujours explicites — jamais implicites. Raison : évite les incohérences silencieuses entre migrations successives sur une même colonne.
- Toutes les colonnes DateTime utilisent `DateTime(timezone=True)` (mappe vers TIMESTAMPTZ en PostgreSQL) — jamais `DateTime` seul. Compatible avec `datetime.now(timezone.utc)`.

## Nommage des contraintes
- Index : `ix_{table}_{colonne}` (ex: `ix_offers_ft_id`)
- Contraintes d'unicité : `uq_{table}_{colonne}` (ex: `uq_offers_ft_id`)
- Clés étrangères : `fk_{table}_{colonne}_ref_{table_cible}` (ex: `fk_matches_cv_id_ref_cvs`)
- Raison : un nommage cohérent permet de repérer immédiatement le type de contrainte et la table concernée dans les messages d'erreur Postgres, sans avoir à ouvrir le schéma.

## Migrations Alembic
- Une migration = un changement logique — jamais plusieurs features dans la même migration
- Nommage fichier : `{NNN}_{description_courte}.py` (ex: `001_initial_schema.py`)
- `down_revision` toujours renseigné — chaque migration doit implémenter `downgrade()`
- `alembic upgrade head` appelé au démarrage de chaque agent (idempotent)
