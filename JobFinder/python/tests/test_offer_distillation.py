"""Tests for agents/offer_distillation/main.py.

Covers: _get_offer (not-found / already-embedded / pending), _distill
(prompt/params wiring, empty-response and API-failure handling),
_save_distillation, and main() (idempotency skip, happy path, no-message).

The module is loaded via importlib under the unique name 'offer_distillation_main'
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
    "offer_distillation_main", _AGENTS_DIR / "offer_distillation" / "main.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["offer_distillation_main"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

_get_offer = _mod._get_offer
_distill = _mod._distill
_save_distillation = _mod._save_distillation


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


# ---------------------------------------------------------------------------
# _get_offer
# ---------------------------------------------------------------------------


class TestGetOffer:
    def test_returns_title_and_description_when_pending(self, mocker):
        mock_row = MagicMock(title="Ingénieur DevOps", description="Terraform, Kubernetes", embedding=None)
        mock_session = MagicMock()
        mock_session.execute.return_value.one_or_none.return_value = mock_row
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        result = _get_offer("offer-uuid-1")

        assert result == ("Ingénieur DevOps", "Terraform, Kubernetes")

    def test_returns_none_when_offer_not_found(self, mocker):
        mock_session = MagicMock()
        mock_session.execute.return_value.one_or_none.return_value = None
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        assert _get_offer("offer-missing") is None

    def test_returns_none_when_already_embedded(self, mocker):
        mock_row = MagicMock(title="t", description="d", embedding=[0.1, 0.2])
        mock_session = MagicMock()
        mock_session.execute.return_value.one_or_none.return_value = mock_row
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        assert _get_offer("offer-uuid-1") is None

    def test_reraises_sqlalchemy_error(self, mocker):
        mock_session = MagicMock()
        mock_session.execute.side_effect = SQLAlchemyError("DB error")
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        with pytest.raises(SQLAlchemyError):
            _get_offer("offer-uuid-1")


# ---------------------------------------------------------------------------
# _distill
# ---------------------------------------------------------------------------


class TestDistill:
    def test_returns_stripped_content_on_success(self, mocker):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "  opérer des pipelines CI/CD GitLab\n  "
        mock_create = mocker.patch.object(
            _mod._openai_client.chat.completions, "create", return_value=mock_response
        )

        result = _distill("titre\n\ndescription")

        assert result == "opérer des pipelines CI/CD GitLab"
        kwargs = mock_create.call_args.kwargs
        assert kwargs["temperature"] == _mod.ANALYSIS_TEMPERATURE
        assert kwargs["seed"] == _mod.ANALYSIS_SEED
        assert kwargs["messages"][0]["content"] == _mod.OFFER_DISTILLATION_SYSTEM_PROMPT

    def test_raises_on_empty_response(self, mocker):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "   "
        mocker.patch.object(
            _mod._openai_client.chat.completions, "create", return_value=mock_response
        )

        with pytest.raises(OpenAIError):
            _distill("titre\n\ndescription")

    def test_reraises_openai_error_from_api_call(self, mocker):
        mocker.patch.object(
            _mod._openai_client.chat.completions,
            "create",
            side_effect=OpenAIError("API failure"),
        )

        with pytest.raises(OpenAIError):
            _distill("titre\n\ndescription")


# ---------------------------------------------------------------------------
# _save_distillation
# ---------------------------------------------------------------------------


class TestSaveDistillation:
    def test_writes_distilled_skills_and_embedding_then_commits(self, mocker):
        mock_session = MagicMock()
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        _save_distillation("offer-uuid-1", "opérer des pipelines CI/CD", [0.1, 0.2])

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_reraises_sqlalchemy_error(self, mocker):
        mock_session = MagicMock()
        mock_session.execute.side_effect = SQLAlchemyError("DB error")
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        with pytest.raises(SQLAlchemyError):
            _save_distillation("offer-uuid-1", "text", [0.1])


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


class TestMain:
    def _run_main_with_payload(self, mocker, payload: dict):
        mocker.patch.object(_mod, "configure_telemetry")
        mocker.patch.object(_mod, "run_migrations")
        mocker.patch.object(_mod, "receive_message", _receive_message_cm(payload))

    def test_skips_cleanly_when_already_embedded_or_deleted(self, mocker):
        self._run_main_with_payload(mocker, {"offer_id": "offer-uuid-1"})
        mocker.patch.object(_mod, "_get_offer", return_value=None)
        mock_distill = mocker.patch.object(_mod, "_distill")
        mock_embed = mocker.patch.object(_mod, "embed")
        mock_save = mocker.patch.object(_mod, "_save_distillation")

        _mod.main()  # must not raise

        mock_distill.assert_not_called()
        mock_embed.assert_not_called()
        mock_save.assert_not_called()

    def test_distills_embeds_and_saves_on_happy_path(self, mocker):
        self._run_main_with_payload(mocker, {"offer_id": "offer-uuid-1"})
        mocker.patch.object(_mod, "_get_offer", return_value=("Titre", "Description"))
        mock_distill = mocker.patch.object(_mod, "_distill", return_value="opérer Terraform")
        mock_embed = mocker.patch.object(_mod, "embed", return_value=[[0.1, 0.2]])
        mock_save = mocker.patch.object(_mod, "_save_distillation")

        _mod.main()

        mock_distill.assert_called_once_with("Titre\n\nDescription")
        mock_embed.assert_called_once_with(["opérer Terraform"])
        mock_save.assert_called_once_with("offer-uuid-1", "opérer Terraform", [0.1, 0.2])

    def test_no_message_does_not_raise(self, mocker):
        mocker.patch.object(_mod, "configure_telemetry")
        mocker.patch.object(_mod, "run_migrations")

        @contextmanager
        def _empty_queue(_queue_name):
            # Mirrors shared/bus.py::receive_message on an empty queue: the
            # generator returns without yielding, which contextlib surfaces
            # to the caller as RuntimeError.
            if False:
                yield  # pragma: no cover — makes this a generator function
            return

        mocker.patch.object(_mod, "receive_message", _empty_queue)

        _mod.main()  # must not raise
