"""Lexical tech-keyword extraction — no LLM call, symmetric on CV and offer text.

See docs/prompts/prompt-matching-lexical-skills-b2.md — this is a deliberately approximate,
zero-cost complement to the semantic embedding score, not a replacement: it only ever adds a
bonus to the match score, never a penalty, so a candidate whose CV lists a related-but-different
tool (e.g. AWS vs an Azure-requiring offer) is never worse off than with the embedding score alone.

The reference list (tech_keywords.json) deliberately excludes universal terms (Git, Agile,
Scrum, Kanban, "CI/CD" as a category) and French common-word collisions (Vue without .js,
Go — also the gigabyte unit —, Chef, Tableau): omnipresent or ambiguous terms cannot
discriminate. Only named languages, clouds, platforms and tools are kept.
"""
import json
import re
from pathlib import Path

_KEYWORDS_PATH = Path(__file__).parent / "tech_keywords.json"
TECH_KEYWORDS: list[str] = json.loads(_KEYWORDS_PATH.read_text(encoding="utf-8"))
# Lookarounds plutôt que \b : équivalents pour les termes alphanumériques, mais \b échoue
# sur les termes finissant (ou commençant) par un caractère non-mot — "C++", "C#", ".NET" —
# car il exige alors un caractère de mot adjacent ("C++ " ne matcherait jamais).
_KEYWORD_PATTERNS = [
    (kw, re.compile(rf"(?<!\w){re.escape(kw)}(?!\w)", re.IGNORECASE)) for kw in TECH_KEYWORDS
]


def extract_tech_keywords(text: str) -> list[str]:
    """Return the subset of TECH_KEYWORDS found (case-insensitive, word-boundary) in text.

    Args:
        text: Raw CV or offer text to scan.

    Returns:
        List of matched keywords, in TECH_KEYWORDS order — empty list if none found or text is empty.
    """
    if not text:
        return []
    return [kw for kw, pattern in _KEYWORD_PATTERNS if pattern.search(text)]
