"""Shared configuration constants read from environment variables."""

import os

# 60 jours : fenêtre de fetch France Travail (minDateActualisation).
# Consommé par offer_fetching/main.py uniquement — cleanup n'utilise plus cette valeur.
# Configurable via CLEANUP_OFFER_MAX_AGE_DAYS pour ajuster sans redéploiement du code.
OFFER_MAX_AGE_DAYS = int(os.getenv("CLEANUP_OFFER_MAX_AGE_DAYS", "60"))
MATCHING_SCORE_THRESHOLD = float(os.getenv("MATCHING_SCORE_THRESHOLD", "0.5"))
# Poids de l'embedding "intention" (expérience/recherche/description du profil) dans le
# score final ; le complément (1 - INTENT_EMBEDDING_WEIGHT) pondère la similarité CV<->offre.
INTENT_EMBEDDING_WEIGHT = float(os.getenv("INTENT_EMBEDDING_WEIGHT", "0.3"))
assert 0 < INTENT_EMBEDDING_WEIGHT < 1, (
    f"INTENT_EMBEDDING_WEIGHT must be strictly between 0 and 1, got {INTENT_EMBEDDING_WEIGHT}"
)
# Nombre de matchs analysés automatiquement par CV à chaque run de matching (top N par score
# courant, cf. ADR-018). Fixé à 1 en bêta — inclus dans le palier gratuit, ne consomme aucun crédit.
MATCH_ANALYSIS_AUTO_TOP_N = int(os.getenv("MATCH_ANALYSIS_AUTO_TOP_N", "1"))
# 2 jours : une offre non revue lors des derniers fetches est considérée clôturée.
# L'agent fetch tourne 2×/jour ; 2 jours = 4 cycles de grâce avant suppression.
# Configurable via CLEANUP_COLLECTED_AGE_DAYS.
CLEANUP_COLLECTED_AGE_DAYS = int(os.getenv("CLEANUP_COLLECTED_AGE_DAYS", "2"))
