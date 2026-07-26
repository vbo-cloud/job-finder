"""Pydantic request and response schemas for the webapp API."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

CVStatus = Literal["pending", "processing", "done", "matched", "error"]


class ProfileUpdate(BaseModel):
    """Payload for creating or updating a user's job search profile.

    rome_codes is intentionally absent — it is managed exclusively by
    the GPT-4o-mini CV analysis agent and must never be overwritten by the user.

    Every field defaults to None (never [] or {}) so that
    model_dump(exclude_unset=True) can distinguish "field absent from the
    request" from "field sent empty" — required for PUT /profile to be a
    real partial update across the /profile and home-page callers.
    """

    commune_codes: list[str] | None = None
    experience_level: Literal["0-2", "2-5", "5+"] | None = None
    candidate_description: str | None = Field(default=None, max_length=1000)
    notification_days: list[Literal[1, 2, 3, 4, 5, 6, 7]] | None = None

    # Canonical, duplicate-free order regardless of how the caller submitted the
    # list — the frontend toggle already sends a sorted, dupe-free array, but a
    # direct API caller isn't guaranteed to, and the column has no DB-level
    # uniqueness/order constraint to fall back on.
    @field_validator("notification_days")
    @classmethod
    def _dedupe_sort_days(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return None
        return sorted(set(v))


class FeedbackCreate(BaseModel):
    """Payload for POST /feedback — user-submitted review or bug report.

    No email/name field: the recipient of the relayed email is derived
    server-side from the validated JWT (UserIdentity), never from client input.
    sentiment is the only optional field — the smiley picker is not required.
    str_strip_whitespace + min_length=1 on subject/message make "required"
    a real server-side guarantee (not just a disabled submit button on the
    client) — a whitespace-only value strips down to "" and fails validation.
    """

    type: Literal["avis", "bug"]
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=5000)
    sentiment: Literal["positif", "neutre", "negatif"] | None = None

    model_config = ConfigDict(str_strip_whitespace=True)


class OfferOut(BaseModel):
    """Job offer returned by the API."""

    id: uuid.UUID
    ft_id: str
    title: str
    company: str
    location: str
    contract_type: str
    description: str
    salary: str | None
    rome_code: str | None
    skills: list[str] = []
    key_skills: list[str] | None = None
    expires_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class CvAnalysisOut(BaseModel):
    """Global CV quality analysis — structure, formulation, ATS score, coherence with profile intent."""

    status: Literal["pending", "processing", "done", "error"]
    ats_score: int | None = None
    synthese: str | None = None
    points_forts: list[str] = []
    points_faibles: list[str] = []
    suggestions: list[str] = []
    coherence_intention: str | None = None

    # JSONB list columns are NULL until the agent writes a "done" row — a
    # pending/processing/error row must still validate.
    @field_validator("points_forts", "points_faibles", "suggestions", mode="before")
    @classmethod
    def _none_to_empty_list(cls, v: list[str] | None) -> list[str]:
        return v if v is not None else []

    model_config = ConfigDict(from_attributes=True)


class PointAmelioration(BaseModel):
    """One improvement point of a match analysis — observation + concrete suggestion.

    suggestion_concrete is None only for legacy rows analysed before migration
    020, where points_amelioration items were plain strings.
    """

    constat: str
    suggestion_concrete: str | None = None


class MatchAnalysisOut(BaseModel):
    """GPT-4o-mini analysis of a single CV<->offer pair — see ADR-018."""

    status: Literal["pending", "processing", "done", "error"]
    matched_skills: list[str] = []
    points_forts: list[str] = []
    points_amelioration: list[PointAmelioration] = []
    synthese: str | None = None
    verdict: str | None = None
    company_summary: str | None = None
    mission_summary: str | None = None
    why_good_fit_for_user: str | None = None
    why_good_candidate: str | None = None
    score_explanation: str | None = None
    questions_entretien_potentielles: list[str] = []
    # Not a DB column — computed by the matches router (needs the user's profile,
    # not just this row) and grafted on via model_copy after model_validate.
    stale: bool = False

    # Forces stale=False on every model_validate(from_attributes), regardless of what
    # a source object exposes under that name — MatchAnalysis has no such column, but a
    # test double (MagicMock) auto-vivifies a truthy attribute for any name accessed,
    # which would otherwise leak through as stale=True before _mark_stale ever runs.
    # The router is the only legitimate writer, via model_copy(update={"stale": ...}).
    @field_validator("stale", mode="before")
    @classmethod
    def _stale_never_from_source(cls, v: object) -> bool:
        return False

    # JSONB list columns are NULL until the agent writes a "done" row — a
    # pending/processing/error row must still validate.
    @field_validator(
        "matched_skills", "points_forts", "questions_entretien_potentielles", mode="before"
    )
    @classmethod
    def _none_to_empty_list(cls, v: list[str] | None) -> list[str]:
        return v if v is not None else []

    # Same NULL coercion, plus: rows analysed before migration 020 store
    # points_amelioration items as plain strings — coerce them so old and new
    # rows serialize the same way.
    @field_validator("points_amelioration", mode="before")
    @classmethod
    def _coerce_points_amelioration(cls, v: list | None) -> list:
        if v is None:
            return []
        return [{"constat": item} if isinstance(item, str) else item for item in v]

    model_config = ConfigDict(from_attributes=True)


class MatchOut(BaseModel):
    """CV-to-offer match returned by the API."""

    score: float
    offer: OfferOut
    analysis: MatchAnalysisOut | None = None
    seen_at: datetime | None = Field(default=None, exclude=True)

    @computed_field
    @property
    def is_new(self) -> bool:
        return self.seen_at is None

    model_config = ConfigDict(from_attributes=True)


class RomeCodeEntry(BaseModel):
    """One ROME code entry in a user profile — tracks contributing CVs and label."""

    cv_ids: list[str]
    label: str


class ProfileOut(BaseModel):
    """User job search profile returned by the API."""

    user_id: str
    rome_codes: dict[str, RomeCodeEntry]
    commune_codes: list[str]
    experience_level: Literal["0-2", "2-5", "5+"] | None
    candidate_description: str | None
    # list[int], not the narrower Literal[1..7] used by ProfileUpdate — this is read
    # back from a column already bounded by ck_user_profiles_notification_days
    # (migration 033), so re-validating each element on every read is redundant.
    notification_days: list[int]
    analysis_credits_remaining: int
    # Not a DB column — computed from ADMIN_USER_IDS by the profile endpoints
    # (model_validate leaves the default; the router overrides via model_copy).
    is_admin: bool = False

    model_config = ConfigDict(from_attributes=True)


class CreditsRefillOut(BaseModel):
    """New credit balance after an admin refill."""

    analysis_credits_remaining: int


class CVUploadOut(BaseModel):
    """Response after a successful CV upload."""

    cv_id: uuid.UUID
    blob_url: str
    message: str


class MatchesOut(BaseModel):
    """GET /matches response — user's ROME codes plus ranked offer matches."""

    rome_codes: dict[str, RomeCodeEntry]
    matches: list[MatchOut]


class CVListItemOut(BaseModel):
    """One CV entry in the user's library."""

    id: uuid.UUID
    name: str | None
    status: CVStatus
    uploaded_at: datetime
    match_count: int
    unseen_count: int = 0
    has_thumbnail: bool

    model_config = ConfigDict(from_attributes=True)
