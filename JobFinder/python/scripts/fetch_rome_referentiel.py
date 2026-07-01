"""Fetch the France Travail ROME métier referential and save it as a versioned JSON file.

Usage:
    FT_CLIENT_ID=... FT_CLIENT_SECRET=... python scripts/fetch_rome_referentiel.py

Uses the same FT credentials as the offer_fetching agent (api_offresdemploiv2 scope).
Run from the JobFinder/python/ directory. Saves to shared/rome_referentiel.json.

The generated file is committed to the repo so agents can load it at startup
without a network dependency. Re-run this script to refresh the referential
when France Travail publishes a new ROME version.
"""

import json
import os
from pathlib import Path

import requests
import structlog

FT_TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
FT_ROME_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/referentiel/metiers"
FT_SCOPE = "api_offresdemploiv2 o2dsoffre"
OUTPUT_PATH = Path(__file__).parent.parent / "shared" / "rome_referentiel.json"
MIN_EXPECTED_CODES = 400

logger = structlog.get_logger()

_ft_client_id = os.environ.get("FT_CLIENT_ID")
if not _ft_client_id:
    raise ValueError("FT_CLIENT_ID environment variable is not set")

_ft_client_secret = os.environ.get("FT_CLIENT_SECRET")
if not _ft_client_secret:
    raise ValueError("FT_CLIENT_SECRET environment variable is not set")


def _get_access_token() -> str:
    """Obtain an OAuth2 access token for the FT offers API.

    Returns:
        The access token string.

    Raises:
        requests.RequestException: If the token request fails.
    """
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
        logger.error("token_request_failed", exc_info=True)
        raise
    return response.json()["access_token"]


def _fetch_all_metiers(token: str) -> dict[str, str]:
    """Fetch all ROME métiers from the FT v2 referentiel endpoint.

    The /referentiel/metiers endpoint returns the complete list in a single
    response — no pagination required.

    Args:
        token: A valid OAuth2 access token.

    Returns:
        Dict mapping each ROME code to its official French label.

    Raises:
        requests.RequestException: If the request fails.
    """
    logger.info("rome_fetch_started")
    try:
        response = requests.get(
            FT_ROME_URL,
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.error("rome_fetch_failed", exc_info=True)
        raise

    items: list[dict] = response.json()
    referentiel: dict[str, str] = {
        item["code"]: item["libelle"]
        for item in items
        if item.get("code") and item.get("libelle")
    }
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
