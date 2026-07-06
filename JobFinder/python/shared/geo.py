"""Geographic helpers shared across agents — INSEE commune/department parsing."""

import re

DEPARTMENT_PREFIX_RE = re.compile(r"^\s*(2[AB]|97[1-8]|\d{2})\s*-", re.IGNORECASE)


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
    if upper_code.startswith("97"):
        return upper_code[:3]
    return upper_code[:2]
