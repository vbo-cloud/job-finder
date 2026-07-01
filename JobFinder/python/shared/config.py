"""Shared configuration constants read from environment variables."""

import os

# 60 jours : fenêtre de fetch France Travail (minDateActualisation).
# Configurable via CLEANUP_OFFER_MAX_AGE_DAYS pour ajuster sans redéploiement du code.
OFFER_MAX_AGE_DAYS = int(os.getenv("CLEANUP_OFFER_MAX_AGE_DAYS", "60"))
MATCHING_SCORE_THRESHOLD = float(os.getenv("MATCHING_SCORE_THRESHOLD", "0.5"))
# 2 jours : une offre non revue lors des derniers fetches est considérée clôturée.
# L'agent fetch tourne 2×/jour ; 2 jours = 4 cycles de grâce avant suppression.
# Configurable via CLEANUP_COLLECTED_AGE_DAYS.
CLEANUP_COLLECTED_AGE_DAYS = int(os.getenv("CLEANUP_COLLECTED_AGE_DAYS", "2"))
