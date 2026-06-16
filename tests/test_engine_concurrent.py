"""Tests for concurrent matching in engine.py (Gemini-only).

Covers:
- _job_detail_fields() does not include raw ORM 'job' object
- GeminiStats counting in the concurrent path (attempted/succeeded per job)
- Concurrent matching completes and filters by min_score
- A Gemini failure in any worker aborts the batch (GeminiUnavailableError)
"""

import pytest
from unittest.mock import MagicMock, patch

from src.matching.engine import JobMatcher, GeminiStats, GeminiUnavailableError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock_resume(skills=None, domains=None, experience_years=5.0, job_titles=None):
    r = MagicMock()
    r.skills = skills if skills is not None else ["Python", "SQL"]
    r.domains = domains if domains is not None else ["fintech"]
    r.experience_years = experience_years
    r.job_titles = job_titles if job_titles is not None else ["Senior Engineer"]
    return r


def make_mock_job(id=1, title="Eng", company="Acme", required_domains=None,
                  structured_requirements=None):
    j = MagicMock()
    j.id = id
    j.title = title
    j.company = company
    j.location = "Toronto"
    j.url = "http://example.com"
    j.description = "A job description"
    j.experience_required = 5
    j.posting_date = None
    j.required_domains = required_domains if required_domains is not None else []
    j.required_skills = []
    j.structured_requirements = structured_requirements
    return j


def make_gemini_result(**overrides):
    base = {
        'overall_score': 0.75, 'skills_score': 0.8, 'experience_score': 0.7,
        'domain_score': 0.6, 'matching_skills': ['Python', 'SQL'],
        'skill_gaps': [], 'matching_domains': [], 'missing_domains': [],
        'match_details': {}, 'extracted_skills': [], 'resume_years': 5,
        'job_years_required': 4, 'engine_version': '1.0', 'match_engine': 'gemini',
        'ai_match_score': 75.0, 'ai_skills_score': 80.0, 'ai_experience_score': 70.0,
        'ai_seniority_fit': 65.0, 'ai_domain_score': 60.0, 'ai_strengths': [],
        'ai_concerns': [], 'ai_recommendations': [], 'skill_matches': [],
        'skill_gaps_detailed': [], 'match_confidence': 0.8, 'gemini_reasoning': 'Good fit',
    }
    base.update(overrides)
    return base


@pytest.fixture
def matcher():
    """A Gemini-only JobMatcher with a mocked, available GeminiMatcher."""
    with patch('src.matching.engine.get_config') as mock_cfg, \
         patch('src.matching.gemini_matcher.GeminiMatcher') as MockGM:
        cfg = MagicMock()
        cfg.get.side_effect = lambda key, default=None: {
            "gemini.matcher.concurrency": 1,
        }.get(key, default)
        cfg.get_min_match_score.return_value = 0.0
        cfg.get_engine_version.return_value = "1.0"
        mock_cfg.return_value = cfg

        gm = MagicMock()
        gm.is_available.return_value = True
        MockGM.return_value = gm

        m = JobMatcher()
    return m


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def test_construction_raises_when_gemini_unavailable():
    """JobMatcher must refuse to construct if Gemini is unavailable (no NLP fallback)."""
    with patch('src.matching.engine.get_config') as mock_cfg, \
         patch('src.matching.gemini_matcher.GeminiMatcher') as MockGM:
        cfg = MagicMock()
        cfg.get.side_effect = lambda key, default=None: default
        cfg.get_engine_version.return_value = "1.0"
        mock_cfg.return_value = cfg

        gm = MagicMock()
        gm.is_available.return_value = False
        MockGM.return_value = gm

        with pytest.raises(GeminiUnavailableError):
            JobMatcher()


# ---------------------------------------------------------------------------
# _job_detail_fields()
# ---------------------------------------------------------------------------

class TestJobDetailFields:
    def test_no_raw_job_orm_object_in_dict(self, matcher):
        job = make_mock_job(id=42, title="PM", company="ACME Corp")
        fields = matcher._job_detail_fields(job)
        assert 'job' not in fields

    def test_all_expected_scalar_fields_present(self, matcher):
        job = make_mock_job(id=7, title="SWE", company="Corp", required_domains=["fintech"])
        fields = matcher._job_detail_fields(job)
        expected_keys = {'job_id', 'job_title', 'company', 'location', 'url',
                         'posting_date', 'description', 'experience_required', 'required_domains'}
        assert expected_keys.issubset(fields.keys())

    def test_field_values_match_job_attributes(self, matcher):
        job = make_mock_job(id=3, title="Data Scientist", company="AI Corp")
        fields = matcher._job_detail_fields(job)
        assert fields['job_id'] == 3
        assert fields['job_title'] == "Data Scientist"
        assert fields['company'] == "AI Corp"

    def test_required_domains_defaults_to_empty_list(self, matcher):
        job = make_mock_job()
        job.required_domains = None  # simulate NULL in DB
        fields = matcher._job_detail_fields(job)
        assert fields['required_domains'] == []


# ---------------------------------------------------------------------------
# GeminiStats in the concurrent path
# ---------------------------------------------------------------------------

class TestGeminiStatsConcurrent:
    def test_attempted_and_succeeded_count_every_job(self, matcher):
        """Every job is a Gemini attempt; successes increment succeeded."""
        resume = make_mock_resume()
        jobs = [make_mock_job(id=i) for i in range(4)]
        stats = GeminiStats()

        with patch.object(matcher, 'match_job', return_value=make_gemini_result()):
            matcher._match_jobs_concurrent(resume, jobs, 0.0, 2, stats)

        assert stats.attempted == 4
        assert stats.succeeded == 4
        assert stats.failed == 0


# ---------------------------------------------------------------------------
# Concurrent matching completion and correctness
# ---------------------------------------------------------------------------

class TestConcurrentMatchingCompletion:
    def test_all_jobs_processed(self, matcher):
        resume = make_mock_resume()
        jobs = [make_mock_job(id=i) for i in range(8)]

        with patch.object(matcher, 'match_job', return_value=make_gemini_result(overall_score=0.8)):
            results = matcher._match_jobs_concurrent(resume, jobs, 0.0, 3, None)

        assert len(results) == 8

    def test_results_filtered_by_min_score(self, matcher):
        resume = make_mock_resume()
        jobs = [make_mock_job(id=i) for i in range(4)]

        def mock_match(r, j, **kw):
            score = 0.8 if j.id % 2 == 0 else 0.3
            return make_gemini_result(overall_score=score)

        with patch.object(matcher, 'match_job', side_effect=mock_match):
            results = matcher._match_jobs_concurrent(resume, jobs, 0.6, 2, None)

        assert len(results) == 2  # Only the 2 high-score jobs

    def test_failure_in_any_worker_aborts_batch(self, matcher):
        """A Gemini failure must abort the whole batch (no NLP fallback)."""
        resume = make_mock_resume()
        jobs = [make_mock_job(id=i) for i in range(3)]

        def mock_match(r, j, **kw):
            if j.id == 1:
                raise GeminiUnavailableError("Simulated Gemini failure")
            return make_gemini_result(overall_score=0.8)

        with patch.object(matcher, 'match_job', side_effect=mock_match):
            with pytest.raises(GeminiUnavailableError):
                matcher._match_jobs_concurrent(resume, jobs, 0.0, 3, None)

    def test_result_dict_contains_job_detail_fields(self, matcher):
        resume = make_mock_resume()
        job = make_mock_job(id=99, title="Staff Engineer", company="TechCo")

        with patch.object(matcher, 'match_job', return_value=make_gemini_result(overall_score=0.9)):
            results = matcher._match_jobs_concurrent(resume, [job], 0.0, 1, None)

        assert len(results) == 1
        r = results[0]
        assert r['job_id'] == 99
        assert r['job_title'] == "Staff Engineer"
        assert r['company'] == "TechCo"
        assert 'job' not in r
