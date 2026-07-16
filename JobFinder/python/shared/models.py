"""SQLAlchemy ORM models shared across all agents."""

import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, relationship


class Base(DeclarativeBase):
    pass


class Offer(Base):
    """Job offer collected from France Travail."""

    __tablename__ = "offers"
    __table_args__ = (UniqueConstraint("ft_id", name="uq_offers_ft_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ft_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str] = mapped_column(String, nullable=False)
    commune: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    department: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    region: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    contract_type: Mapped[str] = mapped_column(String, nullable=False)
    rome_code: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    salary: Mapped[str | None] = mapped_column(String, nullable=True)
    # Années d'expérience minimales demandées, parsées depuis experienceLibelle (France Travail).
    # NULL = non renseigné ou format non reconnu — jamais traité comme "0 an requis".
    experience_min_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    skills: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    # Technologies essentielles extraites par le LLM (match_analysis), une fois par offre.
    # NULL = pas encore extrait ; [] = extrait, aucune technologie essentielle identifiée.
    # Remis à NULL quand France Travail modifie l'offre (voir offer_fetching._upsert_offers).
    key_skills: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ft_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    matches: Mapped[list["Match"]] = relationship("Match", back_populates="offer")


class CV(Base):
    """Candidate CV uploaded for matching."""

    __tablename__ = "cvs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    blob_url: Mapped[str | None] = mapped_column(String, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    thumbnail_url_lg: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    matches: Mapped[list["Match"]] = relationship("Match", back_populates="cv")
    analysis: Mapped["CvAnalysis | None"] = relationship(
        "CvAnalysis", back_populates="cv", uselist=False
    )


class CvAnalysis(Base):
    """Global CV quality analysis — structure, formulation, ATS score, coherence with profile intent."""

    __tablename__ = "cv_analyses"
    __table_args__ = (UniqueConstraint("cv_id", name="uq_cv_analyses_cv_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cv_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cvs.id", name="fk_cv_analyses_cv_id_ref_cvs"), nullable=False
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    ats_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    points_forts: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    points_faibles: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    suggestions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    coherence_intention: Mapped[str | None] = mapped_column(Text, nullable=True)
    synthese: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cv: Mapped["CV"] = relationship("CV", back_populates="analysis")


class UserProfile(Base):
    """User job search preferences and target ROME codes."""

    __tablename__ = "user_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_profiles_user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    # Identity claims captured from the validated JWT (profile creation +
    # refreshed on PUT). Best-effort: None when the Entra user flow does not
    # emit them. They exist to give the operator a human-readable mapping for
    # the otherwise opaque pairwise user_id — never used for authorization.
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    rome_codes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    commune_codes: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    experience_level: Mapped[str | None] = mapped_column(String, nullable=True)
    candidate_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    intent_embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    # server_default="30" is intentional: existing beta users retroactively receive
    # the 30 welcome credits too (see ADR-018 — beta-tester welcome gift).
    analysis_credits_remaining: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30, server_default="30"
    )
    analysis_credits_reset_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class Match(Base):
    """Similarity score between a CV and a job offer."""

    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint("cv_id", "offer_id", name="uq_matches_cv_offer"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cv_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cvs.id", name="fk_matches_cv_id_ref_cvs"),
        nullable=False,
    )
    offer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("offers.id", name="fk_matches_offer_id_ref_offers"),
        nullable=False,
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    cv: Mapped["CV"] = relationship("CV", back_populates="matches")
    offer: Mapped["Offer"] = relationship("Offer", back_populates="matches")
    analysis: Mapped["MatchAnalysis | None"] = relationship(
        "MatchAnalysis", back_populates="match", uselist=False
    )


class MatchAnalysis(Base):
    """GPT-4o-mini analysis of a single CV<->offer pair — see ADR-018."""

    __tablename__ = "match_analyses"
    __table_args__ = (UniqueConstraint("match_id", name="uq_match_analyses_match_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matches.id", name="fk_match_analyses_match_id_ref_matches"), nullable=False
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    points_forts: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    points_amelioration: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    matched_skills: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    synthese: Mapped[str | None] = mapped_column(Text, nullable=True)
    verdict: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    mission_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_good_fit_for_user: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_good_candidate: Mapped[str | None] = mapped_column(Text, nullable=True)
    score_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    questions_entretien_potentielles: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    triggered_by: Mapped[str] = mapped_column(String, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    match: Mapped["Match"] = relationship("Match", back_populates="analysis")
