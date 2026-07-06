"""Tests for shared/geo.py — department/region parsing helpers."""

import pytest

from shared.geo import (
    department_from_commune,
    parse_department_from_location,
    parse_region_from_location,
    regions_intersecting,
)


class TestParseDepartmentFromLocation:
    @pytest.mark.parametrize(
        ("location", "expected"),
        [
            ("75 - Paris", "75"),
            ("2A - Ajaccio", "2A"),
            ("2a - ajaccio", "2A"),
            ("971 - Pointe-à-Pitre", "971"),
            ("987 - Papeete", "987"),
            ("988 - Nouméa", "988"),
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
            ("98735", "987"),
        ],
    )
    def test_derives_expected_department(self, commune_code: str, expected: str):
        assert department_from_commune(commune_code) == expected


class TestParseRegionFromLocation:
    @pytest.mark.parametrize(
        ("location", "expected"),
        [
            ("Île-de-France", "ile-de-france"),
            ("Ile-de-France", "ile-de-france"),
            ("ILE-DE-FRANCE", "ile-de-france"),
            ("Bourgogne-Franche-Comté", "bourgogne-franche-comte"),
            ("Centre-Val de Loire", "centre-val de loire"),
            ("Provence-Alpes-Côte d'Azur", "provence-alpes-cote dazur"),
            ("75 - Paris", None),
            ("France", None),
            ("Luxembourg", None),
            (None, None),
            ("", None),
        ],
    )
    def test_parses_expected_region(self, location: str | None, expected: str | None):
        assert parse_region_from_location(location) == expected


class TestRegionsIntersecting:
    def test_finds_region_for_single_department(self):
        assert regions_intersecting({"69"}) == {"auvergne-rhone-alpes"}

    def test_finds_region_for_paris_department(self):
        assert regions_intersecting({"75"}) == {"ile-de-france"}

    def test_returns_multiple_regions_for_scattered_departments(self):
        assert regions_intersecting({"69", "75"}) == {"auvergne-rhone-alpes", "ile-de-france"}

    def test_returns_empty_set_for_unknown_department(self):
        assert regions_intersecting({"00"}) == set()
