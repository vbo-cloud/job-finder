"""Tests for agents/webapp/auth.py — identity claim extraction from validated JWTs.

Signature validation itself is not covered here (delegated to python-jose):
_decode_token/_get_jwks are patched and the tests verify what
get_current_identity builds from the decoded payload.
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

_PYTHON_DIR = Path(__file__).parent.parent
_WEBAPP_DIR = _PYTHON_DIR / "agents" / "webapp"
for _d in [str(_PYTHON_DIR), str(_WEBAPP_DIR)]:
    if _d not in sys.path:
        sys.path.insert(0, _d)

import auth  # noqa: E402

_SUB = "opaque-pairwise-sub"


def _identity_for(payload: dict) -> auth.UserIdentity:
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="fake-token")
    with (
        patch.object(auth, "_get_jwks", return_value={}),
        patch.object(auth, "_decode_token", return_value=payload),
    ):
        return auth.get_current_identity(creds)


class TestGetCurrentIdentity:
    def test_extracts_sub_email_and_name(self):
        identity = _identity_for(
            {"sub": _SUB, "email": "user@example.test", "name": "Jane Doe"}
        )

        assert identity == auth.UserIdentity(
            user_id=_SUB, email="user@example.test", display_name="Jane Doe"
        )

    def test_falls_back_to_b2c_style_emails_list(self):
        identity = _identity_for({"sub": _SUB, "emails": ["first@example.test", "second@example.test"]})

        assert identity.email == "first@example.test"

    def test_missing_optional_claims_yield_none(self):
        identity = _identity_for({"sub": _SUB})

        assert identity.email is None
        assert identity.display_name is None

    def test_missing_sub_raises_401(self):
        with pytest.raises(HTTPException) as exc_info:
            _identity_for({"name": "No Sub"})

        assert exc_info.value.status_code == 401

    def test_get_current_user_returns_the_sub(self):
        identity = auth.UserIdentity(user_id=_SUB, email=None, display_name=None)

        assert auth.get_current_user(identity) == _SUB
