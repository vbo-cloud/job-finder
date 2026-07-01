"""Regression tests for webapp Pydantic schemas.

Validates that every valid CV status is accepted by CVListItemOut, so a new
status added to the DB constraint or matching agent is caught immediately if
the schema is not updated in sync.
"""
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "webapp"))

from schemas import CVListItemOut  # noqa: E402

_BASE = {
    "id": uuid.uuid4(),
    "name": "test.pdf",
    "uploaded_at": datetime(2024, 1, 1),
    "match_count": 0,
    "unseen_count": 0,
    "has_thumbnail": False,
}


@pytest.mark.parametrize("status", ["pending", "processing", "done", "matched", "error"])
def test_cv_list_item_out_accepts_all_valid_statuses(status: str) -> None:
    item = CVListItemOut(**{**_BASE, "status": status})
    assert item.status == status


def test_cv_list_item_out_rejects_unknown_status() -> None:
    with pytest.raises(Exception):
        CVListItemOut(**{**_BASE, "status": "unknown"})
