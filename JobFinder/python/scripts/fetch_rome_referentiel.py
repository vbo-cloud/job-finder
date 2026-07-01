"""Fetch the France Travail ROME métier referential and save it as a versioned JSON file.

Usage:
    FT_CLIENT_ID=... FT_CLIENT_SECRET=... python scripts/fetch_rome_referentiel.py

Requires FT application credentials with the api_rome-metierv1 scope enabled.
Run from the JobFinder/python/ directory. Saves to shared/rome_referentiel.json.

The generated file is committed to the repo so agents can load it at startup
without a network dependency. Re-run this script to refresh the referential
when France Travail publishes a new ROME version.
"""

import json
import os
import time
from pathlib import Path

import requests
import structlog

FT_TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
FT_ROME_URL = "https://api.francetravail.io/partenaire/rome/v1/metier"
FT_ROME_SCOPE = "api_rome-metierv1"
OUTPUT_PATH = Path(__file__).parent.parent / "shared" / "rome_referentiel.json"
PAGE_SIZE = 150
INTER_PAGE_SLEEP = 0.3
MIN_EXPECTED_CODES = 400

logger = structlog.get_logger()

_ft_client_id = os.environ.get("FT_CLIENT_ID")
if not _ft_client_id:
    raise ValueError("FT_CLIENT_ID environment variable is not set")

_ft_client_secret = os.environ.get("FT_CLIENT_SECRET")
if not _ft_client_secret:
    raise ValueError("FT_CLIENT_SECRET environment variable is not set")


def _get_access_token() -> str:
    """Obtain an OAuth2 access token with the ROME API scope.

    Returns:
        The access token string.

    Raises:
        ValueError: If the token request fails (e.g. scope not enabled on the application).
        requests.RequestException: On network error.
    """
    try:
        response = requests.post(
            FT_TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": _ft_client_id,
                "client_secret": _ft_client_secret,
                "scope": FT_ROME_SCOPE,
            },
        )
        response.raise_for_status()
    except requests.HTTPError as e:
        raise ValueError(
            f"Token request failed ({response.status_code}). "
            "Ensure the FT application has the api_rome-metierv1 scope enabled."
        ) from e
    return response.json()["access_token"]


def _fetch_all_metiers(token: str) -> dict[str, str]:
    """Fetch all ROME métiers from the FT API using range-based pagination.

    Args:
        token: A valid OAuth2 access token.

    Returns:
        Dict mapping each ROME code to its official French label.

    Raises:
        requests.RequestException: If any page request fails.
    """
    referentiel: dict[str, str] = {}
    start = 0

    with requests.Session() as http:
        http.headers.update({"Authorization": f"Bearer {token}"})
        while True:
            end = start + PAGE_SIZE - 1
            logger.info("rome_fetch_page", range=f"{start}-{end}", total_so_far=len(referentiel))
            try:
                response = http.get(FT_ROME_URL, headers={"Range": f"{start}-{end}"})
                response.raise_for_status()
            except requests.RequestException:
                logger.error("rome_fetch_page_failed", range=f"{start}-{end}", exc_info=True)
                raise

            items: list[dict] = response.json()
            for item in items:
                code: str = item.get("code", "")
                label: str = item.get("libelle", "")
                if code and label:
                    referentiel[code] = label

            content_range = response.headers.get("Content-Range", "")
            total = int(content_range.split("/")[-1]) if "/" in content_range else None

            if len(items) < PAGE_SIZE or (total is not None and len(referentiel) >= total):
                break

            start += PAGE_SIZE
            time.sleep(INTER_PAGE_SLEEP)

    return referentiel


def main() -> None:
    """Fetch the ROME referential from France Travail and save it to shared/rome_referentiel.json."""
    logger.info("fetch_rome_referentiel_started")

    token = _get_access_token()
    logger.info("token_obtained")

    referentiel = _fetch_all_metiers(token)
    logger.info("fetch_complete", total_codes=len(referentiel))

    if len(referentiel) < MIN_EXPECTED_CODES:
        logger.warning(
            "referentiel_looks_incomplete",
            total=len(referentiel),
            expected_min=MIN_EXPECTED_CODES,
        )

    OUTPUT_PATH.write_text(
        json.dumps(referentiel, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    logger.info("saved", path=str(OUTPUT_PATH), total_codes=len(referentiel))


if __name__ == "__main__":
    main()
