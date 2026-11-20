"""Pytest configuration for notifications agent tests.

Adds the python/ root and agents/notifications/ directories to sys.path so that
`from shared.* import ...` and `from main import ...` both resolve correctly.

Also stubs DATABASE_URL, ACS_EMAIL_ENDPOINT_HOSTNAME, ACS_EMAIL_SENDER_ADDRESS,
FRONTEND_URL, WEBAPP_BASE_URL, and NOTIFICATIONS_UNSUBSCRIBE_SECRET before any import
touches shared.db, shared.unsubscribe_token, or main — shared.db raises ValueError at
import time if DATABASE_URL is absent, shared.unsubscribe_token does the same for
NOTIFICATIONS_UNSUBSCRIBE_SECRET, and main.py does the same for the remaining four at
module level (see its "Expected environment variables" docstring).
"""

import os
import sys
from pathlib import Path

# Stub required environment variables before shared.db / shared.unsubscribe_token / main
# is imported (all three raise ValueError otherwise).
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ACS_EMAIL_ENDPOINT_HOSTNAME", "acs-test.france.communication.azure.com")
os.environ.setdefault("ACS_EMAIL_SENDER_ADDRESS", "jobfinder_donotreply@vincentboutin.dev")
os.environ.setdefault("FRONTEND_URL", "https://jobfinder.vincentboutin.dev")
os.environ.setdefault("WEBAPP_BASE_URL", "https://api.jobfinder.vincentboutin.dev")
os.environ.setdefault("NOTIFICATIONS_UNSUBSCRIBE_SECRET", "test-unsubscribe-secret")

_here = Path(__file__).parent
sys.path.insert(0, str(_here.parents[2]))  # python/               → shared.*
sys.path.insert(0, str(_here.parent))      # agents/notifications/ → main
