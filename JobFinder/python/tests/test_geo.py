"""Tests for shared/geo.py — department parsing helpers."""

import pytest

from shared.geo import department_from_commune, parse_department_from_location


class TestParseDepartmentFromLocation:
    @pytest.mark.parametrize(
        ("location", "expected"),
        [
            ("75 - Paris", "75"),
            ("2A - Ajaccio", "2A"),
            ("2a - ajaccio", "2A"),
            ("971 - Pointe-à-Pitre", "971"),
            ("France", None),
            ("Luxembourg", None),
            (None, None),
            ("", None),
        ],
    )
    def test_parses_expected_prefix(self, location: str | None, expected: str | None):
        assert parse_department_from_location(location) == expected


class TestDepartmentFromCommune:
    @pytest.mark.parametrize(
        ("commune_code", "expected"),
        [
            ("75101", "75"),
            ("2A004", "2A"),
            ("97105", "971"),
        ],
    )
    def test_derives_expected_department(self, commune_code: str, expected: str):
        assert department_from_commune(commune_code) == expected
