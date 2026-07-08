"""Tests for shared/tech_keywords.py.

Covers: extract_tech_keywords (match, case-insensitivity, word boundaries,
non-word-character keywords like C++/C#, empty inputs).
"""
from shared.tech_keywords import TECH_KEYWORDS, extract_tech_keywords


class TestExtractTechKeywords:
    def test_finds_keywords_present_in_text(self):
        text = "Ingénieur Cloud : déploiement Azure avec Terraform et Kubernetes."
        result = extract_tech_keywords(text)
        assert "Azure" in result
        assert "Terraform" in result
        assert "Kubernetes" in result

    def test_is_case_insensitive_and_returns_canonical_casing(self):
        result = extract_tech_keywords("maîtrise de PYTHON et de docker")
        assert "Python" in result
        assert "Docker" in result

    def test_java_does_not_match_inside_javascript(self):
        result = extract_tech_keywords("Développeur JavaScript confirmé")
        assert "JavaScript" in result
        assert "Java" not in result

    def test_matches_keywords_ending_with_non_word_characters(self):
        # \b échouerait sur ces termes (pas de caractère de mot après "+" ou "#") —
        # c'est la raison des lookarounds dans _KEYWORD_PATTERNS.
        result = extract_tech_keywords("Développement C++ et C# sur .NET")
        assert "C++" in result
        assert "C#" in result
        assert ".NET" in result

    def test_word_boundary_blocks_partial_matches(self):
        # "Javanais" contient "Java" mais collé à d'autres lettres — pas un match.
        assert "Java" not in extract_tech_keywords("locuteur Javanais")

    def test_empty_text_returns_empty_list(self):
        assert extract_tech_keywords("") == []

    def test_text_without_keywords_returns_empty_list(self):
        assert extract_tech_keywords("Boulanger recherché pour fournil traditionnel") == []

    def test_results_follow_reference_list_order(self):
        text = "Terraform avant Azure dans ce texte"
        result = extract_tech_keywords(text)
        assert result == [kw for kw in TECH_KEYWORDS if kw in ("Azure", "Terraform")]
