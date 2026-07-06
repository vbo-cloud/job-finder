"""Geographic helpers shared across agents — INSEE commune/department parsing."""

import re
import unicodedata

DEPARTMENT_PREFIX_RE = re.compile(r"^\s*(2[AB]|97[1-8]|98[6-9]|\d{2})\s*-", re.IGNORECASE)

# Region names as normalized by _normalize_region() (ASCII, lowercase, no
# apostrophe) mapped to their department codes. France Travail sometimes
# gives a region-level label instead of a department-prefixed one (e.g.
# "Île-de-France" rather than "75 - Paris") when an offer has no more precise
# location — covers the 13 metropolitan regions plus the 5 single-department
# overseas regions (DROM).
REGION_DEPARTMENTS: dict[str, frozenset[str]] = {
    "auvergne-rhone-alpes": frozenset({"01", "03", "07", "15", "26", "38", "42", "43", "63", "69", "73", "74"}),
    "bourgogne-franche-comte": frozenset({"21", "25", "39", "58", "70", "71", "89", "90"}),
    "bretagne": frozenset({"22", "29", "35", "56"}),
    "centre-val de loire": frozenset({"18", "28", "36", "37", "41", "45"}),
    "corse": frozenset({"2A", "2B"}),
    "grand est": frozenset({"08", "10", "51", "52", "54", "55", "57", "67", "68", "88"}),
    "hauts-de-france": frozenset({"02", "59", "60", "62", "80"}),
    "ile-de-france": frozenset({"75", "77", "78", "91", "92", "93", "94", "95"}),
    "normandie": frozenset({"14", "27", "50", "61", "76"}),
    "nouvelle-aquitaine": frozenset({"16", "17", "19", "23", "24", "33", "40", "47", "64", "79", "86", "87"}),
    "occitanie": frozenset({"09", "11", "12", "30", "31", "32", "34", "46", "48", "65", "66", "81", "82"}),
    "pays de la loire": frozenset({"44", "49", "53", "72", "85"}),
    "provence-alpes-cote dazur": frozenset({"04", "05", "06", "13", "83", "84"}),
    "guadeloupe": frozenset({"971"}),
    "martinique": frozenset({"972"}),
    "guyane": frozenset({"973"}),
    "la reunion": frozenset({"974"}),
    "mayotte": frozenset({"976"}),
}


def _normalize_region(location: str) -> str:
    """ASCII-fold, de-apostrophe, and lowercase a region label for lookup.

    France Travail's data isn't consistent about accents (e.g. both
    "Île-de-France" and "Ile-de-France" appear) — normalizing both the
    lookup table's keys and the input the same way makes the match
    accent/case/apostrophe-insensitive.
    """
    ascii_only = unicodedata.normalize("NFKD", location).encode("ascii", "ignore").decode()
    return ascii_only.replace("'", "").replace("’", "").strip().lower()


def parse_department_from_location(location: str | None) -> str | None:
    """Extract a department code from a France Travail location label.

    Args:
        location: Free-text location label as returned by France Travail
            (e.g. "75 - Paris", "2A - Ajaccio", "971 - Pointe-à-Pitre").

    Returns:
        The department code (uppercase for Corsica), or None if the label has
        no recognizable department prefix (e.g. "France", "Luxembourg", an
        empty string, or None).
    """
    if not location:
        return None
    match = DEPARTMENT_PREFIX_RE.match(location)
    if not match:
        return None
    return match.group(1).upper()


def department_from_commune(commune_code: str) -> str:
    """Derive a department code from a 5-character INSEE commune code.

    Args:
        commune_code: INSEE commune code (e.g. "75101", "2A004", "97105").
            Expected to be 5 characters — callers are responsible for that
            invariant, since this parses an already-validated code rather
            than raw user input.

    Returns:
        The department code: "2A"/"2B" for Corsica, the 3-digit DOM/TOM
        prefix ("971"-"978"), or the standard 2-digit department prefix.
        A code shorter than 2 characters is returned unchanged (uppercased)
        rather than raising — it will simply never match a real offer's
        department.
    """
    upper_code = commune_code.upper()
    if upper_code.startswith(("2A", "2B")):
        return upper_code[:2]
    if upper_code.startswith(("97", "98")):
        return upper_code[:3]
    return upper_code[:2]


def parse_region_from_location(location: str | None) -> str | None:
    """Extract a region name from a France Travail location label.

    Used as a coarser fallback than department when an offer's label is a
    bare region name rather than a "DD - Ville" department prefix (e.g.
    "Île-de-France" instead of "75 - Paris").

    Args:
        location: Free-text location label as returned by France Travail.

    Returns:
        The normalized region name (see _normalize_region), or None if the
        label doesn't match any known region.
    """
    if not location:
        return None
    normalized = _normalize_region(location)
    return normalized if normalized in REGION_DEPARTMENTS else None


def regions_intersecting(departments: set[str]) -> set[str]:
    """Region names whose department set overlaps the given departments.

    Args:
        departments: Department codes forming a search zone.

    Returns:
        Normalized region names (see _normalize_region) that contain at
        least one of the given departments. Empty input yields an empty set.
    """
    return {region for region, depts in REGION_DEPARTMENTS.items() if depts & departments}
