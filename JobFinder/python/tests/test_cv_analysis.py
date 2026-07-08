"""Tests for agents/cv_analysis/main.py.

Covers: _extract_rome_codes, _get_cv_text, _set_cv_status, _merge_rome_codes,
_get_profile_intent, _analyze_cv_quality, _upsert_cv_analysis.

The module is loaded via importlib under the unique name 'cv_analysis_main' to
avoid sys.modules collision with the matching agent's main.py.
"""
import importlib.util
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from openai import OpenAIError
from sqlalchemy.exc import SQLAlchemyError

_AGENTS_DIR = Path(__file__).parent.parent / "agents"
_spec = importlib.util.spec_from_file_location(
    "cv_analysis_main", _AGENTS_DIR / "cv_analysis" / "main.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["cv_analysis_main"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

_extract_rome_codes = _mod._extract_rome_codes
_get_cv_text = _mod._get_cv_text
_set_cv_status = _mod._set_cv_status
_merge_rome_codes = _mod._merge_rome_codes
_get_profile_intent = _mod._get_profile_intent
_analyze_cv_quality = _mod._analyze_cv_quality
_upsert_cv_analysis = _mod._upsert_cv_analysis
_run_quality_analysis = _mod._run_quality_analysis

_TEST_REFERENTIEL: dict[str, str] = {
    "M1805": "Études et développement informatique",
    "M1802": "Expertise et support en systèmes d'information",
    "M1804": "Études et développement de progiciels",
}


def _session_cm(session: MagicMock):
    """Return a contextmanager-compatible callable that yields the given session."""
    @contextmanager
    def _cm():
        yield session
    return _cm


def _receive_message_cm(payload: dict):
    """Return a receive_message-compatible callable (takes a queue name) yielding payload."""
    @contextmanager
    def _cm(_queue_name):
        yield payload
    return _cm


@pytest.fixture(autouse=True)
def patch_referentiel(mocker):
    """Replace the live ROME referential with a minimal test dict for all tests."""
    mocker.patch.object(_mod, "ROME_REFERENTIEL", _TEST_REFERENTIEL)


# ---------------------------------------------------------------------------
# _extract_rome_codes
# ---------------------------------------------------------------------------


class TestExtractRomeCodes:
    def test_returns_valid_codes_on_first_attempt(self, mocker):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"rome_codes": ["M1805", "M1802"]}'
        mocker.patch.object(
            _mod._openai_client.chat.completions, "create", return_value=mock_response
        )

        result = _extract_rome_codes("cv text")

        assert result == [
            {"code": "M1805", "label": "Études et développement informatique"},
            {"code": "M1802", "label": "Expertise et support en systèmes d'information"},
        ]

    def test_retries_on_json_decode_error_then_succeeds(self, mocker):
        bad = MagicMock()
        bad.choices[0].message.content = "not valid json"
        good = MagicMock()
        good.choices[0].message.content = '{"rome_codes": ["M1805"]}'
        mock_create = mocker.patch.object(
            _mod._openai_client.chat.completions, "create", side_effect=[bad, good]
        )
        mocker.patch.object(_mod, "time", MagicMock())

        result = _extract_rome_codes("cv text")

        assert result == [{"code": "M1805", "label": "Études et développement informatique"}]
        assert mock_create.call_count == 2

    def test_filters_codes_not_matching_pattern(self, mocker):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = (
            '{"rome_codes": ["INVALID", "12345", "ab123"]}'
        )
        mocker.patch.object(
            _mod._openai_client.chat.completions, "create", return_value=mock_response
        )
        mocker.patch.object(_mod, "time", MagicMock())

        with pytest.raises(ValueError):
            _extract_rome_codes("cv text")

    def test_raises_value_error_after_max_attempts_with_empty_list(self, mocker):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"rome_codes": []}'
        mock_create = mocker.patch.object(
            _mod._openai_client.chat.completions, "create", return_value=mock_response
        )
        mocker.patch.object(_mod, "time", MagicMock())

        with pytest.raises(ValueError):
            _extract_rome_codes("cv text")

        assert mock_create.call_count == _mod.MAX_ATTEMPTS

    def test_reraises_openai_error_immediately_without_retry(self, mocker):
        mock_create = mocker.patch.object(
            _mod._openai_client.chat.completions,
            "create",
            side_effect=OpenAIError("API failure"),
        )

        with pytest.raises(OpenAIError):
            _extract_rome_codes("cv text")

        assert mock_create.call_count == 1

    def test_filters_codes_absent_from_referentiel(self, mocker):
        mock_response = MagicMock()
        # Z9999 matches the pattern but is not in _TEST_REFERENTIEL
        mock_response.choices[0].message.content = (
            '{"rome_codes": ["Z9999", "M1805"]}'
        )
        mocker.patch.object(
            _mod._openai_client.chat.completions, "create", return_value=mock_response
        )

        result = _extract_rome_codes("cv text")

        assert len(result) == 1
        assert result[0]["code"] == "M1805"


# ---------------------------------------------------------------------------
# _get_cv_text
# ---------------------------------------------------------------------------


class TestGetCvText:
    def test_returns_text_and_user_id_when_cv_found(self, mocker):
        mock_session = MagicMock()
        mock_session.execute.return_value.one_or_none.return_value = (
            "extracted cv text",
            "user-123",
        )
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        text, user_id = _get_cv_text("cv-uuid-1")

        assert text == "extracted cv text"
        assert user_id == "user-123"

    def test_raises_value_error_when_cv_not_found(self, mocker):
        mock_session = MagicMock()
        mock_session.execute.return_value.one_or_none.return_value = None
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        with pytest.raises(ValueError, match="CV cv-missing not found"):
            _get_cv_text("cv-missing")

    def test_reraises_sqlalchemy_error(self, mocker):
        mock_session = MagicMock()
        mock_session.execute.side_effect = SQLAlchemyError("DB error")
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        with pytest.raises(SQLAlchemyError):
            _get_cv_text("cv-uuid-1")


# ---------------------------------------------------------------------------
# _set_cv_status
# ---------------------------------------------------------------------------


class TestSetCvStatus:
    def test_calls_execute_and_commit(self, mocker):
        mock_session = MagicMock()
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        _set_cv_status("cv-uuid-1", "done")

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_reraises_sqlalchemy_error(self, mocker):
        mock_session = MagicMock()
        mock_session.execute.side_effect = SQLAlchemyError("DB error")
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        with pytest.raises(SQLAlchemyError):
            _set_cv_status("cv-uuid-1", "error")


# ---------------------------------------------------------------------------
# _merge_rome_codes
# ---------------------------------------------------------------------------


class TestMergeRomeCodes:
    def test_merges_new_code_into_empty_profile(self, mocker):
        mock_profile = MagicMock()
        mock_profile.rome_codes = {}
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_profile
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        _merge_rome_codes(
            "user-123",
            "cv-uuid-1",
            [{"code": "M1805", "label": "Dev info"}],
        )

        assert "M1805" in mock_profile.rome_codes
        assert "cv-uuid-1" in mock_profile.rome_codes["M1805"]["cv_ids"]
        mock_session.commit.assert_called_once()

    def test_does_not_duplicate_cv_id_on_second_call(self, mocker):
        mock_profile = MagicMock()
        mock_profile.rome_codes = {
            "M1805": {"cv_ids": ["cv-uuid-1"], "label": "Dev info"}
        }
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_profile
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        _merge_rome_codes(
            "user-123",
            "cv-uuid-1",
            [{"code": "M1805", "label": "Dev info"}],
        )

        assert mock_profile.rome_codes["M1805"]["cv_ids"].count("cv-uuid-1") == 1

    def test_appends_new_cv_id_to_existing_code(self, mocker):
        mock_profile = MagicMock()
        mock_profile.rome_codes = {
            "M1805": {"cv_ids": ["cv-uuid-1"], "label": "Dev info"}
        }
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_profile
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        _merge_rome_codes(
            "user-123",
            "cv-uuid-2",
            [{"code": "M1805", "label": "Dev info"}],
        )

        assert "cv-uuid-2" in mock_profile.rome_codes["M1805"]["cv_ids"]
        assert "cv-uuid-1" in mock_profile.rome_codes["M1805"]["cv_ids"]

    def test_raises_value_error_when_profile_not_found(self, mocker):
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        with pytest.raises(ValueError, match="UserProfile not found"):
            _merge_rome_codes(
                "user-missing",
                "cv-uuid-1",
                [{"code": "M1805", "label": "Dev info"}],
            )

    def test_reraises_sqlalchemy_error(self, mocker):
        mock_session = MagicMock()
        mock_session.execute.side_effect = SQLAlchemyError("DB error")
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        with pytest.raises(SQLAlchemyError):
            _merge_rome_codes(
                "user-123",
                "cv-uuid-1",
                [{"code": "M1805", "label": "Dev info"}],
            )


# ---------------------------------------------------------------------------
# _get_profile_intent
# ---------------------------------------------------------------------------


class TestGetProfileIntent:
    def test_returns_intent_fields_when_profile_exists(self, mocker):
        mock_session = MagicMock()
        mock_session.execute.return_value.one_or_none.return_value = (
            "2-5",
            "Recherche un poste cloud",
        )
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        experience_level, candidate_description = _get_profile_intent("user-123")

        assert experience_level == "2-5"
        assert candidate_description == "Recherche un poste cloud"

    def test_returns_none_tuple_when_no_profile(self, mocker):
        mock_session = MagicMock()
        mock_session.execute.return_value.one_or_none.return_value = None
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        assert _get_profile_intent("user-missing") == (None, None)

    def test_reraises_sqlalchemy_error(self, mocker):
        mock_session = MagicMock()
        mock_session.execute.side_effect = SQLAlchemyError("DB error")
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        with pytest.raises(SQLAlchemyError):
            _get_profile_intent("user-123")


# ---------------------------------------------------------------------------
# _analyze_cv_quality
# ---------------------------------------------------------------------------

_QUALITY_JSON = (
    '{"ats_score": 72, '
    '"synthese": "Un CV bien structuré, avec une reconversion cohérente vers le cloud.", '
    '"points_forts": ["Structure claire"], '
    '"points_faibles": ["Objectif absent"], "suggestions": ["Ajouter un titre"], '
    '"coherence_intention": "Cohérent avec le profil senior."}'
)


class TestAnalyzeCvQuality:
    def test_returns_parsed_result_on_valid_json(self, mocker):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = _QUALITY_JSON
        mocker.patch.object(
            _mod._openai_client.chat.completions, "create", return_value=mock_response
        )

        result = _analyze_cv_quality("cv text", "5+", "Recherche un poste cloud")

        assert result == {
            "ats_score": 72,
            "synthese": "Un CV bien structuré, avec une reconversion cohérente vers le cloud.",
            "points_forts": ["Structure claire"],
            "points_faibles": ["Objectif absent"],
            "suggestions": ["Ajouter un titre"],
            "coherence_intention": "Cohérent avec le profil senior.",
        }

    def test_retries_on_invalid_json_then_succeeds(self, mocker):
        bad = MagicMock()
        bad.choices[0].message.content = "not valid json"
        good = MagicMock()
        good.choices[0].message.content = _QUALITY_JSON
        mock_create = mocker.patch.object(
            _mod._openai_client.chat.completions, "create", side_effect=[bad, good]
        )
        mocker.patch.object(_mod, "time", MagicMock())

        result = _analyze_cv_quality("cv text", None, None)

        assert result["ats_score"] == 72
        assert mock_create.call_count == 2

    def test_clamps_ats_score_out_of_bounds(self, mocker):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = (
            '{"ats_score": 150, "points_forts": [], "points_faibles": [], '
            '"suggestions": [], "coherence_intention": ""}'
        )
        mocker.patch.object(
            _mod._openai_client.chat.completions, "create", return_value=mock_response
        )

        assert _analyze_cv_quality("cv text", None, None)["ats_score"] == 100

    def test_raises_value_error_after_max_attempts(self, mocker):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "never valid json"
        mock_create = mocker.patch.object(
            _mod._openai_client.chat.completions, "create", return_value=mock_response
        )
        mocker.patch.object(_mod, "time", MagicMock())

        with pytest.raises(ValueError):
            _analyze_cv_quality("cv text", None, None)

        assert mock_create.call_count == _mod.MAX_ATTEMPTS

    def test_reraises_openai_error_immediately_without_retry(self, mocker):
        mock_create = mocker.patch.object(
            _mod._openai_client.chat.completions,
            "create",
            side_effect=OpenAIError("API failure"),
        )

        with pytest.raises(OpenAIError):
            _analyze_cv_quality("cv text", "0-2", None)

        assert mock_create.call_count == 1


# ---------------------------------------------------------------------------
# _upsert_cv_analysis
# ---------------------------------------------------------------------------


class TestUpsertCvAnalysis:
    def _run(self, mocker, status: str, **fields) -> tuple[MagicMock, MagicMock]:
        """Run _upsert_cv_analysis with pg_insert and the session mocked."""
        mock_pg_insert = mocker.patch.object(_mod, "pg_insert")
        mock_session = MagicMock()
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        _upsert_cv_analysis("cv-uuid-1", status, **fields)

        return mock_pg_insert, mock_session

    def test_sets_completed_at_for_done(self, mocker):
        mock_pg_insert, mock_session = self._run(mocker, "done", ats_score=72)

        values_kwargs = mock_pg_insert.return_value.values.call_args.kwargs
        assert values_kwargs["status"] == "done"
        assert values_kwargs["ats_score"] == 72
        assert values_kwargs["completed_at"] is not None
        set_kwargs = (
            mock_pg_insert.return_value.values.return_value.on_conflict_do_update.call_args.kwargs
        )
        assert "completed_at" in set_kwargs["set_"]
        mock_session.commit.assert_called_once()

    def test_sets_completed_at_for_error(self, mocker):
        mock_pg_insert, _ = self._run(mocker, "error")

        values_kwargs = mock_pg_insert.return_value.values.call_args.kwargs
        assert "completed_at" in values_kwargs

    def test_does_not_set_completed_at_for_processing(self, mocker):
        mock_pg_insert, mock_session = self._run(mocker, "processing")

        values_kwargs = mock_pg_insert.return_value.values.call_args.kwargs
        assert "completed_at" not in values_kwargs
        set_kwargs = (
            mock_pg_insert.return_value.values.return_value.on_conflict_do_update.call_args.kwargs
        )
        assert "completed_at" not in set_kwargs["set_"]
        mock_session.commit.assert_called_once()

    def test_reraises_sqlalchemy_error(self, mocker):
        mocker.patch.object(_mod, "pg_insert")
        mock_session = MagicMock()
        mock_session.execute.side_effect = SQLAlchemyError("DB error")
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        with pytest.raises(SQLAlchemyError):
            _upsert_cv_analysis("cv-uuid-1", "done")


# ---------------------------------------------------------------------------
# _run_quality_analysis
# ---------------------------------------------------------------------------


class TestRunQualityAnalysis:
    def test_writes_done_on_success(self, mocker):
        mock_upsert = mocker.patch.object(_mod, "_upsert_cv_analysis")
        mocker.patch.object(_mod, "_get_profile_intent", return_value=("2-5", "desc"))
        mocker.patch.object(
            _mod, "_analyze_cv_quality", return_value={"ats_score": 80}
        )

        _run_quality_analysis("cv-uuid-1", "user-123", "cv text")

        mock_upsert.assert_any_call("cv-uuid-1", "processing")
        mock_upsert.assert_any_call("cv-uuid-1", "done", ats_score=80)

    def test_writes_error_status_on_openai_failure_without_raising(self, mocker):
        mock_upsert = mocker.patch.object(_mod, "_upsert_cv_analysis")
        mocker.patch.object(_mod, "_get_profile_intent", return_value=(None, None))
        mocker.patch.object(
            _mod, "_analyze_cv_quality", side_effect=OpenAIError("API failure")
        )

        _run_quality_analysis("cv-uuid-1", "user-123", "cv text")  # must not raise

        mock_upsert.assert_any_call("cv-uuid-1", "error")

    def test_swallows_sqlalchemy_error_when_writing_error_status(self, mocker):
        mock_upsert = mocker.patch.object(
            _mod,
            "_upsert_cv_analysis",
            side_effect=[None, SQLAlchemyError("DB down")],
        )
        mocker.patch.object(_mod, "_get_profile_intent", return_value=(None, None))
        mocker.patch.object(
            _mod, "_analyze_cv_quality", side_effect=OpenAIError("API failure")
        )

        _run_quality_analysis("cv-uuid-1", "user-123", "cv text")  # must not raise

        assert mock_upsert.call_count == 2


# ---------------------------------------------------------------------------
# main() — retry_quality_only branch
# ---------------------------------------------------------------------------


class TestMainRetryQualityOnly:
    def _run_main_with_payload(self, mocker, payload: dict):
        mocker.patch.object(_mod, "configure_telemetry")
        mocker.patch.object(_mod, "run_migrations")
        mocker.patch.object(_mod, "receive_message", _receive_message_cm(payload))
        return mocker.patch.object(_mod, "_run_quality_analysis")

    def test_retry_only_runs_quality_analysis_not_rome(self, mocker):
        mock_run_quality = self._run_main_with_payload(
            mocker, {"cv_id": "cv-uuid-1", "retry_quality_only": True}
        )
        mocker.patch.object(_mod, "_get_cv_text", return_value=("cv text", "user-123"))
        mock_set_status = mocker.patch.object(_mod, "_set_cv_status")
        mock_extract = mocker.patch.object(_mod, "_extract_rome_codes")

        _mod.main()

        mock_run_quality.assert_called_once_with("cv-uuid-1", "user-123", "cv text")
        mock_extract.assert_not_called()
        mock_set_status.assert_not_called()

    def test_retry_only_skips_cleanly_when_cv_deleted(self, mocker):
        mock_run_quality = self._run_main_with_payload(
            mocker, {"cv_id": "cv-missing", "retry_quality_only": True}
        )
        mocker.patch.object(_mod, "_get_cv_text", side_effect=ValueError("not found"))

        _mod.main()  # must not raise

        mock_run_quality.assert_not_called()
