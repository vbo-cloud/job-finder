"""Notifications agent — sends a per-CV digest email of unseen matches to opted-in users.

Runs as a Container App Job on a timer targeting 19:00 Europe/Paris local time (see
container_apps.tf's job_notifications module) — Azure's schedule trigger has no
timezone/DST awareness, so Terraform fires this job at both UTC hours that could map to
19:00 Europe/Paris under CET or CEST; _is_scheduled_local_hour no-ops the firing that
doesn't match the current DST state, same pattern as offer_fetch_scheduler
(agents/offer_fetch_scheduler/main.py).

For each UserProfile whose notification_days includes today's ISO weekday
(1=Monday...7=Sunday, see shared/models.py), the digest lists every CV with at least one
unseen match (Match.seen_at IS NULL), each with its unseen count and its single
best-scoring unseen offer (title, company, location, contract type, match %). The email
also carries a personalized greeting (UserProfile.display_name, best-effort from the JWT),
a reminder-day calendar strip in the header, and a subject line built from the recipient's
total unseen count and top score. Never writes Match.seen_at — that column is exclusively
updated by user action in the webapp (routers/cv.py's mark_all_seen/mark_match_seen) — so
an unseen offer stays in the digest across multiple sends until the user views it in the
app. Not a bug if a user who checks several notification_days receives the same unseen
offer more than once.

Deliberately does not replicate GET /cv's commune-zone filter (routers/matches.py's
commune_zone_condition, package webapp): no agent in this repo imports another agent's
code (cleanup, matching, offer_fetch_scheduler only ever import shared.*), and that
helper lives in webapp, not shared. The digest count can therefore run slightly ahead
of what a user with a small painted zone sees in the CV library.

No CV deep-link exists yet on the frontend (HomeClient.tsx has no query-param handling to
preselect a CV), so every CTA in the digest — per-card and primary — links to the bare
frontend_url rather than a fabricated `?cv=<id>` the frontend would ignore.

Expected environment variables:
    DATABASE_URL: PostgreSQL connection string.
    ACS_EMAIL_ENDPOINT_HOSTNAME: Azure Communication Services Email data-plane hostname
        (endpoint = https://<hostname>).
    ACS_EMAIL_SENDER_ADDRESS: Verified sender address used in the From header.
    FRONTEND_URL: Base URL linked from every CTA and the footer's unsubscribe link.
    AZURE_CLIENT_ID: Read implicitly by DefaultAzureCredential (caj managed identity).
    APPLICATIONINSIGHTS_CONNECTION_STRING: Optional, enables telemetry export.
"""

import html
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import structlog
from alembic.util.exc import CommandError
from azure.communication.email import EmailClient
from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from shared.db import get_session, run_migrations
from shared.models import CV, Match, Offer, UserProfile
from shared.telemetry import configure_telemetry

PARIS_TZ = ZoneInfo("Europe/Paris")
# Kept in sync with the UTC hours covered by container_apps.tf's cron_expression
# for job_notifications — see _is_scheduled_local_hour.
SCHEDULED_LOCAL_HOURS = (19,)
# ISO 8601 weekday (1=Monday...7=Sunday) -> single-letter French day initial, used by the
# header's reminder calendar strip. Tuesday and Wednesday intentionally share "M"
# (Mardi/Mercredi), same as the reference design.
_WEEKDAY_LETTERS = {1: "L", 2: "M", 3: "M", 4: "J", 5: "V", 6: "S", 7: "D"}
_WEEKDAY_ABBREVIATIONS = {1: "Lun", 2: "Mar", 3: "Mer", 4: "Jeu", 5: "Ven", 6: "Sam", 7: "Dim"}

logger = structlog.get_logger()

_endpoint_hostname = os.environ.get("ACS_EMAIL_ENDPOINT_HOSTNAME")
if not _endpoint_hostname:
    raise ValueError("ACS_EMAIL_ENDPOINT_HOSTNAME environment variable is not set")

_sender_address = os.environ.get("ACS_EMAIL_SENDER_ADDRESS")
if not _sender_address:
    raise ValueError("ACS_EMAIL_SENDER_ADDRESS environment variable is not set")

_frontend_url = os.environ.get("FRONTEND_URL")
if not _frontend_url:
    raise ValueError("FRONTEND_URL environment variable is not set")


@dataclass(frozen=True)
class Recipient:
    """One opted-in profile eligible for today's digest.

    Built inside _load_recipients_and_entries's `with get_session()` block, copying every
    field the caller needs off the ORM row — the session closes before this dataclass is
    returned, so touching a lazy/unloaded UserProfile attribute afterward is not an option.
    """

    user_id: str
    email: str | None
    display_name: str | None
    notification_days: list[int]


@dataclass(frozen=True)
class CvDigestEntry:
    """One CV's digest entry: its unseen-match count plus its best-scoring unseen match.

    top_offer_location is Offer.location, falling back to Offer.department when
    Offer.location is blank (some offers only carry a department code), and can be the
    empty string if both are blank — see _load_cv_digest_entries_by_user. _offer_line
    branches on that empty-string case to drop the location segment entirely rather than
    render a stray separator.
    """

    cv_name: str | None
    unseen_count: int
    top_offer_title: str
    top_offer_company: str
    top_offer_location: str
    top_offer_contract_type: str
    top_offer_score_pct: int


def _is_scheduled_local_hour(now_utc: datetime) -> bool:
    """Check whether now_utc falls on this job's intended Europe/Paris run hour.

    Azure Container Apps' schedule trigger only supports a UTC cron_expression, with no
    timezone or DST awareness. Terraform's cron_expression for job_notifications
    therefore fires at every UTC hour that could map to SCHEDULED_LOCAL_HOURS under
    either CET (UTC+1) or CEST (UTC+2) — this guard picks out the firing that is
    actually correct for the current DST state, so main() can no-op the other one.

    Args:
        now_utc: Current time, timezone-aware in UTC.

    Returns:
        True if now_utc's Europe/Paris local hour is one of SCHEDULED_LOCAL_HOURS.
    """
    return now_utc.astimezone(PARIS_TZ).hour in SCHEDULED_LOCAL_HOURS


def _select_profiles_to_notify(session: Session, today_isoweekday: int) -> list[UserProfile]:
    """Return every UserProfile opted in to receive a digest today.

    Args:
        session: Active SQLAlchemy session.
        today_isoweekday: ISO 8601 weekday (1=Monday...7=Sunday) for the current
            Europe/Paris local date.

    Returns:
        UserProfile rows whose notification_days contains today_isoweekday.

    Raises:
        SQLAlchemyError: If the query fails.
    """
    logger.info("notifications_profile_selection_started", today_isoweekday=today_isoweekday)
    return list(
        session.execute(
            select(UserProfile).where(UserProfile.notification_days.any(today_isoweekday))
        ).scalars()
    )


def _load_cv_digest_entries_by_user(
    session: Session, user_ids: list[str]
) -> dict[str, list[CvDigestEntry]]:
    """Load each CV's unseen-match count and best-scoring unseen match, by owning user.

    Issues a single batched query across all given users instead of one query per user,
    avoiding an N+1 pattern when a run notifies many profiles. Ranks each CV's unseen
    matches with `ROW_NUMBER() OVER (PARTITION BY cv_id ORDER BY score DESC, id)` — the
    Match.id tie-break keeps the pick stable when two matches share the same score — and
    counts them with `COUNT(*) OVER (PARTITION BY cv_id)` in the same pass, then keeps only
    rn=1 — one row per CV, carrying both its count and its top match. The final result is
    also ordered by cv_name for a deterministic card order. Built with SQLAlchemy Core's
    window-function support (func.row_number()/func.count().over(...)) rather than raw SQL
    specifically so it stays portable to SQLite (matching/main.py's _enqueue_top_n_analyses
    uses a raw-SQL PostgreSQL-only equivalent; that one is excluded from the SQLite test
    suite per tests/README.md, this one is not).

    Args:
        session: Active SQLAlchemy session.
        user_ids: Owning users' identifiers (CV.user_id) to load entries for.

    Returns:
        Mapping of user_id to CvDigestEntry list, one entry per CV with at least one
        unseen match. A user_id with no unseen matches is absent from the mapping rather
        than present with an empty list. Each entry's top_offer_location falls back to
        Offer.department when Offer.location is blank, and can be the empty string when
        both are blank — see CvDigestEntry.

    Raises:
        SQLAlchemyError: If the query fails.
    """
    if not user_ids:
        return {}

    logger.info("notifications_digest_entries_started", user_count=len(user_ids))
    ranked = (
        select(
            CV.user_id.label("user_id"),
            CV.name.label("cv_name"),
            Offer.title.label("offer_title"),
            Offer.company.label("offer_company"),
            Offer.location.label("offer_location"),
            Offer.department.label("offer_department"),
            Offer.contract_type.label("offer_contract_type"),
            Match.score.label("score"),
            func.count().over(partition_by=CV.id).label("unseen_count"),
            func.row_number()
            .over(partition_by=CV.id, order_by=(Match.score.desc(), Match.id))
            .label("rn"),
        )
        .select_from(Match)
        .join(CV, CV.id == Match.cv_id)
        .join(Offer, Offer.id == Match.offer_id)
        .where(CV.user_id.in_(user_ids), Match.seen_at.is_(None))
        .subquery()
    )
    # Match.id as a tie-breaker keeps the top-match choice stable across runs when two
    # matches share the same score; cv_name orders the digest's cards deterministically.
    rows = session.execute(
        select(ranked).where(ranked.c.rn == 1).order_by(ranked.c.cv_name)
    ).all()

    entries_by_user: dict[str, list[CvDigestEntry]] = {}
    for row in rows:
        location = row.offer_location or row.offer_department or ""
        entries_by_user.setdefault(row.user_id, []).append(
            CvDigestEntry(
                cv_name=row.cv_name,
                unseen_count=row.unseen_count,
                top_offer_title=row.offer_title,
                top_offer_company=row.offer_company,
                top_offer_location=location,
                top_offer_contract_type=row.offer_contract_type,
                top_offer_score_pct=round(row.score * 100),
            )
        )
    return entries_by_user


def _load_recipients_and_entries(
    today_isoweekday: int,
) -> tuple[list[Recipient], dict[str, list[CvDigestEntry]]]:
    """Fetch today's opted-in profiles and their unseen-match digest entries in one session.

    Args:
        today_isoweekday: ISO 8601 weekday (1=Monday...7=Sunday) for the current
            Europe/Paris local date.

    Returns:
        Tuple of (recipients, entries_by_user): recipients is one Recipient per opted-in
        profile; entries_by_user maps user_id to its CvDigestEntry list (see
        _load_cv_digest_entries_by_user). The session is closed before returning, so the
        caller can send emails without holding a DB connection open.

    Raises:
        SQLAlchemyError: If either query fails.
    """
    try:
        with get_session() as session:
            profiles = _select_profiles_to_notify(session, today_isoweekday)
            recipients = [
                Recipient(
                    user_id=profile.user_id,
                    email=profile.email,
                    display_name=profile.display_name,
                    notification_days=list(profile.notification_days),
                )
                for profile in profiles
            ]
            entries_by_user = _load_cv_digest_entries_by_user(
                session, [recipient.user_id for recipient in recipients if recipient.email]
            )
    except SQLAlchemyError:
        logger.error("notifications_query_failed", exc_info=True)
        raise
    return recipients, entries_by_user


def _build_digest_subject(cv_entries: list[CvDigestEntry]) -> str:
    """Build a per-recipient subject line from today's unseen-match totals.

    Args:
        cv_entries: This recipient's CvDigestEntry list, one per CV with unseen matches.

    Returns:
        A French subject line, singular when exactly one offer is unseen across every CV,
        plural otherwise. The plural branch also covers the defensive zero-offer case
        (main() never actually reaches it — it skips a recipient before building content
        when its cv_entries list is empty — but it's covered here rather than assumed).
    """
    total, best_score = _digest_totals(cv_entries)
    if total == 1:
        return f"🎯 Une offre à {best_score}% de correspondance vous attend"
    return f"🎯 {total} offres collent à votre profil (dont une à {best_score}%)"


def _greeting(display_name: str | None) -> str:
    """Build the digest's opening line, personalized when a display_name is known.

    Args:
        display_name: Recipient's UserProfile.display_name, best-effort from the JWT
            (may be None). Not escaped — callers building the HTML body must escape it
            themselves (or escape display_name before calling), same as CV.name/Offer.title
            elsewhere in this module; the plain-text body needs no escaping at all.

    Returns:
        "Bonjour {display_name}," if set, otherwise the generic "Bonjour,".
    """
    if display_name:
        return f"Bonjour {display_name},"
    return "Bonjour,"


def _digest_totals(cv_entries: list[CvDigestEntry]) -> tuple[int, int]:
    """Return (total_unseen, best_score) across every CV, shared by subject/hero/preheader.

    Args:
        cv_entries: One CvDigestEntry per CV with at least one unseen match.

    Returns:
        (sum of unseen_count, max of top_offer_score_pct, or 0 if cv_entries is empty).
    """
    total_unseen = sum(entry.unseen_count for entry in cv_entries)
    best_score = max((entry.top_offer_score_pct for entry in cv_entries), default=0)
    return total_unseen, best_score


def _calendar_day_style(
    isoweekday: int, notification_days: list[int], today_isoweekday: int
) -> tuple[str, str, str, str]:
    """Return the (band, body, letter, weight) style for one reminder-calendar day icon.

    Priority: today (red) beats a selected day (white) beats a plain day (grey) — today
    wins even when also selected, which is nearly always the case since this digest is
    only ever sent on a day present in notification_days. The red icon means "you are
    here", not "not selected".

    Args:
        isoweekday: ISO 8601 weekday of the icon being rendered (1=Monday...7=Sunday).
        notification_days: The recipient's UserProfile.notification_days.
        today_isoweekday: ISO 8601 weekday of the current Europe/Paris local date.

    Returns:
        (band_color, body_color, letter_color, letter_font_weight).
    """
    if isoweekday == today_isoweekday:
        return "#ef4444", "#2a1414", "#fca5a5", "800"
    if isoweekday in notification_days:
        return "#f2f2f4", "#24242f", "#f2f2f4", "800"
    return "#4a4a54", "#1c1c25", "#5c5c66", "700"


def _render_calendar_html(notification_days: list[int], today_isoweekday: int) -> str:
    """Render the 7-day reminder calendar strip shown in the header, right of the title.

    Args:
        notification_days: The recipient's UserProfile.notification_days.
        today_isoweekday: ISO 8601 weekday of the current Europe/Paris local date.

    Returns:
        HTML for the row of 7 nested-table day icons (see _calendar_day_style for colors).
    """
    cells = []
    for isoweekday in range(1, 8):
        band, body, letter, weight = _calendar_day_style(isoweekday, notification_days, today_isoweekday)
        letter_char = _WEEKDAY_LETTERS[isoweekday]
        cells.append(
            "<td><table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\">"
            f"<tr><td style=\"width:22px; height:7px; background-color:{band}; "
            "border-radius:4px 4px 0 0; font-size:1px; line-height:1px;\">&nbsp;</td></tr>"
            f"<tr><td style=\"width:22px; height:16px; background-color:{body}; "
            "border-radius:0 0 4px 4px; text-align:center; vertical-align:middle; "
            f"font-family: Arial, Helvetica, sans-serif; font-size:10px; font-weight:{weight}; "
            f"color:{letter};\">{letter_char}</td></tr></table></td>"
        )
        if isoweekday != 7:
            cells.append('<td style="width:4px; font-size:1px; line-height:1px;">&nbsp;</td>')
    return f'<table role="presentation" cellpadding="0" cellspacing="0"><tr>{"".join(cells)}</tr></table>'


def _render_calendar_text(notification_days: list[int], today_isoweekday: int) -> str:
    """Render the plain-text equivalent of the reminder calendar, as one line.

    Args:
        notification_days: The recipient's UserProfile.notification_days.
        today_isoweekday: ISO 8601 weekday of the current Europe/Paris local date.

    Returns:
        e.g. "Rappels programmés : Lun · Mer · Ven · [Dim] (aujourd'hui)".
    """
    labels = []
    for isoweekday in sorted(notification_days):
        label = _WEEKDAY_ABBREVIATIONS.get(isoweekday, "?")
        if isoweekday == today_isoweekday:
            label = f"[{label}] (aujourd'hui)"
        labels.append(label)
    return "Rappels programmés : " + " · ".join(labels)


def _offer_line(company: str, location: str, contract_type: str) -> str:
    """Build "{company} — {location} · {contract_type}", dropping the location if blank."""
    if location:
        return f"{company} — {location} · {contract_type}"
    return f"{company} · {contract_type}"


def _hero_copy(total_unseen: int, best_score: int) -> tuple[str, str]:
    """Build the digest's hero heading and lead paragraph.

    Args:
        total_unseen: Sum of unseen-match counts across every CV.
        best_score: Highest top_offer_score_pct across every CV.

    Returns:
        (heading, lead_html) — heading is plain text (no user input, no escaping needed);
        lead_html already contains a <strong> highlight around best_score.
    """
    if total_unseen == 1:
        heading = "Une nouvelle offre colle à votre profil 🎯"
    else:
        heading = f"{total_unseen} nouvelles offres collent à votre profil 🎯"
    lead_html = (
        "Notre IA a passé au crible les dernières offres publiées et repéré celles qui "
        f'matchent le mieux vos CV — dont une à <strong style="color:#e5e5ea;">{best_score}% '
        "de correspondance</strong>. Les meilleures offres partent vite, jetez-y un œil."
    )
    return heading, lead_html


def _render_cv_top_match_html(entry: CvDigestEntry) -> str:
    """Render the score chip + offer summary row inside a CV card.

    Args:
        entry: The CV's digest entry.

    Returns:
        HTML for the top-match `<table>` row. Offer.title/Offer.company/Offer.location are
        free text — escaped, same as CV.name.
    """
    title = html.escape(entry.top_offer_title)
    offer_line = html.escape(
        _offer_line(entry.top_offer_company, entry.top_offer_location, entry.top_offer_contract_type)
    )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="margin-top:14px;"><tr>'
        '<td width="54" valign="top" style="padding-right:14px;">'
        '<table role="presentation" cellpadding="0" cellspacing="0" '
        'style="background-color:#173226; border-radius:8px;"><tr>'
        '<td style="width:54px; text-align:center; padding:9px 0; font-family: Arial, '
        f'Helvetica, sans-serif; font-size:15px; font-weight:800; color:#3ee6a0;">'
        f"{entry.top_offer_score_pct}%</td></tr></table></td>"
        '<td valign="top">'
        '<p style="margin:0; font-family: Arial, Helvetica, sans-serif; font-size:14.5px; '
        f'font-weight:700; color:#f2f2f4; line-height:1.35;">{title}</p>'
        '<p style="margin:3px 0 0 0; font-family: Arial, Helvetica, sans-serif; '
        f'font-size:12.5px; color:#9a9aa2;">{offer_line}</p>'
        "</td></tr></table>"
    )


def _render_cv_card_html(entry: CvDigestEntry, frontend_url: str) -> str:
    """Render one CV's full card: name/count badge, top-match summary, and its CTA.

    Args:
        entry: The CV's digest entry.
        frontend_url: Base URL the card's CTA links to (no CV deep-link exists yet, see
            this module's docstring).

    Returns:
        HTML for one card `<tr>` block. The badge text is exactly
        "{cv_name} : {count} nouvelle(s) offre(s)", kept verbatim from the earlier digest
        design — see test_build_email_content_includes_cv_name_and_count.
    """
    name = html.escape(entry.cv_name or "CV sans nom")
    return (
        '<tr><td class="px" style="padding: 14px 32px 0 32px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="background-color:#1c1c25; border:1px solid #26262f; border-radius:12px;">'
        '<tr><td style="padding: 18px 20px;">'
        '<p style="margin:0; font-family: Arial, Helvetica, sans-serif; font-size:11.5px; '
        'font-weight:800; letter-spacing:.05em; text-transform:uppercase; color:#8686a0;">'
        f"{name} : {entry.unseen_count} nouvelle(s) offre(s)</p>"
        f"{_render_cv_top_match_html(entry)}"
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:16px;">'
        '<tr><td style="border-radius:8px; background-color:#2563eb;">'
        f'<a href="{frontend_url}" class="stack-btn" style="display:inline-block; '
        'padding:10px 18px; font-family: Arial, Helvetica, sans-serif; font-size:13px; '
        f'font-weight:700; color:#ffffff;">Voir les {entry.unseen_count} offres →</a>'
        "</td></tr></table>"
        "</td></tr></table></td></tr>"
    )


def _render_cv_card_text(entry: CvDigestEntry, frontend_url: str) -> str:
    """Render one CV's plain-text block: name/count line, top match, and its link.

    Args:
        entry: The CV's digest entry.
        frontend_url: URL appended as this CV's "Voir les offres" link.

    Returns:
        Multi-line plain text for one CV, in the same order as the HTML card. Not
        escaped — plain text has no markup to break, same convention as the earlier
        digest's CV name handling.
    """
    name = entry.cv_name or "CV sans nom"
    offer_line = _offer_line(entry.top_offer_company, entry.top_offer_location, entry.top_offer_contract_type)
    return (
        f"{name} : {entry.unseen_count} nouvelle(s) offre(s)\n"
        f"  ★ {entry.top_offer_score_pct}% de correspondance — {entry.top_offer_title}\n"
        f"  {offer_line}\n"
        f"  Voir les {entry.unseen_count} offres → {frontend_url}"
    )


def _render_preheader_html(total_unseen: int, best_score: int) -> str:
    """Render the hidden preview text shown by mail clients next to the subject in the inbox.

    Args:
        total_unseen: Sum of unseen-match counts across every CV.
        best_score: Highest top_offer_score_pct across every CV.

    Returns:
        HTML for the hidden preheader `<div>`, French singular/plural agreed.
    """
    if total_unseen == 1:
        summary = f"Une offre correspond à vos CV, à {best_score}%"
    else:
        summary = f"{total_unseen} offres correspondent à vos CV, dont une à {best_score}%"
    return (
        '<div style="display:none; max-height:0; overflow:hidden; mso-hide:all; '
        'font-size:1px; line-height:1px; color:#0a0a0f;">'
        f"{summary} — vos favorites pourraient disparaître vite."
        "&#8203;&zwnj;&nbsp;&#8203;&zwnj;&nbsp;&#8203;&zwnj;&nbsp;&#8203;&zwnj;&nbsp;&#8203;&zwnj;&nbsp;"
        "</div>"
    )


def _render_header_html(calendar_html: str) -> str:
    """Render the header row: "Job Finder" title on the left, reminder calendar on the right."""
    return (
        '<tr><td class="px" style="padding: 18px 32px; border-bottom:1px solid #212129;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
        '<td valign="middle" style="font-family: Arial, Helvetica, sans-serif; font-size:16px; '
        'font-weight:800; color:#f2f2f4; letter-spacing:.01em;">'
        '<span style="color:#60a5fa;">●</span>&nbsp;Job Finder</td>'
        f'<td align="right" valign="middle">{calendar_html}</td>'
        "</tr></table></td></tr>"
    )


def _render_hero_html(greeting: str, heading: str, lead_html: str) -> str:
    """Render the hero section: greeting, heading, and lead paragraph."""
    return (
        '<tr><td class="px" style="padding: 32px 32px 4px 32px;">'
        '<p style="margin:0 0 10px 0; font-family: Arial, Helvetica, sans-serif; '
        f'font-size:14px; color:#8a8a92;">{greeting}</p>'
        '<h1 style="margin:0 0 14px 0; font-family: Arial, Helvetica, sans-serif; '
        f'font-size:23px; line-height:1.32; font-weight:800; color:#ffffff;">{heading}</h1>'
        '<p style="margin:0 0 8px 0; font-family: Arial, Helvetica, sans-serif; '
        f'font-size:14.5px; line-height:1.55; color:#b0b0b8;">{lead_html}</p>'
        "</td></tr>"
    )


def _render_cta_html(frontend_url: str) -> str:
    """Render the primary "Voir toutes mes offres" call-to-action button."""
    return (
        '<tr><td align="center" style="padding: 28px 32px 28px 32px;">'
        '<table role="presentation" cellpadding="0" cellspacing="0"><tr>'
        '<td style="border-radius:10px; background-color:#2563eb;">'
        f'<a href="{frontend_url}" style="display:inline-block; padding:14px 30px; '
        'font-family: Arial, Helvetica, sans-serif; font-size:15px; font-weight:800; '
        'color:#ffffff;">Voir toutes mes offres sur Job Finder</a>'
        "</td></tr></table></td></tr>"
    )


def _render_footer_html(frontend_url: str) -> str:
    """Render the footer: opt-in reminder and an explicit "Se désabonner" link.

    A clear, explicit unsubscribe label matters here — a vague "Gérer mes préférences"
    pushes recipients toward their mail client's spam button instead of the app, which
    hurts sender reputation more than an explicit unsubscribe link would.
    """
    return (
        '<tr><td class="px" style="padding: 24px 32px 28px 32px; border-top:1px solid #212129;">'
        '<p style="margin:0 0 6px 0; font-family: Arial, Helvetica, sans-serif; font-size:12px; '
        'line-height:1.6; color:#5c5c66;">Vous recevez cet email car vous avez activé les '
        "rappels dans vos préférences Job Finder.</p>"
        '<p style="margin:0; font-family: Arial, Helvetica, sans-serif; font-size:12px; '
        'line-height:1.6; color:#5c5c66;">'
        f'<a href="{frontend_url}/profile" style="color:#7d9dfc; font-weight:600;">'
        "Se désabonner des rappels</a>&nbsp;·&nbsp;"
        f'<a href="{frontend_url}" style="color:#7d9dfc; font-weight:600;">Job Finder</a>'
        "</p></td></tr>"
    )


def _html_document_head() -> str:
    """Return the static `<!DOCTYPE html>`...`<head>` block (no dynamic content)."""
    return (
        '<!DOCTYPE html><html lang="fr" xmlns:v="urn:schemas-microsoft-com:vml" '
        'xmlns:o="urn:schemas-microsoft-com:office:office"><head>'
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        '<meta http-equiv="X-UA-Compatible" content="IE=edge">'
        '<meta name="color-scheme" content="dark light">'
        '<meta name="supported-color-schemes" content="dark light">'
        "<title>Vos nouvelles offres Job Finder</title>"
        "<!--[if mso]><noscript><xml><o:OfficeDocumentSettings>"
        "<o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml></noscript><![endif]-->"
        "<style>"
        "body, table, td, a { -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }"
        "table, td { mso-table-lspace: 0pt; mso-table-rspace: 0pt; }"
        "img { -ms-interpolation-mode: bicubic; border: 0; line-height: 100%; outline: none; "
        "text-decoration: none; }"
        "body { margin: 0; padding: 0; width: 100% !important; background-color: #0a0a0f; }"
        "a { text-decoration: none; }"
        "@media screen and (max-width: 600px) {"
        ".container { width: 100% !important; border-radius: 0 !important; }"
        ".px { padding-left: 20px !important; padding-right: 20px !important; }"
        ".stack-btn { display: block !important; width: 100% !important; text-align: center !important; }"
        "}</style></head>"
    )


def _render_html_body(
    display_name: str | None,
    notification_days: list[int],
    today_isoweekday: int,
    cv_entries: list[CvDigestEntry],
    frontend_url: str,
) -> str:
    """Assemble the complete HTML email document from its rendered sections.

    Args:
        display_name: Recipient's UserProfile.display_name.
        notification_days: Recipient's UserProfile.notification_days.
        today_isoweekday: ISO 8601 weekday of the current Europe/Paris local date.
        cv_entries: One CvDigestEntry per CV with at least one unseen match.
        frontend_url: Base URL for every CTA and the footer's links.

    Returns:
        Complete HTML document string.
    """
    total_unseen, best_score = _digest_totals(cv_entries)
    heading, lead_html = _hero_copy(total_unseen, best_score)
    calendar_html = _render_calendar_html(notification_days, today_isoweekday)
    cards_html = "".join(_render_cv_card_html(entry, frontend_url) for entry in cv_entries)
    # display_name is free text from a JWT claim (UserProfile.display_name) — escaped here,
    # same as CV.name/Offer.title elsewhere in this module. The plain-text greeting built by
    # _build_email_content uses the raw, unescaped value instead.
    greeting = _greeting(html.escape(display_name) if display_name else None)

    body = (
        f"{_render_preheader_html(total_unseen, best_score)}"
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="background-color:#0a0a0f;"><tr><td align="center" style="padding: 32px 12px;">'
        '<table role="presentation" class="container" width="600" cellpadding="0" cellspacing="0" '
        'style="width:600px; max-width:600px; background-color:#15151c; border:1px solid #26262f; '
        'border-radius:16px; overflow:hidden;">'
        f"{_render_header_html(calendar_html)}"
        f"{_render_hero_html(greeting, heading, lead_html)}"
        f"{cards_html}"
        f"{_render_cta_html(frontend_url)}"
        f"{_render_footer_html(frontend_url)}"
        "</table></td></tr></table>"
    )
    return f'{_html_document_head()}<body style="margin:0; padding:0; background-color:#0a0a0f;">{body}</body></html>'


def _build_email_content(
    display_name: str | None,
    notification_days: list[int],
    today_isoweekday: int,
    cv_entries: list[CvDigestEntry],
    frontend_url: str,
) -> tuple[str, str]:
    """Build the plain-text and HTML bodies of the digest email.

    Args:
        display_name: Recipient's UserProfile.display_name, best-effort from the JWT — used
            for the greeting, falling back to a generic "Bonjour," when unset.
        notification_days: Recipient's UserProfile.notification_days, rendered as a reminder
            calendar in the header.
        today_isoweekday: ISO 8601 weekday of the current Europe/Paris local date.
        cv_entries: One CvDigestEntry per CV with at least one unseen match, in digest order.
        frontend_url: Base URL linked from every CTA and the footer's unsubscribe link.

    Returns:
        Tuple of (plain_text, html).
    """
    total_unseen, best_score = _digest_totals(cv_entries)
    greeting = _greeting(display_name)
    heading, _ = _hero_copy(total_unseen, best_score)

    plain_text = "\n\n".join(
        [
            greeting,
            _render_calendar_text(notification_days, today_isoweekday),
            f"{heading}\n\nNotre IA a passé au crible les dernières offres publiées et repéré "
            f"celles qui matchent le mieux vos CV, dont une à {best_score}% de correspondance "
            "sur Job Finder. Les meilleures offres partent vite, jetez-y un œil.",
            "\n\n".join(_render_cv_card_text(entry, frontend_url) for entry in cv_entries),
            f"Voir toutes mes offres sur Job Finder :\n{frontend_url}",
            "—\nVous recevez cet email car vous avez activé les rappels dans vos préférences "
            f"Job Finder.\nSe désabonner des rappels : {frontend_url}/profile",
        ]
    )

    html_body = _render_html_body(display_name, notification_days, today_isoweekday, cv_entries, frontend_url)
    return plain_text, html_body


def _send_digest(
    client: EmailClient, recipient: str, subject: str, plain_text: str, html_body: str
) -> None:
    """Send one digest email via Azure Communication Services Email.

    Args:
        client: Configured EmailClient.
        recipient: Destination address (UserProfile.email).
        subject: Per-recipient subject line (see _build_digest_subject).
        plain_text: Plain-text body.
        html_body: HTML body.

    Raises:
        AzureError: If the send request fails. The caller counts this per user and
            continues with the next profile.
    """
    logger.info("notifications_send_started", recipient=recipient)
    try:
        poller = client.begin_send(
            {
                "senderAddress": _sender_address,
                "content": {"subject": subject, "plainText": plain_text, "html": html_body},
                "recipients": {"to": [{"address": recipient}]},
            }
        )
        poller.result()
    except AzureError:
        logger.error("notifications_send_failed", recipient=recipient, exc_info=True)
        raise
    logger.info("notifications_send_completed", recipient=recipient)


def _process_recipient(
    client: EmailClient,
    recipient: Recipient,
    cv_entries: list[CvDigestEntry],
    today_isoweekday: int,
    frontend_url: str,
) -> str:
    """Build and send one recipient's digest, given it already has an email address.

    Args:
        client: Configured EmailClient.
        recipient: An opted-in recipient known to have an email address.
        cv_entries: This recipient's CvDigestEntry list — empty if nothing unseen.
        today_isoweekday: ISO 8601 weekday of the current Europe/Paris local date.
        frontend_url: Base URL for every CTA and the footer's links.

    Returns:
        "sent", "skipped_no_unseen_offers", or "failed" — matches main()'s tally keys.
    """
    if not cv_entries:
        logger.info("notifications_skipped_no_unseen_offers", user_id=recipient.user_id)
        return "skipped_no_unseen_offers"

    subject = _build_digest_subject(cv_entries)
    plain_text, html_body = _build_email_content(
        recipient.display_name, recipient.notification_days, today_isoweekday, cv_entries, frontend_url
    )
    try:
        _send_digest(client, recipient.email, subject, plain_text, html_body)
    except AzureError:
        return "failed"
    return "sent"


def main() -> None:
    """Send the daily digest email to every opted-in profile, unless outside the scheduled hour."""
    configure_telemetry("notifications")

    now_utc = datetime.now(timezone.utc)
    if not _is_scheduled_local_hour(now_utc):
        logger.info("notifications_skipped_outside_local_window", utc_hour=now_utc.hour)
        return

    try:
        run_migrations()
    except (SQLAlchemyError, CommandError):  # matches run_migrations()'s documented Raises
        logger.error("migrations_failed", exc_info=True)
        raise

    today_isoweekday = now_utc.astimezone(PARIS_TZ).isoweekday()
    recipients, entries_by_user = _load_recipients_and_entries(today_isoweekday)
    client = EmailClient(f"https://{_endpoint_hostname}", DefaultAzureCredential())

    outcomes = {"sent": 0, "skipped_no_email": 0, "skipped_no_unseen_offers": 0, "failed": 0}
    for recipient in recipients:
        if not recipient.email:
            logger.info("notifications_skipped_no_email", user_id=recipient.user_id)
            outcomes["skipped_no_email"] += 1
            continue

        cv_entries = entries_by_user.get(recipient.user_id, [])
        outcome = _process_recipient(client, recipient, cv_entries, today_isoweekday, _frontend_url)
        outcomes[outcome] += 1

    logger.info(
        "notifications_completed",
        sent=outcomes["sent"],
        skipped_no_email=outcomes["skipped_no_email"],
        skipped_no_unseen_offers=outcomes["skipped_no_unseen_offers"],
        failed=outcomes["failed"],
    )


if __name__ == "__main__":
    main()
