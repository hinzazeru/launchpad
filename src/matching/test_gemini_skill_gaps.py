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
