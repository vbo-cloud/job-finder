"""SQLAlchemy ORM models shared across all agents."""

import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
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


class OfferFetchSignal(Base):
    """Single-row signal: sole durable contact point between concurrent offer_fetching
    triggers (see agents/offer_fetching/main.py's advisory-lock-based coordination,
    docs/prompts/prompt-offer-fetching-event-driven-and-new-code-fetch.md). Set true when a
    scheduled (full active-codes) trigger arrives while another fetch cycle already holds the
    lock; drained by the running cycle before it releases the lock.

    Standard UUID primary key, per conventions-sql — the single-row guarantee (and every
    lookup/update) goes through singleton_key = 1 instead, not id. See the migration's
    docstring (030_add_offer_fetch_coordination.py) for why this table doesn't qualify for
    conventions-sql's cache/stats-table primary-key exception.
    """

    __tablename__ = "offer_fetch_signals"
    __table_args__ = (
        UniqueConstraint("singleton_key", name="uq_offer_fetch_signals_singleton_key"),
        CheckConstraint("singleton_key = 1", name="ck_offer_fetch_signals_single_row"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    singleton_key: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    full_refresh_pending: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class OfferFetchPendingCode(Base):
    """A ROME code requested by a targeted (new-code) fetch trigger that arrived while another
    offer_fetching cycle already held the coordination lock. Drained (and cleared) by the
    running cycle before it releases the lock — see OfferFetchSignal.

    Standard UUID primary key, per conventions-sql; deduplication on rome_code (the
    INSERT ... ON CONFLICT DO NOTHING in _mark_rome_codes_pending) targets
    uq_offer_fetch_pending_codes_rome_code, not the primary key — same pattern as
    Offer.id / uq_offers_ft_id. See the migration's docstring for the full rationale.
    """

    __tablename__ = "offer_fetch_pending_codes"
    __table_args__ = (UniqueConstraint("rome_code", name="uq_offer_fetch_pending_codes_rome_code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rome_code: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


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
    # Set by cv_analysis whenever ROME extraction completes (upload or reanalysis). Its only
    # reader — GET /cv/'s rome_reanalysis_available flag, offering a manual reanalysis button —
    # was removed once ROME reanalysis on intent change became automatic (put_profile, see
    # docs/prompts/prompt-intent-driven-reanalysis.md). Left in place, unconsumed, rather than
    # dropped: still meaningful data, and cheap to keep should a future reader need it.
    rome_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set at upload time by the column-aware PDF extraction (routers/cv.py). NULL = not yet
    # computed (CV uploaded before this feature) — never treated as "1 column". 1 = single
    # column, 2 = two columns detected (the only multi-column layout this extraction handles).
    layout_columns_detected: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

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
    # Jours de la semaine (ISO 8601 : 1=lundi ... 7=dimanche) où l'utilisateur reçoit le récap email
    # des nouvelles offres par CV (agent de notification planifié, pas encore livré — voir migration
    # 033). [] = notifications désactivées, pas de booléen séparé. Défaut [7] (dimanche uniquement).
    notification_days: Mapped[list[int]] = mapped_column(
        ARRAY(SmallInteger), nullable=False, default=lambda: [7]
    )
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
    # Stamped unconditionally by POST /credits/request-more on every accepted call (once
    # the 0-credit gate passes) — read back on the next request to enforce
    # MORE_CREDITS_REQUEST_COOLDOWN_SECONDS, which only decides whether the alert email
    # is (re-)sent, not whether this column gets updated. NULL = never requested.
    more_credits_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    # Set in PUT /profile whenever experience_level or candidate_description changes —
    # distinct from updated_at above, which _merge_rome_codes also touches on every CV
    # analysis and is therefore unusable to detect "did the candidate's stated intent
    # change". Renamed from description_updated_at (migration 031) by migration 034:
    # generalized to cover experience_level too, since match_analysis's own prompt
    # context (agents/match_analysis/main.py) renders both fields, not just the
    # description embedded in intent_embedding.
    intent_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Throttles the start-matching + CV reanalysis dispatch on intent change (see
    # put_profile) — independent of intent_updated_at, which stamps on every change
    # regardless of whether the dispatch itself was throttled.
    last_intent_dispatch_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
