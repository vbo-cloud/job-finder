"""Tests for agents/webapp/routers/matches.py.

A minimal FastAPI test app is created here (no lifespan, no run_migrations)
with dependency overrides for get_current_user and get_db.

Covers: GET /matches, GET /matches/cv/{cv_id},
POST /matches/{cv_id}/offers/{offer_id}/analyze.
"""
import re
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

_PYTHON_DIR = Path(__file__).parent.parent
_WEBAPP_DIR = _PYTHON_DIR / "agents" / "webapp"
for _d in [str(_PYTHON_DIR), str(_WEBAPP_DIR)]:
    if _d not in sys.path:
        sys.path.insert(0, _d)

from auth import get_current_user  # noqa: E402
from dependencies import get_db  # noqa: E402
from routers import matches as matches_router_module  # noqa: E402
from routers.matches import commune_zone_condition, router  # noqa: E402

TEST_USER_ID = "test-user-abc123"
TEST_CV_ID = uuid.uuid4()


def _make_offer(commune: str | None = "75101", department: str | None = None) -> MagicMock:
    offer = MagicMock()
    offer.id = uuid.uuid4()
    offer.ft_id = "FT-001"
    offer.title = "Développeur Python"
    offer.company = "ACME"
    offer.location = "Paris (75)"
    offer.commune = commune
    offer.department = department
    offer.contract_type = "CDI"
    offer.description = "Description complète de l'offre de test."
    offer.salary = None
    offer.rome_code = "M1805"
    offer.skills = []
    offer.expires_at = None
    return offer


def _make_match(score: float = 0.85) -> MagicMock:
    match = MagicMock()
    match.score = score
    match.offer = _make_offer()
    match.analysis = None
    return match


def _make_analysis(status: str = "done") -> MagicMock:
    analysis = MagicMock()
    analysis.status = status
    analysis.matched_skills = ["Python", "Docker"]
    analysis.points_forts = ["Expérience solide"]
    analysis.points_amelioration = [
        {"constat": "Certifications absentes", "suggestion_concrete": "Passer AZ-104."}
    ]
    analysis.synthese = "Profil solide sur les compétences cœur."
    analysis.verdict = "À tenter"
    analysis.company_summary = None
    analysis.mission_summary = "Développement backend Python."
    analysis.why_good_fit_for_user = "Poste aligné avec votre recherche cloud."
    analysis.why_good_candidate = "4 ans d'expérience Python."
    analysis.score_explanation = "Forte couverture des compétences demandées."
    analysis.questions_entretien_potentielles = ["Comment gérez-vous les migrations ?"]
    return analysis


def _make_profile(
    rome_codes: dict | None = None, commune_codes: list[str] | None = None
) -> MagicMock:
    profile = MagicMock()
    profile.rome_codes = rome_codes or {
        "M1805": {"cv_ids": [str(TEST_CV_ID)], "label": "Dev info"}
    }
    profile.commune_codes = commune_codes or []
    return profile


@pytest.fixture()
def mock_session() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def test_client(mock_session) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: TEST_USER_ID
    app.dependency_overrides[get_db] = lambda: (yield mock_session)
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# GET /matches
# ---------------------------------------------------------------------------


class TestGetMatches:
    def test_returns_rome_codes_and_matches_when_profile_exists(
        self, test_client, mock_session
    ):
        profile = _make_profile()
        match = _make_match(0.9)
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": profile}),
            MagicMock(**{"scalars.return_value.all.return_value": [match]}),
        ]

        resp = test_client.get("/matches")

        assert resp.status_code == 200
        body = resp.json()
        assert "M1805" in body["rome_codes"]
        assert len(body["matches"]) == 1
        assert body["matches"][0]["score"] == pytest.approx(0.9)

    def test_returns_empty_rome_codes_when_no_profile(self, test_client, mock_session):
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": None}),
            MagicMock(**{"scalars.return_value.all.return_value": []}),
        ]

        resp = test_client.get("/matches")

        assert resp.status_code == 200
        body = resp.json()
        assert body["rome_codes"] == {}
        assert body["matches"] == []

    def test_returns_empty_matches_list_when_no_matches(self, test_client, mock_session):
        profile = _make_profile()
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": profile}),
            MagicMock(**{"scalars.return_value.all.return_value": []}),
        ]

        resp = test_client.get("/matches")

        assert resp.status_code == 200
        assert resp.json()["matches"] == []

    def test_returns_500_on_db_error(self, test_client, mock_session):
        mock_session.execute.side_effect = SQLAlchemyError("DB error")

        resp = test_client.get("/matches")

        assert resp.status_code == 500

    def test_serializes_null_analysis(self, test_client, mock_session):
        profile = _make_profile()
        match = _make_match(0.9)
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": profile}),
            MagicMock(**{"scalars.return_value.all.return_value": [match]}),
        ]

        resp = test_client.get("/matches")

        assert resp.status_code == 200
        assert resp.json()["matches"][0]["analysis"] is None

    def test_serializes_non_null_analysis(self, test_client, mock_session):
        profile = _make_profile()
        match = _make_match(0.9)
        match.analysis = _make_analysis()
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": profile}),
            MagicMock(**{"scalars.return_value.all.return_value": [match]}),
        ]

        resp = test_client.get("/matches")

        assert resp.status_code == 200
        analysis = resp.json()["matches"][0]["analysis"]
        assert analysis["status"] == "done"
        assert analysis["matched_skills"] == ["Python", "Docker"]
        assert analysis["points_forts"] == ["Expérience solide"]
        assert analysis["points_amelioration"] == [
            {"constat": "Certifications absentes", "suggestion_concrete": "Passer AZ-104."}
        ]
        assert analysis["synthese"] == "Profil solide sur les compétences cœur."
        assert analysis["verdict"] == "À tenter"
        assert analysis["company_summary"] is None
        assert analysis["score_explanation"] == "Forte couverture des compétences demandées."
        assert analysis["questions_entretien_potentielles"] == [
            "Comment gérez-vous les migrations ?"
        ]

    def test_serializes_legacy_analysis_with_plain_string_points(self, test_client, mock_session):
        # Rows analysed before migration 020 store points_amelioration items as
        # plain strings — the schema must coerce them to PointAmelioration dicts.
        profile = _make_profile()
        match = _make_match(0.9)
        analysis = _make_analysis()
        analysis.points_amelioration = ["Certifications absentes"]
        match.analysis = analysis
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": profile}),
            MagicMock(**{"scalars.return_value.all.return_value": [match]}),
        ]

        resp = test_client.get("/matches")

        assert resp.status_code == 200
        body = resp.json()["matches"][0]["analysis"]
        assert body["points_amelioration"] == [
            {"constat": "Certifications absentes", "suggestion_concrete": None}
        ]

    def test_serializes_pending_analysis_with_null_lists(self, test_client, mock_session):
        # The agent has not run yet: JSONB list columns are still NULL in the
        # row created by the enqueuer — the schema must coerce them to [].
        profile = _make_profile()
        match = _make_match(0.9)
        analysis = _make_analysis(status="pending")
        analysis.matched_skills = []
        analysis.points_forts = None
        analysis.points_amelioration = None
        analysis.synthese = None
        match.analysis = analysis
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": profile}),
            MagicMock(**{"scalars.return_value.all.return_value": [match]}),
        ]

        resp = test_client.get("/matches")

        assert resp.status_code == 200
        body = resp.json()["matches"][0]["analysis"]
        assert body["status"] == "pending"
        assert body["points_forts"] == []
        assert body["points_amelioration"] == []

    def test_filters_by_commune_when_zone_is_defined(self, test_client, mock_session):
        profile = _make_profile(commune_codes=["75101", "75102"])
        match = _make_match(0.9)
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": profile}),
            MagicMock(**{"scalars.return_value.all.return_value": [match]}),
        ]

        resp = test_client.get("/matches")

        assert resp.status_code == 200
        # No real DB behind the mock — validate the geographic filter by
        # inspecting the compiled statement passed to session.execute.
        stmt = str(mock_session.execute.call_args_list[1].args[0])
        assert "JOIN offers" in stmt
        assert "offers.commune IN" in stmt

    def test_no_commune_filter_when_zone_is_empty(self, test_client, mock_session):
        profile = _make_profile(commune_codes=[])
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": profile}),
            MagicMock(**{"scalars.return_value.all.return_value": []}),
        ]

        resp = test_client.get("/matches")

        assert resp.status_code == 200
        stmt = str(mock_session.execute.call_args_list[1].args[0])
        assert "offers.commune" not in stmt

    def test_department_token_filters_by_code_prefix(self, test_client, mock_session):
        profile = _make_profile(commune_codes=["dept:74", "75101"])
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": profile}),
            MagicMock(**{"scalars.return_value.all.return_value": []}),
        ]

        resp = test_client.get("/matches")

        assert resp.status_code == 200
        # "dept:74" compiles to a LIKE prefix condition, plain codes to IN —
        # both OR-ed inside the same geographic filter.
        stmt = str(mock_session.execute.call_args_list[1].args[0])
        assert "offers.commune IN" in stmt
        assert "offers.commune LIKE" in stmt
        assert " OR " in stmt

    def test_commune_less_offers_survive_the_zone_filter(self, test_client, mock_session):
        profile = _make_profile(commune_codes=["75101"])
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": profile}),
            MagicMock(**{"scalars.return_value.all.return_value": []}),
        ]

        resp = test_client.get("/matches")

        assert resp.status_code == 200
        # Offers with no commune code fall back to a department match (or the
        # unconditional bypass when the department is also unknown) — both
        # gated behind "commune IS NULL", covered precisely in
        # TestCommuneZoneConditionDepartmentFallback below.
        stmt = str(mock_session.execute.call_args_list[1].args[0])
        assert "offers.commune IS NULL" in stmt
        assert "offers.commune IN" in stmt

    def test_no_commune_filter_when_no_profile(self, test_client, mock_session):
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": None}),
            MagicMock(**{"scalars.return_value.all.return_value": []}),
        ]

        resp = test_client.get("/matches")

        assert resp.status_code == 200
        stmt = str(mock_session.execute.call_args_list[1].args[0])
        assert "offers.commune" not in stmt


# ---------------------------------------------------------------------------
# GET /matches/cv/{cv_id}
# ---------------------------------------------------------------------------


class TestGetMatchesForCv:
    def test_returns_matches_when_cv_found(self, test_client, mock_session):
        cv = MagicMock()
        cv.id = TEST_CV_ID
        profile = _make_profile()
        match = _make_match(0.75)
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": cv}),
            MagicMock(**{"scalar_one_or_none.return_value": profile}),
            MagicMock(**{"scalars.return_value.all.return_value": [match]}),
        ]

        resp = test_client.get(f"/matches/cv/{TEST_CV_ID}")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["matches"]) == 1

    def test_filters_by_commune_when_zone_is_defined(self, test_client, mock_session):
        cv = MagicMock()
        cv.id = TEST_CV_ID
        profile = _make_profile(commune_codes=["13201"])
        match = _make_match(0.75)
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": cv}),
            MagicMock(**{"scalar_one_or_none.return_value": profile}),
            MagicMock(**{"scalars.return_value.all.return_value": [match]}),
        ]

        resp = test_client.get(f"/matches/cv/{TEST_CV_ID}")

        assert resp.status_code == 200
        stmt = str(mock_session.execute.call_args_list[2].args[0])
        assert "JOIN offers" in stmt
        assert "offers.commune IN" in stmt

    def test_no_commune_filter_when_zone_is_empty(self, test_client, mock_session):
        cv = MagicMock()
        cv.id = TEST_CV_ID
        profile = _make_profile(commune_codes=[])
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": cv}),
            MagicMock(**{"scalar_one_or_none.return_value": profile}),
            MagicMock(**{"scalars.return_value.all.return_value": []}),
        ]

        resp = test_client.get(f"/matches/cv/{TEST_CV_ID}")

        assert resp.status_code == 200
        stmt = str(mock_session.execute.call_args_list[2].args[0])
        assert "offers.commune" not in stmt

    def test_returns_404_when_cv_not_found_or_not_owned(self, test_client, mock_session):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        resp = test_client.get(f"/matches/cv/{uuid.uuid4()}")

        assert resp.status_code == 404

    def test_returns_500_on_db_error(self, test_client, mock_session):
        mock_session.execute.side_effect = SQLAlchemyError("DB error")

        resp = test_client.get(f"/matches/cv/{TEST_CV_ID}")

        assert resp.status_code == 500

    def test_serializes_non_null_analysis(self, test_client, mock_session):
        cv = MagicMock()
        cv.id = TEST_CV_ID
        profile = _make_profile()
        match = _make_match(0.75)
        match.analysis = _make_analysis()
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": cv}),
            MagicMock(**{"scalar_one_or_none.return_value": profile}),
            MagicMock(**{"scalars.return_value.all.return_value": [match]}),
        ]

        resp = test_client.get(f"/matches/cv/{TEST_CV_ID}")

        assert resp.status_code == 200
        analysis = resp.json()["matches"][0]["analysis"]
        assert analysis["status"] == "done"
        assert analysis["matched_skills"] == ["Python", "Docker"]


# ---------------------------------------------------------------------------
# POST /matches/{cv_id}/offers/{offer_id}/analyze
# ---------------------------------------------------------------------------


class TestRequestMatchAnalysis:
    TEST_OFFER_ID = uuid.uuid4()
    TEST_MATCH_ID = uuid.uuid4()

    def _make_owned_match(self) -> MagicMock:
        match = MagicMock()
        match.id = self.TEST_MATCH_ID
        return match

    def test_returns_404_when_match_not_found(self, test_client, mock_session, mocker):
        mock_send = mocker.patch.object(matches_router_module, "send_message")
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        resp = test_client.post(f"/matches/{TEST_CV_ID}/offers/{self.TEST_OFFER_ID}/analyze")

        assert resp.status_code == 404
        mock_send.assert_not_called()

    def test_returns_402_when_no_credits_remaining(self, test_client, mock_session, mocker):
        mock_send = mocker.patch.object(matches_router_module, "send_message")
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": self._make_owned_match()}),
            MagicMock(rowcount=0),  # conditional credit decrement matched no row
        ]

        resp = test_client.post(f"/matches/{TEST_CV_ID}/offers/{self.TEST_OFFER_ID}/analyze")

        assert resp.status_code == 402
        mock_send.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_happy_path_decrements_credit_and_dispatches(
        self, test_client, mock_session, mocker
    ):
        mock_send = mocker.patch.object(matches_router_module, "send_message")
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": self._make_owned_match()}),
            MagicMock(rowcount=1),  # credit decremented
            MagicMock(),            # match_analyses upsert
        ]

        resp = test_client.post(f"/matches/{TEST_CV_ID}/offers/{self.TEST_OFFER_ID}/analyze")

        assert resp.status_code == 202
        mock_session.commit.assert_called_once()
        mock_send.assert_called_once_with(
            "match-analysis", {"match_id": str(self.TEST_MATCH_ID)}
        )
        # The credit decrement is a conditional UPDATE on user_profiles.
        stmt = str(mock_session.execute.call_args_list[1].args[0])
        assert "UPDATE user_profiles" in stmt
        assert "analysis_credits_remaining" in stmt

    def test_returns_202_even_if_dispatch_fails(self, test_client, mock_session, mocker):
        from azure.servicebus.exceptions import ServiceBusError

        mocker.patch.object(
            matches_router_module, "send_message", side_effect=ServiceBusError("boom")
        )
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": self._make_owned_match()}),
            MagicMock(rowcount=1),
            MagicMock(),
        ]

        resp = test_client.post(f"/matches/{TEST_CV_ID}/offers/{self.TEST_OFFER_ID}/analyze")

        assert resp.status_code == 202

    def test_returns_500_on_db_error(self, test_client, mock_session, mocker):
        mock_send = mocker.patch.object(matches_router_module, "send_message")
        mock_session.execute.side_effect = SQLAlchemyError("DB error")

        resp = test_client.post(f"/matches/{TEST_CV_ID}/offers/{self.TEST_OFFER_ID}/analyze")

        assert resp.status_code == 500
        mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# commune_zone_condition — department fallback for commune-less offers
# ---------------------------------------------------------------------------


def _compiled(commune_codes: list[str]) -> str:
    condition = commune_zone_condition(commune_codes)
    return str(condition.compile(compile_kwargs={"literal_binds": True}))


class TestCommuneZoneConditionDepartmentFallback:
    def test_offer_without_commune_included_via_department_in_zone(self):
        # Zone = commune "75101" (department "75"). An offer with no commune
        # code but department "75" must be reachable: the fallback clause
        # ORs in "offers.department IN ('75')" once the commune is unknown.
        stmt = _compiled(["75101"])
        assert "offers.department IN ('75')" in stmt

    def test_offer_without_commune_excluded_when_department_outside_zone(self):
        # Zone covers only department "75" — the department fallback set
        # never contains an unrelated department like "13" (Marseille), so
        # an offer whose department is "13" cannot match through it.
        stmt = _compiled(["75101"])
        assert "'13'" not in stmt

    def test_offer_with_neither_commune_nor_department_known_falls_to_region_check(self):
        # An offer with no commune and no department still isn't a blanket
        # bypass — it's gated by region next (test class below covers that
        # level precisely). This just confirms the department-unknown branch
        # is present at all.
        stmt = _compiled(["75101"])
        assert "offers.department IS NULL" in stmt

    def test_known_commune_outside_zone_not_rescued_by_department_match(self):
        # An offer with a precise commune outside the zone must not be
        # rescued just because its department happens to be in the zone —
        # the department fallback is gated behind "commune IS NULL", so it
        # never applies to offers with a known commune.
        stmt = _compiled(["75101"])
        assert "offers.commune IS NULL AND (offers.department IS NULL AND" in stmt
        assert "OR offers.department IN" in stmt

    def test_department_derived_from_both_codes_and_dept_tokens(self):
        stmt = _compiled(["dept:74", "75101"])
        # departments is a set — Python's iteration order for str sets isn't
        # guaranteed, so extract the IN(...) values instead of matching a
        # fixed literal order.
        match = re.search(r"offers\.department IN \(([^)]*)\)", stmt)
        assert match is not None
        values = {v.strip().strip("'") for v in match.group(1).split(",")}
        assert values == {"74", "75"}


class TestCommuneZoneConditionRegionFallback:
    def test_offer_without_commune_or_department_included_via_region_in_zone(self):
        # Zone = department "69" (Lyon, region auvergne-rhone-alpes). An
        # offer labeled with that region but no commune/department (e.g.
        # France Travail gave "Île-de-France" instead of "75 - Paris") must
        # be reachable through the region fallback.
        stmt = _compiled(["dept:69"])
        assert "offers.region IN ('auvergne-rhone-alpes')" in stmt

    def test_offer_excluded_when_region_outside_zone(self):
        # A Lyon-only zone (department 69, region auvergne-rhone-alpes) must
        # never reference an unrelated region like ile-de-france.
        stmt = _compiled(["dept:69"])
        assert "ile-de-france" not in stmt

    def test_paris_zone_derives_ile_de_france_region(self):
        stmt = _compiled(["dept:75"])
        assert "offers.region IN ('ile-de-france')" in stmt

    def test_offer_with_neither_commune_department_nor_region_always_included(self):
        # Genuinely unlocatable offers ("France", "Luxembourg" — no
        # parseable department or region) keep the final unconditional
        # bypass.
        stmt = _compiled(["dept:69"])
        assert "offers.region IS NULL" in stmt

    def test_known_department_outside_zone_not_rescued_by_region_match(self):
        # An offer with a known department outside the zone must not be
        # rescued by a region-level coincidence — the region fallback is
        # gated behind "department IS NULL", same precedence rule as
        # department under commune.
        stmt = _compiled(["dept:69"])
        assert "offers.department IS NULL AND (offers.region IS NULL OR offers.region IN" in stmt
