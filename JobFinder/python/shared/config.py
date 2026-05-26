"""Shared configuration constants read from environment variables."""

import os

# 60 jours : durée de vie raisonnable pour une offre France Travail.
# Au-delà, l'offre est probablement pourvue ou expirée côté France Travail.
# Configurable via CLEANUP_OFFER_MAX_AGE_DAYS pour ajuster sans redéploiement du code.
OFFER_MAX_AGE_DAYS = int(os.getenv("CLEANUP_OFFER_MAX_AGE_DAYS", "60"))
MATCHING_TOP_K = int(os.getenv("MATCHING_TOP_K", "20"))
