"""Tests for agents/offer_fetching/main.py.

Covers: _parse_experience_min_years, _upsert_offers (values wiring),
_embed_pending_offers, _dispatch_start_matching.

The module is loaded via importlib under the unique name 'offer_fetching_main'
to avoid sys.modules collision with the other agents' main.py. The
offer_fetching directory is added to sys.path first so the module's plain
`from ft_client import ...` resolves (same technique as test_ft_client.py).
"""
import importlib.util
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_OFFER_FETCHING_DIR = Path(__file__).parent.parent / "agents" / "offer_fetching"
if str(_OFFER_FETCHING_DIR) not in sys.path:
    sys.path.insert(0, str(_OFFER_FETCHING_DIR))

_spec = importlib.util.spec_from_file_location(
    "offer_fetching_main", _OFFER_FETCHING_DIR / "main.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["offer_fetching_main"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

_parse_experience_min_years = _mod._parse_experience_min_years
_upsert_offers = _mod._upsert_offers
_embed_pending_offers = _mod._embed_pending_offers
_dispatch_start_matching = _mod._dispatch_start_matching


def _session_cm(session: MagicMock):
    """Return a contextmanager-compatible callable that yields the given session."""
    @contextmanager
    def _cm():
        yield session
    return _cm


# ---------------------------------------------------------------------------
# _parse_experience_min_years
# ---------------------------------------------------------------------------


class TestParseExperienceMinYears:
    @pytest.mark.parametrize(
        ("libelle", "expected"),
        [
            # Formats en années — le plus courant
            ("Expérience exigée de 6 An(s)", 6),
            ("Expérience souhaitée de 2 An(s)", 2),
            ("10 An(s)", 10),
            # Format en mois — observé sur des payloads réels ("60 Mois" = 5 ans) ;
            # arrondi à l'année inférieure par design (pénalité jamais sur-estimée)
            ("Expérience exigée de 60 Mois", 5),
            ("Expérience exigée de 18 Mois", 1),
            ("Expérience exigée de 6 Mois", 0),
            # Débutant accepté — 0 an requis, quel que soit le casing
            ("Débutant accepté", 0),
            ("DÉBUTANT ACCEPTÉ", 0),
        ],
    )
    def test_parses_known_france_travail_formats(self, libelle: str, expected: int):
        assert _parse_experience_min_years(libelle) == expected

    @pytest.mark.parametrize(
        "libelle",
        [
            None,                  # champ absent du payload
            "Expérience exigée",   # durée absente — observé sur des payloads réels
            "Non renseigné",       # format inattendu — ne pas deviner
            "",
        ],
    )
    def test_returns_none_when_signal_is_absent_or_unparseable(self, libelle: str | None):
        # L'absence de donnée ne doit jamais devenir "0 an requis" — cela
        # favoriserait les offres au libellé imparsable face aux offres
        # honnêtement étiquetées débutant.
        assert _parse_experience_min_years(libelle) is None


# ---------------------------------------------------------------------------
# _upsert_offers — values wiring
# ---------------------------------------------------------------------------


class TestUpsertOffersValues:
    def test_populates_experience_min_years_from_raw_offer(self, mocker):
        mock_pg_insert = mocker.patch.object(_mod, "pg_insert")
        mock_session = MagicMock()
        mock_session.execute.return_value = []
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        _upsert_offers(
            [
                {
                    "id": "FT-1",
                    "intitule": "Ingénieur Cloud",
                    "description": "Déploiement Azure avec Terraform et Kubernetes.",
                    "experienceLibelle": "Expérience exigée de 5 An(s)",
                    "competences": [{"libelle": "Cloud computing"}],
                }
            ],
            "M1805",
        )

        values = mock_pg_insert.return_value.values.call_args.args[0]
        assert values[0]["experience_min_years"] == 5
        assert values[0]["skills"] == ["Cloud computing"]
        mock_session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# _embed_pending_offers
# ---------------------------------------------------------------------------


class _PendingRow:
    def __init__(self, id: str, title: str, description: str):
        self.id = id
        self.title = title
        self.description = description


class TestEmbedPendingOffers:
    def test_embeds_offers_with_null_embedding(self, mocker):
        mock_session = MagicMock()
        mock_session.execute.return_value.all.return_value = [
            _PendingRow("offer-uuid-1", "Ingénieur Cloud", "Déploiement Azure."),
            _PendingRow("offer-uuid-2", "Data Engineer", "Pipelines de données."),
        ]
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))
        mock_embed = mocker.patch.object(_mod, "embed", return_value=[[0.1], [0.2]])

        result = _embed_pending_offers()

        assert result == 2
        mock_embed.assert_called_once_with(
            ["Ingénieur Cloud\n\nDéploiement Azure.", "Data Engineer\n\nPipelines de données."]
        )
        mock_session.commit.assert_called_once()

    def test_does_not_call_embed_when_no_pending_offers(self, mocker):
        mock_session = MagicMock()
        mock_session.execute.return_value.all.return_value = []
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))
        mock_embed = mocker.patch.object(_mod, "embed")

        result = _embed_pending_offers()

        assert result == 0
        mock_embed.assert_not_called()


# ---------------------------------------------------------------------------
# _dispatch_start_matching
# ---------------------------------------------------------------------------


class TestDispatchStartMatching:
    def test_sends_expected_payload(self, mocker):
        mock_send = mocker.patch.object(_mod, "send_message")

        _dispatch_start_matching("2026-07-10", ["M1805"], 3, 5)

        mock_send.assert_called_once_with(
            _mod.START_MATCHING_QUEUE,
            {
                "run_date": "2026-07-10",
                "rome_codes": ["M1805"],
                "new_offers_count": 3,
                "embedded_count": 5,
                "trigger": "offer_fetching",
            },
        )

    def test_logs_and_does_not_raise_on_servicebus_error(self, mocker):
        mocker.patch.object(_mod, "send_message", side_effect=_mod.ServiceBusError("boom"))

        _dispatch_start_matching("2026-07-10", [], 0, 1)
