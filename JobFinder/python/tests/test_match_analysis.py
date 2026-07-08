"""Tests for agents/match_analysis/main.py.

Covers: _get_match_context, _analyze_match, _update_match_analysis.

The module is loaded via importlib under the unique name 'match_analysis_main'
to avoid sys.modules collision with the other agents' main.py.
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
    "match_analysis_main", _AGENTS_DIR / "match_analysis" / "main.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["match_analysis_main"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

_get_match_context = _mod._get_match_context
_analyze_match = _mod._analyze_match
_update_match_analysis = _mod._update_match_analysis


def _session_cm(session: MagicMock):
    """Return a contextmanager-compatible callable that yields the given session."""
    @contextmanager
    def _cm():
        yield session
    return _cm


def _make_context(**overrides) -> dict:
    context = {
        "cv_text": "Développeur Python avec 4 ans d'expérience.",
        "offer_title": "Développeur Python",
        "offer_company": "ACME",
        "offer_description": "Description complète de l'offre.",
        "offer_skills": ["Python", "Docker"],
        "match_score": 0.87,
        "experience_level": "2-5",
        "candidate_description": "Recherche un poste cloud",
    }
    context.update(overrides)
    return context


# ---------------------------------------------------------------------------
# _get_match_context
# ---------------------------------------------------------------------------


class TestGetMatchContext:
    def test_returns_context_when_match_found(self, mocker):
        row = MagicMock()
        row.raw_text = "cv text"
        row.title = "Développeur Python"
        row.company = "ACME"
        row.description = "Description de l'offre."
        row.skills = ["Python"]
        row.score = 0.87
        row.experience_level = "2-5"
        row.candidate_description = "Recherche cloud"
        mock_session = MagicMock()
        mock_session.execute.return_value.one_or_none.return_value = row
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        context = _get_match_context("match-uuid-1")

        assert context == {
            "cv_text": "cv text",
            "offer_title": "Développeur Python",
            "offer_company": "ACME",
            "offer_description": "Description de l'offre.",
            "offer_skills": ["Python"],
            "match_score": 0.87,
            "experience_level": "2-5",
            "candidate_description": "Recherche cloud",
        }

    def test_raises_value_error_when_match_not_found(self, mocker):
        mock_session = MagicMock()
        mock_session.execute.return_value.one_or_none.return_value = None
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        with pytest.raises(ValueError, match="Match match-missing not found"):
            _get_match_context("match-missing")

    def test_reraises_sqlalchemy_error(self, mocker):
        mock_session = MagicMock()
        mock_session.execute.side_effect = SQLAlchemyError("DB error")
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        with pytest.raises(SQLAlchemyError):
            _get_match_context("match-uuid-1")


# ---------------------------------------------------------------------------
# _analyze_match
# ---------------------------------------------------------------------------

_ANALYSIS_JSON = (
    '{"matched_skills": ["Python", "Docker"], "points_forts": ["Expérience solide"], '
    '"points_amelioration": [{"constat": "Certifications absentes", '
    '"suggestion_concrete": "Passer la certification AZ-104."}], '
    '"synthese": "Profil solide sur les compétences cœur.", '
    '"verdict": "À tenter", '
    '"company_summary": null, '
    '"mission_summary": "Développement backend Python.", '
    '"why_good_fit_for_user": "Poste aligné avec votre recherche cloud.", '
    '"why_good_candidate": "4 ans d\'expérience Python.", '
    '"score_explanation": "Le score de 87% reflète une forte couverture des compétences.", '
    '"questions_entretien_potentielles": ["Comment gérez-vous les migrations ?"]}'
)


class TestAnalyzeMatch:
    def test_returns_parsed_result_on_valid_json(self, mocker):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = _ANALYSIS_JSON
        mocker.patch.object(
            _mod._openai_client.chat.completions, "create", return_value=mock_response
        )

        result = _analyze_match(_make_context())

        assert result == {
            "matched_skills": ["Python", "Docker"],
            "points_forts": ["Expérience solide"],
            "points_amelioration": [
                {
                    "constat": "Certifications absentes",
                    "suggestion_concrete": "Passer la certification AZ-104.",
                }
            ],
            "synthese": "Profil solide sur les compétences cœur.",
            "verdict": "À tenter",
            "company_summary": None,
            "mission_summary": "Développement backend Python.",
            "why_good_fit_for_user": "Poste aligné avec votre recherche cloud.",
            "why_good_candidate": "4 ans d'expérience Python.",
            "score_explanation": "Le score de 87% reflète une forte couverture des compétences.",
            "questions_entretien_potentielles": ["Comment gérez-vous les migrations ?"],
        }

    def test_coerces_partial_points_amelioration_items(self, mocker):
        # An item without constat is dropped; a missing suggestion_concrete is
        # kept as None — same shape the API accepts for legacy pre-020 rows.
        payload = (
            '{"points_amelioration": ['
            '{"constat": "Certifications absentes", "suggestion_concrete": "Passer AZ-104."}, '
            '{"constat": "Sans suggestion"}, '
            '"un simple texte"]}'
        )
        mock_response = MagicMock()
        mock_response.choices[0].message.content = payload
        mocker.patch.object(
            _mod._openai_client.chat.completions, "create", return_value=mock_response
        )

        result = _analyze_match(_make_context())

        assert result["points_amelioration"] == [
            {"constat": "Certifications absentes", "suggestion_concrete": "Passer AZ-104."},
            {"constat": "Sans suggestion", "suggestion_concrete": None},
        ]
        # An absent synthese stays None (nullable column), never "".
        assert result["synthese"] is None

    def test_includes_match_score_in_user_content(self, mocker):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = _ANALYSIS_JSON
        mock_create = mocker.patch.object(
            _mod._openai_client.chat.completions, "create", return_value=mock_response
        )

        _analyze_match(_make_context(match_score=0.87))

        user_content = mock_create.call_args.kwargs["messages"][1]["content"]
        assert "Score de correspondance déjà calculé : 87%" in user_content

    def test_retries_on_invalid_json_then_succeeds(self, mocker):
        bad = MagicMock()
        bad.choices[0].message.content = "not valid json"
        good = MagicMock()
        good.choices[0].message.content = _ANALYSIS_JSON
        mock_create = mocker.patch.object(
            _mod._openai_client.chat.completions, "create", side_effect=[bad, good]
        )
        mocker.patch.object(_mod, "time", MagicMock())

        result = _analyze_match(_make_context())

        assert result["matched_skills"] == ["Python", "Docker"]
        assert mock_create.call_count == 2

    def test_raises_value_error_after_max_attempts(self, mocker):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "never valid json"
        mock_create = mocker.patch.object(
            _mod._openai_client.chat.completions, "create", return_value=mock_response
        )
        mocker.patch.object(_mod, "time", MagicMock())

        with pytest.raises(ValueError):
            _analyze_match(_make_context())

        assert mock_create.call_count == _mod.MAX_ATTEMPTS

    def test_reraises_openai_error_immediately_without_retry(self, mocker):
        mock_create = mocker.patch.object(
            _mod._openai_client.chat.completions,
            "create",
            side_effect=OpenAIError("API failure"),
        )

        with pytest.raises(OpenAIError):
            _analyze_match(_make_context())

        assert mock_create.call_count == 1

    def test_includes_intent_fallback_when_profile_empty(self, mocker):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = _ANALYSIS_JSON
        mock_create = mocker.patch.object(
            _mod._openai_client.chat.completions, "create", return_value=mock_response
        )

        _analyze_match(_make_context(experience_level=None, candidate_description=None))

        user_content = mock_create.call_args.kwargs["messages"][1]["content"]
        assert "Aucune intention renseignée" in user_content

    def test_truncates_cv_and_offer_text(self, mocker):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = _ANALYSIS_JSON
        mock_create = mocker.patch.object(
            _mod._openai_client.chat.completions, "create", return_value=mock_response
        )

        _analyze_match(
            _make_context(
                cv_text="x" * (_mod.CV_TEXT_MAX_CHARS + 500),
                offer_description="y" * (_mod.OFFER_TEXT_MAX_CHARS + 500),
            )
        )

        user_content = mock_create.call_args.kwargs["messages"][1]["content"]
        assert "x" * (_mod.CV_TEXT_MAX_CHARS + 1) not in user_content
        assert "y" * (_mod.OFFER_TEXT_MAX_CHARS + 1) not in user_content

    def test_pins_temperature_and_seed_for_determinism(self, mocker):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = _ANALYSIS_JSON
        mock_create = mocker.patch.object(
            _mod._openai_client.chat.completions, "create", return_value=mock_response
        )

        _analyze_match(_make_context())

        kwargs = mock_create.call_args.kwargs
        assert kwargs["temperature"] == _mod.ANALYSIS_TEMPERATURE
        assert kwargs["seed"] == _mod.ANALYSIS_SEED


# ---------------------------------------------------------------------------
# _update_match_analysis
# ---------------------------------------------------------------------------


class TestUpdateMatchAnalysis:
    def _run(self, mocker, status: str, **fields) -> MagicMock:
        mock_update = mocker.patch.object(_mod, "update")
        mock_session = MagicMock()
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        _update_match_analysis("match-uuid-1", status, **fields)

        mock_session.commit.assert_called_once()
        return mock_update.return_value.where.return_value.values

    def test_sets_completed_at_for_done(self, mocker):
        mock_values = self._run(mocker, "done", matched_skills=["Python"])

        values_kwargs = mock_values.call_args.kwargs
        assert values_kwargs["status"] == "done"
        assert values_kwargs["matched_skills"] == ["Python"]
        assert values_kwargs["completed_at"] is not None

    def test_sets_completed_at_for_error(self, mocker):
        mock_values = self._run(mocker, "error")

        assert "completed_at" in mock_values.call_args.kwargs

    def test_does_not_set_completed_at_for_processing(self, mocker):
        mock_values = self._run(mocker, "processing")

        assert "completed_at" not in mock_values.call_args.kwargs

    def test_reraises_sqlalchemy_error(self, mocker):
        mock_session = MagicMock()
        mock_session.execute.side_effect = SQLAlchemyError("DB error")
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        with pytest.raises(SQLAlchemyError):
            _update_match_analysis("match-uuid-1", "done")
