# SQL / Alembic Conventions

## Modèles SQLAlchemy
- Clés primaires : UUID v4 (`uuid.uuid4`) — jamais d'autoincrement
- Toutes les tables ont `created_at` (DateTime, default `utcnow`, `nullable=False`)
- Nommage des tables : snake_case pluriel (`offers`, `cvs`, `matches`)
- `nullable=True` et `nullable=False` toujours explicites — jamais implicites
- Toutes les colonnes DateTime utilisent `DateTime(timezone=True)` (mappe vers TIMESTAMPTZ en PostgreSQL) — jamais `DateTime` seul. Compatible avec `datetime.now(timezone.utc)`.

## Nommage des contraintes
- Index : `ix_{table}_{colonne}` (ex: `ix_offers_ft_id`)
- Contraintes d'unicité : `uq_{table}_{colonne}` (ex: `uq_offers_ft_id`)
- Clés étrangères : `fk_{table}_{colonne}_ref_{table_cible}` (ex: `fk_matches_cv_id_ref_cvs`)

## Migrations Alembic
- Une migration = un changement logique — jamais plusieurs features dans la même migration
- Nommage fichier : `{NNN}_{description_courte}.py` (ex: `001_initial_schema.py`)
- `down_revision` toujours renseigné — chaque migration doit implémenter `downgrade()`
- `alembic upgrade head` appelé au démarrage de chaque agent (idempotent)
