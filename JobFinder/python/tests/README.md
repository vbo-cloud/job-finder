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
| `test_cv_analysis.py` | `agents/cv_analysis/main.py` | `_extract_rome_codes`, `_get_cv_text`, `_set_cv_status`, `_merge_rome_codes` (incl. its `new_codes` return value), `_get_profile_intent`, `_analyze_cv_quality`, `_upsert_cv_analysis`, `_run_quality_analysis`, `main()` retry_quality_only branch, `main()` offer-fetch-request dispatch branch |
| `test_ft_client.py` | `agents/offer_fetching/ft_client.py` | `get_access_token`, `fetch_offers` |
| `test_offer_fetching.py` | `agents/offer_fetching/main.py` | `_parse_experience_min_years`, `_upsert_offers` (values wiring), `_mark_full_refresh_pending`, `_mark_rome_codes_pending`, `_drain_pending_signal`, `_handle_fetch_request` (call wiring, not real Postgres locking — see Intentionally excluded) |
| `test_offer_fetch_scheduler.py` | `agents/offer_fetch_scheduler/main.py` | `_is_scheduled_local_hour`, `main()` |
| `test_match_analysis.py` | `agents/match_analysis/main.py` | `_get_match_context`, `_analyze_match`, `_update_match_analysis` |
| `test_matching.py` | `agents/matching/main.py` | `_upsert_matches`, `_purge_stale_matches` (call order + returned count only) |
| `test_webapp_matches.py` | `agents/webapp/routers/matches.py` | `GET /matches`, `GET /matches/cv/{cv_id}` (incl. `_mark_stale`), `POST /matches/{cv_id}/offers/{offer_id}/analyze` |
| `test_webapp_profile.py` | `agents/webapp/routers/profile.py` | `GET /profile`, `PUT /profile` |
| `test_webapp_cv.py` | `agents/webapp/routers/cv.py` | `POST /upload` (validation), `GET /cv/`, `GET /cv/{cv_id}/analysis` (incl. `_backfill_cv_analysis` self-healing dispatch), thumbnail/pdf (404), `PATCH mark-all-seen`, `DELETE` (404) |

## Design decisions

- **No real DB, API, or network calls.** All external dependencies are mocked via `pytest-mock`.
- **Module collision avoidance.** `cv_analysis/main.py` and `matching/main.py` are both named `main.py`. They are loaded via `importlib.util.spec_from_file_location` under unique module names (`cv_analysis_main`, `matching_main`) to avoid `sys.modules` conflicts.
- **Webapp tests use minimal FastAPI apps.** Instead of importing the `webapp/main.py` entry point (which has a lifespan that runs `run_migrations()`), each webapp test file creates a bare `FastAPI()` instance with only the router under test included. This avoids any database migration calls during testing.
- **PostgreSQL-specific SQL mocked.** `_upsert_matches` uses `pg_insert` with `RETURNING xmax` — incompatible with SQLite. `session.execute()` is mocked to return rows with an `inserted` attribute.

## Intentionally excluded

- `POST /cv/upload` happy path: requires simultaneous mocking of `pdfplumber`, the embedding model (`shared/embedder`), Azure Blob Storage upload, and Service Bus `send_message`. Covered by manual integration tests.
- `_enqueue_top_n_analyses` (`agents/matching/main.py`): uses PostgreSQL-specific SQL (`text()` with `ROW_NUMBER() OVER`) — incompatible with SQLite, same exclusion as `_get_all_matches`. Validated manually (see the verification steps in the implementing PR).
- `_get_all_matches` experience penalty (`agents/matching/main.py`): lives in a PostgreSQL-specific query (CTEs, `GREATEST`/`LEAST`/`NULLIF`) — covered by the existing `_get_all_matches` exclusion. Validated manually against a throwaway Postgres 16 + pgvector with offers of known `experience_min_years` (see the implementing PRs).
- `_get_all_matches` ROME-code hard filter (`agents/matching/main.py`): same PostgreSQL-specific SQL exclusion as above (`jsonb_each`, `CROSS JOIN LATERAL`, the `?` JSONB containment operator) — incompatible with SQLite, no unit test. Validated manually against a throwaway Postgres 16 + pgvector (see prompt-matching-rome-code-hard-filter.md and the implementing PR).
- `_purge_stale_matches` stale-match SQL predicate (`agents/matching/main.py`): same PostgreSQL-specific SQL exclusion as above — incompatible with SQLite. `test_matching.py::TestPurgeStaleMatches` covers call order (match_analyses deleted before matches) and the returned count with a mocked session, not the predicate itself. Validated manually against the same throwaway Postgres 16 + pgvector setup (see prompt-matching-rome-code-hard-filter.md and the implementing PR).
- `GET /cv/{id}/thumbnail` and `GET /cv/{id}/pdf` happy paths: require mocking the blob download client. The 404 paths are covered.
- `DELETE /cv/{id}` happy path: requires mocking blob delete + multi-step DB session. The 404 path is covered.
- `_get_active_rome_codes` (`agents/offer_fetching/main.py`): uses PostgreSQL-specific SQL (`jsonb_object_keys`) — incompatible with SQLite, same class of exclusion as the `agents/matching/main.py` entries above. `_get_active_rome_codes` itself is always mocked in `test_offer_fetching.py`.
- `_handle_fetch_request`'s advisory-lock coordination (`agents/offer_fetching/main.py`): `pg_try_advisory_lock`/`pg_advisory_lock` is real PostgreSQL session-level locking behavior — no SQLite equivalent, and a mocked connection can't reproduce actual cross-process serialization. `test_offer_fetching.py`'s `TestHandleFetchRequest`/`TestMarkFullRefreshPending`/`TestMarkRomeCodesPending`/`TestDrainPendingSignal` only cover the Python-level call wiring (statements executed, commit called, control flow on acquired/busy) — not that Postgres actually serializes concurrent fetch cycles as intended. Validated manually against a throwaway Postgres 16 instance (see prompt-offer-fetching-event-driven-and-new-code-fetch.md and the implementing PR).
