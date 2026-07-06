"""Tests for agents/webapp/main.py — CORS configuration.

Importing main.py pulls in routers/cv.py, which constructs a BlobServiceClient
at module level; patched here the same way test_webapp_cv.py does, so the
import doesn't touch real Azure credentials. Building the FastAPI app object
does not run the lifespan (migrations only run on ASGI startup), so no real
DB connection is attempted either.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_PYTHON_DIR = Path(__file__).parent.parent
_WEBAPP_DIR = _PYTHON_DIR / "agents" / "webapp"
for _d in [str(_PYTHON_DIR), str(_WEBAPP_DIR)]:
    if _d not in sys.path:
        sys.path.insert(0, _d)

# The patch must wrap the import itself, not decorate a test function:
# BlobServiceClient(...) is constructed once at cv.py's module level (via
# main.py's router include), so it needs to be mocked at import time — by
# the time a test runs, the real call has already happened or not at all.
_mock_bsc = MagicMock()
with patch("azure.storage.blob.BlobServiceClient", return_value=_mock_bsc):
    import main  # noqa: E402


def _cors_middleware_kwargs() -> dict:
    for middleware in main.app.user_middleware:
        if middleware.cls.__name__ == "CORSMiddleware":
            return middleware.kwargs
    raise AssertionError("CORSMiddleware not registered on the app")


class TestCorsConfiguration:
    def test_allows_patch_method(self):
        # PATCH powers /cv/{cv_id}/matches/{offer_id}/seen and
        # /cv/{cv_id}/mark-all-seen — without it in allow_methods, the
        # browser's preflight OPTIONS request is rejected and the PATCH
        # never reaches the backend (a silent failure, visible only in
        # devtools as a CORS-blocked network error).
        assert "PATCH" in _cors_middleware_kwargs()["allow_methods"]

    def test_allows_expected_methods(self):
        methods = set(_cors_middleware_kwargs()["allow_methods"])
        assert {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"} <= methods
