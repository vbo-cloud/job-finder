"""Tests for agents/offer_fetching/main.py.

Covers: _parse_experience_min_years, _upsert_offers (values wiring),
_embed_pending_offers, _dispatch_start_matching, the advisory-lock coordination
helpers (_mark_full_refresh_pending, _mark_rome_codes_pending,
_drain_pending_signal, _handle_fetch_request).

_is_scheduled_local_hour and main()'s scheduling guard moved to
agents/offer_fetch_scheduler (see test_offer_fetch_scheduler.py) when
offer_fetching became purely event-driven — see
docs/prompts/prompt-offer-fetching-event-driven-and-new-code-fetch.md.

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
from sqlalchemy.dialects import postgresql

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
_mark_full_refresh_pending = _mod._mark_full_refresh_pending
_mark_rome_codes_pending = _mod._mark_rome_codes_pending
_drain_pending_signal = _mod._drain_pending_signal
_handle_fetch_request = _mod._handle_fetch_request


def _patched_connection(mocker, conn: MagicMock) -> MagicMock:
    """Wire a mocked AUTOCOMMIT connection the way _handle_fetch_request expects it —
    same helper as tests/test_db.py's TestRunMigrations for the identical
    get_engine().connect().execution_options(...) as conn pattern."""
    conn.__enter__.return_value = conn
    conn.__exit__.return_value = False
    conn.execution_options.return_value = conn
    mock_engine = MagicMock()
    mock_engine.connect.return_value = conn
    mocker.patch.object(_mod, "get_engine", return_value=mock_engine)
    return conn


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
# _upsert_offers — offer-change invalidation (embedding + key_skills)
# ---------------------------------------------------------------------------


class TestUpsertOffersInvalidation:
    def test_embedding_and_key_skills_share_the_same_ft_updated_at_case(self, mocker):
        # pg_insert is intentionally NOT mocked here (unlike TestUpsertOffersValues)
        # so the real on_conflict_do_update statement gets built and can be
        # compiled to SQL — the only way to assert that key_skills rides the
        # existing ft_updated_at invalidation instead of a parallel mechanism.
        mock_session = MagicMock()
        mock_session.execute.return_value = []
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        _upsert_offers(
            [
                {
                    "id": "FT-1",
                    "intitule": "Ingénieur Cloud",
                    "description": "Déploiement Azure.",
                    "dateActualisation": "2026-07-10T00:00:00+00:00",
                }
            ],
            "M1805",
        )

        stmt = mock_session.execute.call_args.args[0]
        compiled = str(stmt.compile(dialect=postgresql.dialect()))
        assert "key_skills" in compiled
        assert "embedding" in compiled
        # Both columns are driven by their own CASE, each referencing
        # ft_updated_at — same mechanism, not a duplicated one.
        assert compiled.count("ft_updated_at") >= 3


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


# ---------------------------------------------------------------------------
# _mark_full_refresh_pending / _mark_rome_codes_pending / _drain_pending_signal
# ---------------------------------------------------------------------------
# Real pg_try_advisory_lock/JSONB-equivalent SQL behavior is PostgreSQL-specific and not
# simulable with a mocked session — same class of exclusion already documented for
# _get_active_rome_codes (see tests/README.md, "Intentionally excluded"). These tests only
# cover the Python-level call wiring (statements executed, commit called), not that Postgres
# actually serializes/dedupes as intended — validated manually against a real instance instead.


class TestMarkFullRefreshPending:
    def test_updates_signal_row_and_commits(self, mocker):
        mock_session = MagicMock()
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        _mark_full_refresh_pending()

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()


class TestMarkRomeCodesPending:
    def test_no_op_on_empty_list(self, mocker):
        mock_get_session = mocker.patch.object(_mod, "get_session")

        _mark_rome_codes_pending([])

        mock_get_session.assert_not_called()

    def test_inserts_rows_and_commits_on_non_empty_list(self, mocker):
        mock_session = MagicMock()
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        _mark_rome_codes_pending(["M1805", "M1502"])

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()


class TestDrainPendingSignal:
    def test_returns_full_pending_true_and_codes_when_both_present(self, mocker):
        mock_session = MagicMock()
        update_result = MagicMock()
        update_result.first.return_value = MagicMock()  # a row -- the guarded UPDATE matched
        delete_result = [MagicMock(rome_code="M1502"), MagicMock(rome_code="M1703")]
        mock_session.execute.side_effect = [update_result, delete_result]
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        full_pending, pending_codes = _drain_pending_signal()

        assert full_pending is True
        assert pending_codes == ["M1502", "M1703"]
        mock_session.commit.assert_called_once()

    def test_returns_false_and_empty_list_when_nothing_pending(self, mocker):
        mock_session = MagicMock()
        update_result = MagicMock()
        update_result.first.return_value = None  # no row matched -- nothing was pending
        mock_session.execute.side_effect = [update_result, []]
        mocker.patch.object(_mod, "get_session", _session_cm(mock_session))

        full_pending, pending_codes = _drain_pending_signal()

        assert full_pending is False
        assert pending_codes == []


# ---------------------------------------------------------------------------
# _handle_fetch_request
# ---------------------------------------------------------------------------


class TestHandleFetchRequest:
    def test_defers_full_refresh_when_lock_busy(self, mocker):
        conn = _patched_connection(mocker, MagicMock())
        conn.execute.return_value.scalar.return_value = False  # lock not acquired
        mock_mark_full = mocker.patch.object(_mod, "_mark_full_refresh_pending")
        mock_mark_codes = mocker.patch.object(_mod, "_mark_rome_codes_pending")
        mock_run_cycle = mocker.patch.object(_mod, "_run_fetch_cycle")

        _handle_fetch_request({})

        mock_mark_full.assert_called_once()
        mock_mark_codes.assert_not_called()
        mock_run_cycle.assert_not_called()

    def test_defers_targeted_codes_when_lock_busy(self, mocker):
        conn = _patched_connection(mocker, MagicMock())
        conn.execute.return_value.scalar.return_value = False  # lock not acquired
        mock_mark_full = mocker.patch.object(_mod, "_mark_full_refresh_pending")
        mock_mark_codes = mocker.patch.object(_mod, "_mark_rome_codes_pending")
        mock_run_cycle = mocker.patch.object(_mod, "_run_fetch_cycle")

        _handle_fetch_request({"rome_codes": ["M1805"]})

        mock_mark_codes.assert_called_once_with(["M1805"])
        mock_mark_full.assert_not_called()
        mock_run_cycle.assert_not_called()

    def test_runs_cycle_and_drains_until_empty_when_lock_acquired(self, mocker):
        conn = _patched_connection(mocker, MagicMock())
        conn.execute.return_value.scalar.return_value = True  # lock acquired
        mock_run_cycle = mocker.patch.object(_mod, "_run_fetch_cycle")
        mock_drain = mocker.patch.object(
            _mod, "_drain_pending_signal", side_effect=[(True, []), (False, [])]
        )

        _handle_fetch_request({"rome_codes": ["M1805"]})

        assert mock_run_cycle.call_args_list == [
            mocker.call(["M1805"]),
            mocker.call(None),
        ]
        assert mock_drain.call_count == 2

    def test_releases_lock_even_when_run_cycle_raises(self, mocker):
        conn = _patched_connection(mocker, MagicMock())
        conn.execute.return_value.scalar.return_value = True  # lock acquired
        mocker.patch.object(_mod, "_run_fetch_cycle", side_effect=RuntimeError("boom"))

        with pytest.raises(RuntimeError):
            _handle_fetch_request({})

        unlock_calls = [c for c in conn.execute.call_args_list if "pg_advisory_unlock" in str(c.args[0])]
        assert len(unlock_calls) == 1
