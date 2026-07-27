"""Shared pytest configuration — env var stubs and sys.path for all agent tests.

Env vars must be set before any module-level import that checks them.
DATABASE_URL is set to a valid DSN format so shared/db.py passes its check;
the actual engine is never created in tests because get_session() is always patched.
"""
import os
import sys
from pathlib import Path

_ENV_STUBS: dict[str, str] = {
    "DATABASE_URL": "postgresql://test:test@localhost/testdb",
    "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
    "FT_CLIENT_ID": "test-ft-client-id",
    "FT_CLIENT_SECRET": "test-ft-client-secret",
    "ENTRA_EXTERNAL_TENANT_ID": "00000000-0000-0000-0000-000000000000",
    "ENTRA_EXTERNAL_CLIENT_ID": "00000000-0000-0000-0000-000000000001",
    "AZURE_STORAGE_ACCOUNT_URL": "https://teststorage.blob.core.windows.net",
    "AZURE_SERVICEBUS_FULLY_QUALIFIED_NAMESPACE": "test.servicebus.windows.net",
    "NOTIFICATIONS_UNSUBSCRIBE_SECRET": "test-unsubscribe-secret",
    "ACS_EMAIL_ENDPOINT_HOSTNAME": "test-acs.communication.azure.com",
    "ACS_EMAIL_SENDER_ADDRESS": "donotreply@test.example.com",
    "OWNER_ALERT_EMAIL": "owner@test.example.com",
    # Pinned to a deployment that supports temperature/seed so existing determinism
    # assertions (kwargs["temperature"]/["seed"]) hold without every test needing to
    # patch AZURE_OPENAI_CV_ANALYSIS_DEPLOYMENT itself — the module default is
    # gpt-5-mini, which _sampling_kwargs() deliberately omits them for.
    "AZURE_OPENAI_CV_ANALYSIS_DEPLOYMENT": "gpt-4o-mini",
}

for key, value in _ENV_STUBS.items():
    os.environ.setdefault(key, value)

# Expose shared/ and agents/ to pytest so all from-shared imports resolve.
_PYTHON_DIR = Path(__file__).parent.parent
if str(_PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(_PYTHON_DIR))
