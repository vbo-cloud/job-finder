"""Pytest configuration for cleanup agent tests.

Adds the python/ root and agents/cleanup/ directories to sys.path so that
`from shared.* import ...` and `from main import ...` both resolve correctly.

Also stubs DATABASE_URL before any import touches shared.db — the module raises
ValueError at import time if the env var is absent.
"""

import os
import sys
from pathlib import Path

# Stub DATABASE_URL before shared.db is imported (it raises ValueError otherwise).
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

_here = Path(__file__).parent
sys.path.insert(0, str(_here.parents[2]))  # python/          → shared.*
sys.path.insert(0, str(_here.parent))      # agents/cleanup/  → main
