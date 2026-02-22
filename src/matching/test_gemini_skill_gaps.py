"""Unit tests for Gemini matcher skill gap filtering."""

import pytest
from src.matching.gemini_matcher import GeminiMatcher
from src.matching.requirements import SkillGap


class TestSkillGapFiltering:
    """Test that functional role skills aren't incorrectly flagged as gaps."""

    def test_product_management_gap_filtered_for_pm(self):
        """PM roles should NOT have 'Product Management' as a skill gap."""
        matcher = GeminiMatcher()
        
        gap_skill = "Product Management"
        candidate_titles = [
            "Vice President - Product, Governance QualityScore",
            "Senior Manager, Product and Insights"
        ]
        
        result = matcher._is_functional_role_gap(gap_skill, candidate_titles)
        
        assert result is True, "Product Management should be filtered for PM candidates"

    def test_product_manager_gap_filtered_for_pm(self):
        """Test variation: 'Product Manager' should also be filtered."""
        matcher = GeminiMatcher()
        
        gap_skill = "Product Manager"
        candidate_titles = ["Senior Product Manager"]
        
        result = matcher._is_functional_role_gap(gap_skill, candidate_titles)
        
        assert result is True, "Product Manager should be filtered for PM candidates"

    def test_software_engineering_gap_filtered_for_engineer(self):
        """Software engineers shouldn't have 'Software Engineering' as a gap."""
        matcher = GeminiMatcher()
        
        gap_skill = "Software Engineering"
        candidate_titles = [
            "Senior Software Engineer",
            "Software Developer"
        ]
        
        result = matcher._is_functional_role_gap(gap_skill, candidate_titles)
        
        assert result is True, "Software Engineering should be filtered for engineers"

    def test_data_science_gap_filtered_for_data_scientist(self):
        """Data scientists shouldn't have 'Data Science' as a gap."""
        matcher = GeminiMatcher()
        
        gap_skill = "Data Science"
        candidate_titles = ["Data Scientist", "Senior Data Scientist"]
        
        result = matcher._is_functional_role_gap(gap_skill, candidate_titles)
        
        assert result is True, "Data Science should be filtered for data scientists"

    def test_technical_skill_not_filtered(self):
        """Legitimate technical skills should NOT be filtered."""
        matcher = GeminiMatcher()
        
        gap_skill = "Kubernetes"
        candidate_titles = ["Senior Product Manager"]
        
        result = matcher._is_functional_role_gap(gap_skill, candidate_titles)
        
        assert result is False, "Kubernetes should NOT be filtered - it's a legitimate gap"

    def test_domain_skill_not_filtered(self):
        """Domain-specific skills should NOT be filtered."""
        matcher = GeminiMatcher()
        
        gap_skill = "Financial Modeling"
        candidate_titles = ["Product Manager"]
        
        result = matcher._is_functional_role_gap(gap_skill, candidate_titles)
        
        assert result is False, "Financial Modeling should NOT be filtered"

    def test_product_management_not_filtered_for_engineer(self):
        """Engineers SHOULD have 'Product Management' as a potential gap."""
        matcher = GeminiMatcher()
        
        gap_skill = "Product Management"
        candidate_titles = ["Senior Software Engineer", "Tech Lead"]
        
        result = matcher._is_functional_role_gap(gap_skill, candidate_titles)
        
        assert result is False, "Product Management should NOT be filtered for engineers"

    def test_case_insensitive_matching(self):
        """Filtering should work regardless of case."""
        matcher = GeminiMatcher()
        
        gap_skill = "pRoDuCt MaNaGeMeNt"  # Mixed case
        candidate_titles = ["SENIOR PRODUCT MANAGER"]  # Upper case
        
        result = matcher._is_functional_role_gap(gap_skill, candidate_titles)
        
        assert result is True, "Filtering should be case-insensitive"

    def test_empty_candidate_titles(self):
        """Should handle empty candidate_titles gracefully."""
        matcher = GeminiMatcher()
        
        gap_skill = "Product Management"
        candidate_titles = []
        
        result = matcher._is_functional_role_gap(gap_skill, candidate_titles)
        
        assert result is False, "Empty titles should not cause errors"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ---------------------------------------------------------------------------
# Truncation warning in _parse_response() (Issue #8)
# ---------------------------------------------------------------------------

import json
import logging
from unittest.mock import MagicMock


def _make_mock_response(text: str):
    """Build a minimal mock Gemini SDK response object with one text part."""
    part = MagicMock()
    part.text = text
    candidate = MagicMock()
    candidate.content.parts = [part]
    response = MagicMock()
    response.candidates = [candidate]
    return response


# Minimal valid JSON that would result from token-budget truncation:
# the model outputs scores but runs out of tokens before filling arrays.
_TRUNCATED_JSON = json.dumps({
    "overall_score": 75,
    "skills_score": 70,
    "experience_score": 80,
    "seniority_fit": 65,
    "domain_score": 60,
    "skill_matches": [],
    "skill_gaps": [],
    "strengths": [],
    "concerns": [],
    "recommendations": [],
    "confidence": 0.8,
    "reasoning": "Good match overall.",
})

# Full normal response — arrays are populated.
_FULL_JSON = json.dumps({
    "overall_score": 75,
    "skills_score": 70,
    "experience_score": 80,
    "seniority_fit": 65,
    "domain_score": 60,
    "skill_matches": [
        {"job_skill": "Python", "resume_skill": "Python", "confidence": 1.0, "context": "Direct match"}
    ],
    "skill_gaps": [],
    "strengths": ["Strong Python background"],
    "concerns": ["Limited Kubernetes experience"],
    "recommendations": ["Highlight backend projects"],
    "confidence": 0.85,
    "reasoning": "Strong technical match.",
})

# Score is 0 and all arrays empty — legitimate result, NOT truncation.
_ZERO_SCORE_EMPTY_JSON = json.dumps({
    "overall_score": 0,
    "skills_score": 0,
    "experience_score": 0,
    "seniority_fit": 0,
    "domain_score": 0,
    "skill_matches": [],
    "skill_gaps": [],
    "strengths": [],
    "concerns": [],
    "recommendations": [],
    "confidence": 0.1,
    "reasoning": "No match.",
})


class TestTruncationWarning:
    """Tests for the token-budget truncation sanity check in _parse_response()."""

    @pytest.fixture
    def matcher(self):
        """GeminiMatcher with Gemini disabled (no API key required)."""
        return GeminiMatcher()

    def test_warning_emitted_when_score_nonzero_and_all_arrays_empty(
        self, matcher, caplog
    ):
        """A non-zero score with empty skill_matches/strengths/concerns triggers a warning.

        This is the fingerprint of a truncated thinking-model response: the model
        outputs scores but runs out of the token budget before filling insight arrays.
        """
        with caplog.at_level(logging.WARNING, logger="src.matching.gemini_matcher"):
            result = matcher._parse_response(
                _make_mock_response(_TRUNCATED_JSON), "Test Job Title"
            )
        assert "token-budget truncation" in caplog.text, (
            "Expected truncation warning to be logged, but it was not. "
            f"Log output: {caplog.text!r}"
        )
        # The warning is observational — _parse_response must still return a result
        assert result is not None, "Should return a GeminiMatchResult even when truncation is suspected"

    def test_no_warning_when_score_is_zero(self, matcher, caplog):
        """A zero score with empty arrays is a legitimate result — no warning."""
        with caplog.at_level(logging.WARNING, logger="src.matching.gemini_matcher"):
            matcher._parse_response(
                _make_mock_response(_ZERO_SCORE_EMPTY_JSON), "Test Job Title"
            )
        assert "token-budget truncation" not in caplog.text, (
            "Should NOT warn when overall_score == 0 (legit null result)"
        )

    def test_no_warning_when_arrays_populated(self, matcher, caplog):
        """Normal full response with skill_matches and strengths — no truncation warning."""
        with caplog.at_level(logging.WARNING, logger="src.matching.gemini_matcher"):
            matcher._parse_response(
                _make_mock_response(_FULL_JSON), "Test Job Title"
            )
        assert "token-budget truncation" not in caplog.text, (
            "Should NOT warn when response arrays are populated"
        )

    def test_no_warning_when_only_strengths_present(self, matcher, caplog):
        """If at least one insight array is non-empty, the response is not truncated."""
        data = json.loads(_TRUNCATED_JSON)
        data["strengths"] = ["Solid Python background"]  # one array has content
        with caplog.at_level(logging.WARNING, logger="src.matching.gemini_matcher"):
            matcher._parse_response(
                _make_mock_response(json.dumps(data)), "Test Job Title"
            )
        assert "token-budget truncation" not in caplog.text

    def test_result_fields_correct_despite_truncation_warning(self, matcher):
        """The returned GeminiMatchResult should reflect the parsed JSON values."""
        result = matcher._parse_response(
            _make_mock_response(_TRUNCATED_JSON), "Test Job"
        )
        assert result is not None
        assert result.overall_score == pytest.approx(75.0)
        assert result.skill_matches == []
        assert result.strengths == []

    def test_response_length_included_in_warning(self, matcher, caplog):
        """The warning message should include the response length for debugging."""
        with caplog.at_level(logging.WARNING, logger="src.matching.gemini_matcher"):
            matcher._parse_response(
                _make_mock_response(_TRUNCATED_JSON), "Engineer Role"
            )
        # The warning should mention response length so devs can see how much was returned
        assert "chars" in caplog.text or "length" in caplog.text, (
            f"Warning should mention response length. Log: {caplog.text!r}"
        )
