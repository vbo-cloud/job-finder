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
# courant, cf. ADR-018). Fixé à 20 en bêta — inclus dans le palier gratuit, ne consomme aucun crédit.
MATCH_ANALYSIS_AUTO_TOP_N = int(os.getenv("MATCH_ANALYSIS_AUTO_TOP_N", "20"))
# 2 jours : une offre non revue lors des derniers fetches est considérée clôturée.
# L'agent fetch tourne 1×/jour (offer_fetch_scheduler, 18h Europe/Paris) ; 2 jours = 2 cycles
# de grâce avant suppression. Configurable via CLEANUP_COLLECTED_AGE_DAYS.
CLEANUP_COLLECTED_AGE_DAYS = int(os.getenv("CLEANUP_COLLECTED_AGE_DAYS", "2"))
# Température basse + seed fixe pour les appels d'analyse GPT-4o-mini (qualité CV, paires CV<->offre) :
# la cohérence du score/de la review d'une exécution à l'autre sur le même contenu prime sur la
# variété créative. OpenAI ne garantit pas un déterminisme à 100 % même avec seed fixé, mais réduit
# fortement la variance observée (contrairement à la température par défaut de 1.0).
ANALYSIS_TEMPERATURE = float(os.getenv("ANALYSIS_TEMPERATURE", "0"))
ANALYSIS_SEED = int(os.getenv("ANALYSIS_SEED", "42"))
# Pénalité de score quand l'expérience minimale demandée par une offre dépasse le plafond d'années
# associé au niveau d'expérience déclaré par le candidat. Volontairement progressive (pas d'exclusion) :
# un écart de 2-3 ans sur une offre par ailleurs pertinente ne doit coûter que quelques points, pas
# faire disparaître l'offre — voir docs/prompts/prompt-matching-experience-penalty-and-skills-signal.md.
EXPERIENCE_PENALTY_PER_YEAR_GAP = float(os.getenv("EXPERIENCE_PENALTY_PER_YEAR_GAP", "0.03"))
EXPERIENCE_MAX_PENALTY = float(os.getenv("EXPERIENCE_MAX_PENALTY", "0.3"))
# 5 minutes : borne la fréquence du dispatch start-matching + réanalyse CV déclenché par un
# changement d'intention (PUT /profile) — un utilisateur qui enchaîne les sauvegardes ne doit
# jamais déclencher un volume illimité d'appels IA, même gratuits. Le profil est toujours
# sauvegardé immédiatement ; seul le déclenchement du recalcul est retardé.
INTENT_DISPATCH_COOLDOWN_SECONDS = int(os.getenv("INTENT_DISPATCH_COOLDOWN_SECONDS", "300"))
# 24h : borne la fréquence des emails d'alerte envoyés à Vincent quand un utilisateur à 0
# crédit reclique plusieurs fois sur "Je voudrais plus de crédits". more_credits_requested_at
# n'est réécrit qu'après un envoi d'email réussi (jamais sur un clic dédupliqué ni sur un
# échec ACS) — sinon un premier envoi en échec démarrerait quand même le cooldown et
# bloquerait silencieusement les tentatives suivantes pendant 24h sans jamais alerter
# Vincent (voir PR #254 dans docs/JOURNAL.md).
MORE_CREDITS_REQUEST_COOLDOWN_SECONDS = int(os.getenv("MORE_CREDITS_REQUEST_COOLDOWN_SECONDS", "86400"))
