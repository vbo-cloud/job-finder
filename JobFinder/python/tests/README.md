# Python Unit Tests

## How to run

From the `JobFinder/python/` directory:

```bash
# Install all dependencies (once)
pip install -r agents/webapp/requirements.txt
pip install -r requirements-dev.txt

# Run all tests
pytest tests/ -v

# Run a specific module
pytest tests/test_cv_analysis.py -v
```

## Modules covered

| Test file | Module under test | Functions covered |
|---|---|---|
| `test_cv_analysis.py` | `agents/cv_analysis/main.py` | `_extract_rome_codes`, `_get_cv_text`, `_set_cv_status`, `_merge_rome_codes`, `_get_profile_intent`, `_analyze_cv_quality`, `_upsert_cv_analysis`, `_run_quality_analysis`, `main()` retry_quality_only branch |
| `test_ft_client.py` | `agents/offer_fetching/ft_client.py` | `get_access_token`, `fetch_offers` |
| `test_offer_fetching.py` | `agents/offer_fetching/main.py` | `_parse_experience_min_years`, `_upsert_offers` (values wiring) |
| `test_tech_keywords.py` | `shared/tech_keywords.py` | `extract_tech_keywords` |
| `test_match_analysis.py` | `agents/match_analysis/main.py` | `_get_match_context`, `_analyze_match`, `_update_match_analysis` |
| `test_matching.py` | `agents/matching/main.py` | `_upsert_matches` |
| `test_webapp_matches.py` | `agents/webapp/routers/matches.py` | `GET /matches`, `GET /matches/cv/{cv_id}`, `POST /matches/{cv_id}/offers/{offer_id}/analyze` |
| `test_webapp_profile.py` | `agents/webapp/routers/profile.py` | `GET /profile`, `PUT /profile` |
| `test_webapp_cv.py` | `agents/webapp/routers/cv.py` | `POST /upload` (validation), `GET /cv/`, `GET /cv/{cv_id}/analysis`, `POST /cv/{cv_id}/analysis/retry`, thumbnail/pdf (404), `PATCH mark-all-seen`, `DELETE` (404) |

## Design decisions

- **No real DB, API, or network calls.** All external dependencies are mocked via `pytest-mock`.
- **Module collision avoidance.** `cv_analysis/main.py` and `matching/main.py` are both named `main.py`. They are loaded via `importlib.util.spec_from_file_location` under unique module names (`cv_analysis_main`, `matching_main`) to avoid `sys.modules` conflicts.
- **Webapp tests use minimal FastAPI apps.** Instead of importing the `webapp/main.py` entry point (which has a lifespan that runs `run_migrations()`), each webapp test file creates a bare `FastAPI()` instance with only the router under test included. This avoids any database migration calls during testing.
- **PostgreSQL-specific SQL mocked.** `_upsert_matches` uses `pg_insert` with `RETURNING xmax` — incompatible with SQLite. `session.execute()` is mocked to return rows with an `inserted` attribute.

## Intentionally excluded

- `POST /cv/upload` happy path: requires simultaneous mocking of `pdfplumber`, the embedding model (`shared/embedder`), Azure Blob Storage upload, and Service Bus `send_message`. Covered by manual integration tests.
- `_enqueue_top_n_analyses` (`agents/matching/main.py`): uses PostgreSQL-specific SQL (`text()` with `ROW_NUMBER() OVER`) — incompatible with SQLite, same exclusion as `_get_all_matches`. Validated manually (see the verification steps in the implementing PR).
- `_get_all_matches` experience penalty and lexical tech-keyword bonus (`agents/matching/main.py`): both corrections live in the same PostgreSQL-specific query (CTEs, `GREATEST`/`LEAST`/`NULLIF`, `UNNEST ... INTERSECT`) — covered by the existing `_get_all_matches` exclusion. Validated manually against a throwaway Postgres 16 + pgvector with offers of known `experience_min_years` / `tech_keywords` (see the implementing PRs).
- `GET /cv/{id}/thumbnail` and `GET /cv/{id}/pdf` happy paths: require mocking the blob download client. The 404 paths are covered.
- `DELETE /cv/{id}` happy path: requires mocking blob delete + multi-step DB session. The 404 path is covered.
