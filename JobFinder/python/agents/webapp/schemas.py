"""Pydantic request and response schemas for the webapp API."""

import uuid

from pydantic import BaseModel, ConfigDict


class ProfileUpdate(BaseModel):
    """Payload for creating or updating a user's job search profile.

    rome_codes is intentionally absent — it is managed exclusively by
    the GPT-4o-mini CV analysis agent and must never be overwritten by the user.
    """

    job_categories: list[str]
    location: str | None = None
    contract_types: list[str]


class OfferOut(BaseModel):
    """Job offer returned by the API."""

    id: uuid.UUID
    title: str
    company: str
    location: str
    contract_type: str
    salary: str | None
    rome_code: str | None
    skills: list[str] = []

    model_config = ConfigDict(from_attributes=True)


class MatchOut(BaseModel):
    """CV-to-offer match returned by the API."""

    score: float
    offer: OfferOut

    model_config = ConfigDict(from_attributes=True)


class ProfileOut(BaseModel):
    """User job search profile returned by the API."""

    user_id: str
    rome_codes: list[str]
    job_categories: list[str]
    location: str | None
    contract_types: list[str]

    model_config = ConfigDict(from_attributes=True)


class CVUploadOut(BaseModel):
    """Response after a successful CV upload."""

    cv_id: uuid.UUID
    blob_url: str
    message: str


class MatchesOut(BaseModel):
    """GET /matches response — user's ROME codes plus ranked offer matches."""

    rome_codes: list[str]
    matches: list[MatchOut]
