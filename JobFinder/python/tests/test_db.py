"""Tests for shared/db.py::run_migrations.

Covers the advisory-lock serialization added around `alembic upgrade head`:
lock acquired before the upgrade, released after (including on failure), and
a lock-acquisition failure propagating without ever running the upgrade.
"""
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture
from sqlalchemy.exc import SQLAlchemyError

from shared.db import ALEMBIC_MIGRATION_LOCK_ID, run_migrations


def _patched_connection(mocker: MockerFixture, conn: MagicMock) -> MagicMock:
    conn.__enter__.return_value = conn
    conn.__exit__.return_value = False
    conn.execution_options.return_value = conn
    mock_engine = MagicMock()
    mock_engine.connect.return_value = conn
    mocker.patch("shared.db.get_engine", return_value=mock_engine)
    return conn


class TestRunMigrations:
    def test_acquires_lock_runs_upgrade_then_releases_lock(self, mocker: MockerFixture) -> None:
        conn = _patched_connection(mocker, MagicMock())
        # Attach execute and upgrade to one parent mock so their combined call order
        # (not just each mock's own calls) can be asserted — two independent mocks would
        # let an implementation that upgrades before locking (or after unlocking) pass.
        parent = MagicMock()
        parent.attach_mock(conn.execute, "execute")
        mock_upgrade = mocker.patch("shared.db.command.upgrade")
        parent.attach_mock(mock_upgrade, "upgrade")

        run_migrations()

        mock_upgrade.assert_called_once()
        sql_calls = [str(c.args[0]) for c in conn.execute.call_args_list]
        lock_calls = [c for c in conn.execute.call_args_list if "pg_advisory_lock" in str(c.args[0])]
        unlock_calls = [c for c in conn.execute.call_args_list if "pg_advisory_unlock" in str(c.args[0])]
        assert len(lock_calls) == 1
        assert len(unlock_calls) == 1
        assert lock_calls[0].args[1] == {"key": ALEMBIC_MIGRATION_LOCK_ID}
        assert unlock_calls[0].args[1] == {"key": ALEMBIC_MIGRATION_LOCK_ID}
        # The combined call order across both mocks must be: lock, upgrade, unlock.
        ordered_names = [c[0] for c in parent.mock_calls]
        assert ordered_names == ["execute", "upgrade", "execute"]

    def test_releases_lock_even_when_upgrade_raises(self, mocker: MockerFixture) -> None:
        conn = _patched_connection(mocker, MagicMock())
        mocker.patch("shared.db.command.upgrade", side_effect=RuntimeError("boom"))

        with pytest.raises(RuntimeError):
            run_migrations()

        unlock_calls = [c for c in conn.execute.call_args_list if "pg_advisory_unlock" in str(c.args[0])]
        assert len(unlock_calls) == 1

    def test_lock_acquisition_failure_never_runs_upgrade(self, mocker: MockerFixture) -> None:
        conn = MagicMock()
        conn.execute.side_effect = SQLAlchemyError("cannot acquire lock")
        _patched_connection(mocker, conn)
        mock_upgrade = mocker.patch("shared.db.command.upgrade")

        with pytest.raises(SQLAlchemyError):
            run_migrations()

        mock_upgrade.assert_not_called()
