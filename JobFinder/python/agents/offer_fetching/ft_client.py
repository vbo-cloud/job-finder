"""France Travail API client — authenticate and paginate job offer results."""

import os
import time
from datetime import datetime, timedelta, timezone

import requests
import structlog

FT_TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
FT_OFFERS_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
FT_SCOPE = "api_offresdemploiv2 o2dsoffre"
INTER_PAGE_SLEEP = 0.5
MAX_RETRIES = 5
PAGE_SIZE = 50
# Marge de sécurité sous le plafond de pagination observé empiriquement (~3050 sur un cas réel,
# voir docs/prompts/prompt-fix-offer-fetching-pagination-ceiling.md) — pas une valeur documentée
# par France Travail, à ajuster si le comportement réel de l'API diverge. fetch_all_offers découpe
# la recherche par fenêtres de date de création pour qu'aucun appel fetch_offers ne dépasse ce seuil.
PAGINATION_SAFE_THRESHOLD = 2500
# Largeur (en jours) de la fenêtre de date de création par laquelle démarre la recherche adaptative :
# rétrécie de moitié tant que la tranche dépasse le seuil, jusqu'au plancher MIN_WINDOW_DAYS.
DEFAULT_WINDOW_DAYS = 30
MIN_WINDOW_DAYS = 1

logger = structlog.get_logger()

_ft_client_id = os.environ.get("FT_CLIENT_ID")
if not _ft_client_id:
    raise ValueError("FT_CLIENT_ID environment variable is not set")

_ft_client_secret = os.environ.get("FT_CLIENT_SECRET")
if not _ft_client_secret:
    raise ValueError("FT_CLIENT_SECRET environment variable is not set")


def get_access_token() -> str:
    """Obtain an OAuth2 access token from France Travail using client credentials.

    Returns:
        The access token string.

    Raises:
        requests.RequestException: If the token request fails.
    """
    logger.info("ft_token_request_started")
    try:
        response = requests.post(
            FT_TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": _ft_client_id,
                "client_secret": _ft_client_secret,
                "scope": FT_SCOPE,
            },
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.error("ft_token_request_failed", exc_info=True)
        raise
    token: str = response.json()["access_token"]
    logger.info("ft_token_request_succeeded")
    return token


def _iso(dt: datetime) -> str:
    """Format a timezone-aware datetime as the ISO-8601 string France Travail expects.

    minCreationDate/maxCreationDate require full ISO-8601 with a trailing Z (e.g.
    "2026-07-28T00:00:00Z"), unlike minDateActualisation which takes a bare YYYY-MM-DD.
    Converts to UTC first so the literal Z suffix is always accurate, even if a caller
    passes an aware datetime in another timezone.

    Args:
        dt: A timezone-aware datetime.

    Returns:
        The ISO-8601 string in UTC with a literal Z suffix.
    """
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_params(
    rome_code: str,
    range_str: str,
    min_date: str | None = None,
    min_creation_date: str | None = None,
    max_creation_date: str | None = None,
) -> dict[str, str]:
    """Assemble the query params for one offres/search request.

    Args:
        rome_code: ROME occupation code (codeROME filter).
        range_str: Pagination range header value (e.g. "0-49").
        min_date: Optional minDateActualisation filter (YYYY-MM-DD) — the fixed business filter.
        min_creation_date: Optional minCreationDate filter (ISO-8601) — mechanical windowing only.
        max_creation_date: Optional maxCreationDate filter (ISO-8601) — mechanical windowing only.

    Returns:
        The params dict, omitting any filter left as None.
    """
    params: dict[str, str] = {"range": range_str, "codeROME": rome_code}
    if min_date:
        params["minDateActualisation"] = min_date
    if min_creation_date:
        params["minCreationDate"] = min_creation_date
    if max_creation_date:
        params["maxCreationDate"] = max_creation_date
    return params


def _get_page(http: requests.Session, rome_code: str, range_str: str, params: dict[str, str]) -> requests.Response:
    """Perform one offres/search GET, retrying on 429 up to MAX_RETRIES.

    Returns the raw response without calling raise_for_status — the caller decides how to
    interpret a non-2xx status (e.g. fetch_offers treats a 400 on a later page as the
    pagination ceiling rather than an error).

    Args:
        http: An authenticated requests.Session.
        rome_code: ROME code being fetched (for log correlation).
        range_str: Pagination range value (for log correlation).
        params: Fully built query params.

    Returns:
        The requests.Response of the first non-429 attempt.

    Raises:
        requests.RequestException: If the GET fails, or if MAX_RETRIES 429s are exhausted.
    """
    for attempt in range(MAX_RETRIES):
        try:
            response = http.get(FT_OFFERS_URL, params=params)
        except requests.RequestException:
            logger.error("ft_fetch_offers_page_failed", rome_code=rome_code, range=range_str, exc_info=True)
            raise
        if response.status_code != 429:
            return response
        retry_after = int(response.headers.get("Retry-After", "2"))
        logger.warning(
            "ft_fetch_rate_limited",
            rome_code=rome_code,
            attempt=attempt + 1,
            retry_after=retry_after,
        )
        time.sleep(retry_after)
    # `response` holds the last 429 response from the loop
    logger.error("ft_fetch_max_retries_exceeded", rome_code=rome_code, max_retries=MAX_RETRIES)
    raise requests.HTTPError(f"Max retries ({MAX_RETRIES}) exceeded on 429", response=response)


def _parse_page(response: requests.Response) -> tuple[list[dict], int | None]:
    """Extract the offers list and the total count from a successful page response.

    Args:
        response: A 2xx offres/search response (already past raise_for_status).

    Returns:
        (page, total) — page is the "resultats" list (empty for a 204 No Content with no
        body), total is the count parsed from Content-Range, or None when the header is absent.
    """
    content_range = response.headers.get("Content-Range", "")
    total = int(content_range.split("/")[-1]) if "/" in content_range else None
    # An empty result set comes back as 204 No Content with no body — response.json()
    # would raise on it. Guard on response.content so a 204 yields an empty page.
    page: list[dict] = response.json().get("resultats", []) if response.content else []
    return page, total


def fetch_offers(
    token: str,
    rome_code: str,
    min_date: str | None = None,
    min_creation_date: str | None = None,
    max_creation_date: str | None = None,
) -> list[dict]:
    """Fetch job offers for a ROME code using cursor-based pagination.

    Paginates in batches of PAGE_SIZE until the response returns fewer offers than
    PAGE_SIZE, Content-Range indicates the end of results, or France Travail's pagination
    depth ceiling is reached (a 400 on a page after the first — see below).

    Args:
        token: A valid OAuth2 access token.
        rome_code: ROME occupation code to filter offers (e.g. "M1805").
        min_date: Optional ISO date string (YYYY-MM-DD). When provided, only offers
            updated on or after this date are returned (minDateActualisation filter).
        min_creation_date: Optional ISO-8601 string (minCreationDate). Used by
            fetch_all_offers to slice the search by creation date — leave None otherwise.
        max_creation_date: Optional ISO-8601 string (maxCreationDate). Same windowing role.

    Note: min_date is formatted as YYYY-MM-DD (date only). The France Travail API
    interprets this as the start of the day in its local timezone — offers updated
    earlier on the cutoff day may be included.

    A 400 on the very first page (start == 0) is a genuinely invalid request (bad ROME
    code, bad date format...) and is re-raised. A 400 on a later page (start > 0), after
    at least one successful page, is France Travail's hard pagination depth ceiling — the
    offers collected so far are returned instead of failing the whole fetch, and a warning
    is logged. fetch_all_offers avoids this ceiling proactively via creation-date windowing;
    this handling is the last-resort safety net when a single day still exceeds the ceiling.

    Returns:
        A list of raw offer dicts as returned by the API (possibly truncated at the
        pagination ceiling — see above).

    Raises:
        requests.RequestException: If a page request fails, or a 400 occurs on the first page.
    """
    logger.info(
        "ft_fetch_offers_started",
        rome_code=rome_code,
        min_date=min_date,
        min_creation_date=min_creation_date,
        max_creation_date=max_creation_date,
    )
    offers: list[dict] = []
    start = 0

    with requests.Session() as http:
        http.headers.update({"Authorization": f"Bearer {token}"})
        while True:
            end = start + PAGE_SIZE - 1
            range_str = f"{start}-{end}"
            logger.info("ft_fetch_offers_page", rome_code=rome_code, range=range_str)
            params = _build_params(rome_code, range_str, min_date, min_creation_date, max_creation_date)
            response = _get_page(http, rome_code, range_str, params)

            try:
                response.raise_for_status()
            except requests.RequestException:
                if response.status_code == 400 and start > 0:
                    logger.warning(
                        "ft_pagination_ceiling_reached",
                        rome_code=rome_code,
                        range=range_str,
                        collected=len(offers),
                    )
                    break
                logger.error("ft_fetch_offers_page_failed", rome_code=rome_code, range=range_str, exc_info=True)
                raise

            page, total = _parse_page(response)
            offers.extend(page)

            if len(page) < PAGE_SIZE or (total is not None and len(offers) >= total):
                break

            start += PAGE_SIZE
            time.sleep(INTER_PAGE_SLEEP)

    logger.info("ft_fetch_offers_completed", rome_code=rome_code, total=len(offers))
    return offers


def _probe_total(
    token: str,
    rome_code: str,
    min_date: str | None = None,
    min_creation_date: str | None = None,
    max_creation_date: str | None = None,
) -> int:
    """Read the total offer count for a filter set via a single range=0-0 request.

    Reads Content-Range's total field without paginating — the cheap way for
    fetch_all_offers to decide how to slice the creation-date window.

    Args:
        token: A valid OAuth2 access token.
        rome_code: ROME occupation code being probed.
        min_date: Optional minDateActualisation filter (YYYY-MM-DD).
        min_creation_date: Optional minCreationDate filter (ISO-8601).
        max_creation_date: Optional maxCreationDate filter (ISO-8601).

    Returns:
        The total number of matching offers, or 0 when Content-Range is absent
        (e.g. the API's 204 No Content for an empty result set).

    Raises:
        requests.RequestException: If the probe request fails.
    """
    logger.info(
        "ft_probe_total_started",
        rome_code=rome_code,
        min_creation_date=min_creation_date,
        max_creation_date=max_creation_date,
    )
    params = _build_params(rome_code, "0-0", min_date, min_creation_date, max_creation_date)
    with requests.Session() as http:
        http.headers.update({"Authorization": f"Bearer {token}"})
        response = _get_page(http, rome_code, "0-0", params)
        try:
            response.raise_for_status()
        except requests.RequestException:
            logger.error("ft_probe_total_failed", rome_code=rome_code, exc_info=True)
            raise

    content_range = response.headers.get("Content-Range", "")
    total = int(content_range.split("/")[-1]) if "/" in content_range else 0
    logger.info("ft_probe_total_completed", rome_code=rome_code, total=total)
    return total


def _shrink_window(
    token: str,
    rome_code: str,
    min_date: str | None,
    cursor_end: datetime,
    start_width_days: int,
) -> tuple[datetime, int]:
    """Find a creation-date window ending at cursor_end whose total fits under the threshold.

    Halves the window width (starting from start_width_days) until the probed total drops
    below PAGINATION_SAFE_THRESHOLD or the MIN_WINDOW_DAYS floor is reached.

    Args:
        token: A valid OAuth2 access token.
        rome_code: ROME occupation code being fetched.
        min_date: Fixed minDateActualisation business filter (YYYY-MM-DD) or None.
        cursor_end: Upper creation-date bound of the window (the backward walk cursor).
        start_width_days: Initial window width in days before any halving.

    Returns:
        (window_start, total) — window_start is cursor_end minus the retained width; total
        is the last probed count. total may still exceed the threshold when even a
        MIN_WINDOW_DAYS window is too dense — fetch_offers' pagination-ceiling handling is
        then the last-resort safety net, and the caller logs an explicit warning.

    Raises:
        requests.RequestException: If a probe request fails.
    """
    width = start_width_days
    while True:
        window_start = cursor_end - timedelta(days=width)
        total = _probe_total(
            token,
            rome_code,
            min_date=min_date,
            min_creation_date=_iso(window_start),
            max_creation_date=_iso(cursor_end),
        )
        logger.info("ft_bisection_window_probed", rome_code=rome_code, width_days=width, total=total)
        if total < PAGINATION_SAFE_THRESHOLD or width <= MIN_WINDOW_DAYS:
            return window_start, total
        width = max(width // 2, MIN_WINDOW_DAYS)


def _extend_unique(offers: list[dict], seen_ids: set[str], new_offers: list[dict]) -> None:
    """Append offers whose ft id hasn't been seen yet, keeping the merged list deduplicated.

    Adjacent creation-date windows can share offers on their common boundary — dedup by the
    raw "id" field, same logic as agents/offer_fetching/main.py::_upsert_offers.

    Args:
        offers: Accumulator list, mutated in place.
        seen_ids: Set of ft ids already added, mutated in place.
        new_offers: Freshly fetched raw offer dicts to merge in.
    """
    for raw in new_offers:
        if raw["id"] not in seen_ids:
            seen_ids.add(raw["id"])
            offers.append(raw)


def _fetch_and_merge_window(
    token: str,
    rome_code: str,
    min_date: str | None,
    cursor_end: datetime,
    window_start: datetime | None,
    offers: list[dict],
    seen_ids: set[str],
) -> None:
    """Fetch one creation-date window and merge it deduplicated into the running result.

    Args:
        token: A valid OAuth2 access token.
        rome_code: ROME occupation code being fetched.
        min_date: Fixed minDateActualisation business filter (YYYY-MM-DD) or None.
        cursor_end: Upper creation-date bound (maxCreationDate) of the window.
        window_start: Lower creation-date bound (minCreationDate), or None to fetch the whole
            tail — everything created at or before cursor_end — once it fits under the threshold.
        offers: Accumulator list, mutated in place via _extend_unique.
        seen_ids: Set of ft ids already added, mutated in place via _extend_unique.
    """
    min_creation_date = _iso(window_start) if window_start is not None else None
    window_offers = fetch_offers(
        token,
        rome_code,
        min_date=min_date,
        min_creation_date=min_creation_date,
        max_creation_date=_iso(cursor_end),
    )
    logger.info(
        "ft_bisection_window_fetched",
        rome_code=rome_code,
        window_start=min_creation_date,
        window_end=_iso(cursor_end),
        count=len(window_offers),
    )
    _extend_unique(offers, seen_ids, window_offers)


def fetch_all_offers(token: str, rome_code: str, min_date: str | None = None) -> list[dict]:
    """Fetch every offer for a ROME code, walking backwards through creation-date windows.

    Works around France Travail's pagination depth ceiling: no single fetch_offers call can
    reach past ~3050 results, so a high-volume ROME code (e.g. M1507) would otherwise lose
    every offer beyond the ceiling. minDateActualisation (min_date) stays the fixed business
    filter; minCreationDate/maxCreationDate are used only mechanically to slice the total into
    sub-threshold windows, ANDed with min_date. The walk probes cheaply (range=0-0) before
    each fetch and adapts the window width to the real offer density — wide windows when
    offers are sparse, narrow ones when dense. Windows are merged deduplicated by ft id.

    Args:
        token: A valid OAuth2 access token.
        rome_code: ROME occupation code to fetch (e.g. "M1805").
        min_date: Optional minDateActualisation filter (YYYY-MM-DD) — offers updated on or
            after this date. Passed unchanged to every underlying fetch/probe.

    Returns:
        The deduplicated list of raw offer dicts across all windows. May still miss offers
        in a single day that alone exceeds the ceiling (logged as a warning) — an accepted
        degradation, not silent data loss.

    Raises:
        requests.RequestException: If a probe or a non-ceiling page request fails.
    """
    logger.info("ft_fetch_all_offers_started", rome_code=rome_code, min_date=min_date)
    offers: list[dict] = []
    seen_ids: set[str] = set()
    cursor_end = datetime.now(timezone.utc)
    next_width = DEFAULT_WINDOW_DAYS

    while True:
        # Everything created at or before cursor_end (min_date still applied). Shrinks as the
        # cursor walks back in time; reaching 0 means nothing older is left — stop.
        total_below = _probe_total(token, rome_code, min_date=min_date, max_creation_date=_iso(cursor_end))
        if total_below == 0:
            break
        if total_below < PAGINATION_SAFE_THRESHOLD:
            # The whole remaining tail fits in one paginated fetch — no windowing needed.
            _fetch_and_merge_window(token, rome_code, min_date, cursor_end, None, offers, seen_ids)
            break

        window_start, total_window = _shrink_window(token, rome_code, min_date, cursor_end, next_width)
        if total_window == 0:
            # A creation-date gap right below cursor_end (bursty/seasonal posting): total_below is
            # over threshold only because of an older burst, and this window is empty. Skip it
            # without a fetch (a 0-result fetch would be a bodyless 204) and keep walking back.
            cursor_end = window_start
            continue
        if total_window >= PAGINATION_SAFE_THRESHOLD:
            logger.warning(
                "ft_bisection_leaf_still_over_threshold",
                rome_code=rome_code,
                window_start=_iso(window_start),
                window_end=_iso(cursor_end),
                total=total_window,
            )
        _fetch_and_merge_window(token, rome_code, min_date, cursor_end, window_start, offers, seen_ids)
        # Reuse the width that just worked as the next probe's starting point — adjacent
        # windows usually have similar density, so this avoids re-shrinking from 30 days.
        next_width = max((cursor_end - window_start).days, MIN_WINDOW_DAYS)
        cursor_end = window_start

    logger.info("ft_fetch_all_offers_completed", rome_code=rome_code, total=len(offers))
    return offers
