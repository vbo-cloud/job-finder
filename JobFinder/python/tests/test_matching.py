"""Tests for agents/matching/main.py.

Covers: _upsert_matches (empty list, inserted vs updated rows), _purge_stale_matches
(call order and returned count only — the stale-match SQL itself is PostgreSQL-specific,
see tests/README.md "Intentionally excluded").

The module is loaded via importlib under the unique name 'matching_main' to
avoid sys.modules collision with the cv_analysis agent's main.py.
session.execute() is mocked — no real PostgreSQL or pg_insert dialect needed.
"""
import importlib.util
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock

_AGENTS_DIR = Path(__file__).parent.parent / "agents"
_spec = importlib.util.spec_from_file_location(
    "matching_main", _AGENTS_DIR / "matching" / "main.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["matching_main"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

_upsert_matches = _mod._upsert_matches
_purge_stale_matches = _mod._purge_stale_matches


def _make_match(score: float = 0.9) -> dict:
    return {
        "cv_id": str(uuid.uuid4()),
        "offer_id": str(uuid.uuid4()),
        "score": score,
    }


class TestUpsertMatches:
    def test_returns_zero_for_empty_list_without_db_call(self):
        mock_session = MagicMock()

        result = _upsert_matches([], mock_session)

        assert result == 0
        mock_session.execute.assert_not_called()

    def test_counts_only_inserted_rows(self):
        mock_session = MagicMock()
        rows = [
            MagicMock(inserted=True),
            MagicMock(inserted=False),
            MagicMock(inserted=True),
        ]
        mock_session.execute.return_value = rows

        result = _upsert_matches([_make_match() for _ in range(3)], mock_session)

        assert result == 2
        mock_session.execute.assert_called_once()

    def test_returns_zero_when_all_rows_are_updates(self):
        mock_session = MagicMock()
        rows = [MagicMock(inserted=False), MagicMock(inserted=False)]
        mock_session.execute.return_value = rows

        result = _upsert_matches([_make_match(), _make_match()], mock_session)

        assert result == 0

    def test_returns_full_count_when_all_rows_are_new(self):
        mock_session = MagicMock()
        rows = [MagicMock(inserted=True)] * 5
        mock_session.execute.return_value = rows

        result = _upsert_matches([_make_match() for _ in range(5)], mock_session)

        assert result == 5


class TestPurgeStaleMatches:
    def test_deletes_match_analyses_before_matches_and_returns_deleted_count(self):
        mock_session = MagicMock()
        deleted_rows = [MagicMock(id=uuid.uuid4()), MagicMock(id=uuid.uuid4())]
        matches_delete_result = MagicMock()
        matches_delete_result.fetchall.return_value = deleted_rows
        # First execute() call deletes match_analyses (no .fetchall() use), second
        # deletes matches with RETURNING — order matches the FK dependency.
        mock_session.execute.side_effect = [MagicMock(), matches_delete_result]

        result = _purge_stale_matches(mock_session)

        assert result == 2
        assert mock_session.execute.call_count == 2
        first_call_sql = str(mock_session.execute.call_args_list[0].args[0])
        second_call_sql = str(mock_session.execute.call_args_list[1].args[0])
        assert "match_analyses" in first_call_sql
        assert "DELETE FROM matches" in second_call_sql

    def test_returns_zero_when_nothing_stale(self):
        mock_session = MagicMock()
        matches_delete_result = MagicMock()
        matches_delete_result.fetchall.return_value = []
        mock_session.execute.side_effect = [MagicMock(), matches_delete_result]

        result = _purge_stale_matches(mock_session)

        assert result == 0
