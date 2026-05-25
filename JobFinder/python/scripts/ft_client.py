"""France Travail API client — authenticate and paginate job offer results."""

import os

import requests
import structlog

FT_TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
FT_OFFERS_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
FT_SCOPE = "api_offresdemploi_v2 o2dsillage"
PAGE_SIZE = 50

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


def fetch_offers(token: str, rome_code: str) -> list[dict]:
    """Fetch all job offers for a given ROME code using cursor-based pagination.

    Paginates through results in batches of PAGE_SIZE until the response returns
    fewer offers than PAGE_SIZE or Content-Range indicates the end of results.

    Args:
        token: A valid OAuth2 access token.
        rome_code: ROME occupation code to filter offers (e.g. "M1805").

    Returns:
        A list of raw offer dicts as returned by the API.

    Raises:
        requests.RequestException: If any page request fails.
    """
    logger.info("ft_fetch_offers_started", rome_code=rome_code)
    offers: list[dict] = []
    start = 0

    with requests.Session() as http:
        http.headers.update({"Authorization": f"Bearer {token}"})
        while True:
            end = start + PAGE_SIZE - 1
            logger.info("ft_fetch_offers_page", rome_code=rome_code, range=f"{start}-{end}")
            try:
                response = http.get(
                    FT_OFFERS_URL,
                    params={"range": f"{start}-{end}", "codeROME": rome_code},
                )
                response.raise_for_status()
            except requests.RequestException:
                logger.error("ft_fetch_offers_page_failed", rome_code=rome_code, range=f"{start}-{end}", exc_info=True)
                raise

            content_range = response.headers.get("Content-Range", "")
            total = int(content_range.split("/")[-1]) if "/" in content_range else None

            page: list[dict] = response.json().get("resultats", [])
            offers.extend(page)

            if len(page) < PAGE_SIZE or (total is not None and len(offers) >= total):
                break

            start += PAGE_SIZE

    logger.info("ft_fetch_offers_completed", rome_code=rome_code, total=len(offers))
    return offers
