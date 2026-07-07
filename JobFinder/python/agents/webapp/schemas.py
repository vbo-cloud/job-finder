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
    expires_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class CvAnalysisOut(BaseModel):
    """Global CV quality analysis — structure, formulation, ATS score, coherence with profile intent."""

    status: Literal["pending", "processing", "done", "error"]
    ats_score: int | None = None
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


class MatchAnalysisOut(BaseModel):
    """GPT-4o-mini analysis of a single CV<->offer pair — see ADR-018."""

    status: Literal["pending", "processing", "done", "error"]
    matched_skills: list[str] = []
    points_forts: list[str] = []
    points_amelioration: list[str] = []
    synthese: str | None = None

    # JSONB list columns are NULL until the agent writes a "done" row — a
    # pending/processing/error row must still validate.
    @field_validator("matched_skills", "points_forts", "points_amelioration", mode="before")
    @classmethod
    def _none_to_empty_list(cls, v: list[str] | None) -> list[str]:
        return v if v is not None else []

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

    model_config = ConfigDict(from_attributes=True)


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
