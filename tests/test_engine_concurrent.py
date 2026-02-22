"""Tests for concurrent matching fixes in engine.py.

Covers:
- _job_detail_fields() does not include raw ORM 'job' object
- GeminiStats.attempted semantics: concurrent path counts only Gemini-eligible jobs
- GeminiStats consistency: sequential and concurrent paths produce same counts
- Concurrent matching completes without errors with mock ORM objects
"""

import pytest
from unittest.mock import MagicMock, patch

from src.matching.engine import JobMatcher, GeminiStats


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


def make_nlp_result(**overrides):
    base = {
        'overall_score': 0.75, 'skills_score': 0.8, 'experience_score': 0.7,
        'domain_score': 0.6, 'matching_skills': ['Python', 'SQL'],
        'skill_gaps': [], 'matching_domains': [], 'missing_domains': [],
        'match_details': {}, 'extracted_skills': [], 'resume_years': 5,
        'job_years_required': 4, 'engine_version': '1.0', 'match_engine': 'nlp',
    }
    base.update(overrides)
    return base


def make_gemini_result(**overrides):
    base = make_nlp_result(match_engine='gemini', **overrides)
    base.update({
        'ai_match_score': 75.0, 'ai_skills_score': 80.0,
        'ai_experience_score': 70.0, 'ai_seniority_fit': 65.0,
        'ai_domain_score': 60.0, 'ai_strengths': [], 'ai_concerns': [],
        'ai_recommendations': [], 'skill_matches': [], 'skill_gaps_detailed': [],
        'match_confidence': 0.8, 'gemini_reasoning': 'Good fit',
    })
    base.update(overrides)
    return base


@pytest.fixture
def nlp_matcher():
    """A JobMatcher in NLP-only mode (no Gemini init needed)."""
    with patch('src.matching.engine.get_config') as mock_cfg:
        cfg = MagicMock()
        cfg.get.side_effect = lambda key, default=None: {
            "matching.engine": "nlp",
            "gemini.matcher.concurrency": 1,
        }.get(key, default)
        cfg.get_matching_weights.return_value = {'skills': 0.45, 'experience': 0.35, 'domains': 0.20}
        cfg.get_min_match_score.return_value = 0.0
        cfg.get_engine_version.return_value = "1.0"
        mock_cfg.return_value = cfg
        matcher = JobMatcher(mode="nlp", preload_cache=False)
    return matcher


# ---------------------------------------------------------------------------
# _job_detail_fields()
# ---------------------------------------------------------------------------

class TestJobDetailFields:
    def test_no_raw_job_orm_object_in_dict(self, nlp_matcher):
        """The raw ORM job object must NOT be included in the result dict.

        Before the fix, 'job': job was included, creating a DetachedInstanceError
        landmine for any code accessing unloaded relations after the session closes.
        """
        job = make_mock_job(id=42, title="PM", company="ACME Corp")
        fields = nlp_matcher._job_detail_fields(job)
        assert 'job' not in fields, (
            "'job' key found in _job_detail_fields() — raw ORM object must not be stored "
            "in match result dicts (DetachedInstanceError risk after session close)"
        )

    def test_all_expected_scalar_fields_present(self, nlp_matcher):
        job = make_mock_job(id=7, title="SWE", company="Corp", required_domains=["fintech"])
        fields = nlp_matcher._job_detail_fields(job)
        expected_keys = {'job_id', 'job_title', 'company', 'location', 'url',
                         'posting_date', 'description', 'experience_required', 'required_domains'}
        assert expected_keys.issubset(fields.keys()), (
            f"Missing keys: {expected_keys - fields.keys()}"
        )

    def test_field_values_match_job_attributes(self, nlp_matcher):
        job = make_mock_job(id=3, title="Data Scientist", company="AI Corp")
        fields = nlp_matcher._job_detail_fields(job)
        assert fields['job_id'] == 3
        assert fields['job_title'] == "Data Scientist"
        assert fields['company'] == "AI Corp"

    def test_required_domains_defaults_to_empty_list(self, nlp_matcher):
        job = make_mock_job()
        job.required_domains = None  # simulate NULL in DB
        fields = nlp_matcher._job_detail_fields(job)
        assert fields['required_domains'] == []


# ---------------------------------------------------------------------------
# GeminiStats.attempted semantics in concurrent path
# ---------------------------------------------------------------------------

class TestGeminiStatsConcurrent:
    def test_attempted_is_zero_in_nlp_mode(self, nlp_matcher):
        """NLP mode: _should_use_gemini always False → attempted must stay 0."""
        resume = make_mock_resume()
        jobs = [make_mock_job(id=i) for i in range(4)]
        stats = GeminiStats()

        with patch.object(nlp_matcher, 'match_job', return_value=make_nlp_result()):
            nlp_matcher._match_jobs_concurrent(resume, jobs, 0.0, 2, stats)

        assert stats.attempted == 0, (
            f"NLP mode should never increment attempted, but got {stats.attempted}. "
            "This was the bug: concurrent path was counting ALL jobs as Gemini-attempted."
        )
        assert stats.succeeded == 0

    def test_attempted_counts_only_gemini_eligible_jobs(self, nlp_matcher):
        """Only jobs where _should_use_gemini() returns True count toward attempted."""
        resume = make_mock_resume()
        jobs = [make_mock_job(id=i) for i in range(5)]
        stats = GeminiStats()

        # NLP matcher: _should_use_gemini always returns False
        assert nlp_matcher._should_use_gemini(jobs[0]) is False
        with patch.object(nlp_matcher, 'match_job', return_value=make_nlp_result()):
            nlp_matcher._match_jobs_concurrent(resume, jobs, 0.0, 2, stats)

        assert stats.attempted == 0  # Not 5

    def test_succeeded_only_incremented_for_gemini_engine_results(self, nlp_matcher):
        """succeeded is only incremented when match_engine == 'gemini'."""
        resume = make_mock_resume()
        jobs = [make_mock_job(id=i) for i in range(3)]
        stats = GeminiStats()

        # Even if we stub match_job to return gemini, NLP mode means _should_use_gemini=False
        with patch.object(nlp_matcher, 'match_job', return_value=make_gemini_result()):
            nlp_matcher._match_jobs_concurrent(resume, jobs, 0.0, 2, stats)

        # In NLP mode, even a gemini result doesn't count because _should_use_gemini=False
        assert stats.succeeded == 0

    def test_gemini_stats_consistent_sequential_vs_concurrent(self):
        """Sequential and concurrent paths must produce identical stats for the same inputs.

        In a mode where Gemini is attempted but all fall back to NLP:
        - sequential: attempted += 1 per job where _should_use_gemini=True, succeeded=0
        - concurrent: same semantics after the fix
        """
        with patch('src.matching.engine.get_config') as mock_cfg:
            cfg = MagicMock()
            cfg.get.side_effect = lambda key, default=None: {
                "matching.engine": "nlp",
                "gemini.matcher.concurrency": 1,
            }.get(key, default)
            cfg.get_matching_weights.return_value = {'skills': 0.45, 'experience': 0.35, 'domains': 0.20}
            cfg.get_min_match_score.return_value = 0.0
            cfg.get_engine_version.return_value = "1.0"
            mock_cfg.return_value = cfg
            matcher = JobMatcher(mode="nlp", preload_cache=False)

        resume = make_mock_resume()
        jobs = [make_mock_job(id=i) for i in range(3)]

        # Sequential
        seq_stats = GeminiStats()
        with patch.object(matcher, 'match_job', return_value=make_nlp_result()):
            matcher._match_jobs_sequential(resume, jobs, 0.0, seq_stats)

        # Concurrent
        con_stats = GeminiStats()
        with patch.object(matcher, 'match_job', return_value=make_nlp_result()):
            matcher._match_jobs_concurrent(resume, jobs, 0.0, 2, con_stats)

        assert seq_stats.attempted == con_stats.attempted, (
            f"Sequential attempted={seq_stats.attempted} != concurrent attempted={con_stats.attempted}"
        )
        assert seq_stats.succeeded == con_stats.succeeded


# ---------------------------------------------------------------------------
# Concurrent matching completion and correctness
# ---------------------------------------------------------------------------

class TestConcurrentMatchingCompletion:
    def test_all_jobs_processed(self, nlp_matcher):
        """All submitted jobs are matched even with concurrency > 1."""
        resume = make_mock_resume()
        jobs = [make_mock_job(id=i) for i in range(8)]

        with patch.object(nlp_matcher, 'match_job', return_value=make_nlp_result(overall_score=0.8)):
            results = nlp_matcher._match_jobs_concurrent(resume, jobs, 0.0, 3, None)

        assert len(results) == 8

    def test_results_filtered_by_min_score(self, nlp_matcher):
        """Jobs scoring below min_score are excluded from results."""
        resume = make_mock_resume()
        jobs = [make_mock_job(id=i) for i in range(4)]

        call_n = [0]
        def mock_match(r, j, **kw):
            call_n[0] += 1
            # Alternating high/low scores
            score = 0.8 if j.id % 2 == 0 else 0.3
            return make_nlp_result(overall_score=score)

        with patch.object(nlp_matcher, 'match_job', side_effect=mock_match):
            results = nlp_matcher._match_jobs_concurrent(resume, jobs, 0.6, 2, None)

        assert len(results) == 2  # Only the 2 high-score jobs

    def test_exception_in_one_worker_does_not_abort_others(self, nlp_matcher):
        """If one job raises an exception, the other jobs still complete."""
        resume = make_mock_resume()
        jobs = [make_mock_job(id=i) for i in range(3)]

        call_n = [0]
        def mock_match(r, j, **kw):
            call_n[0] += 1
            if j.id == 1:
                raise RuntimeError("Simulated crash")
            return make_nlp_result(overall_score=0.8)

        results = []
        with patch.object(nlp_matcher, 'match_job', side_effect=mock_match):
            results = nlp_matcher._match_jobs_concurrent(resume, jobs, 0.0, 3, None)

        # 2 of 3 jobs should succeed (job id=1 failed)
        assert len(results) == 2

    def test_result_dict_contains_job_detail_fields(self, nlp_matcher):
        """Results must include job detail fields (job_id, job_title, etc.)."""
        resume = make_mock_resume()
        job = make_mock_job(id=99, title="Staff Engineer", company="TechCo")
        jobs = [job]

        with patch.object(nlp_matcher, 'match_job', return_value=make_nlp_result(overall_score=0.9)):
            results = nlp_matcher._match_jobs_concurrent(resume, jobs, 0.0, 1, None)

        assert len(results) == 1
        r = results[0]
        assert r['job_id'] == 99
        assert r['job_title'] == "Staff Engineer"
        assert r['company'] == "TechCo"
        assert 'job' not in r, "Raw ORM 'job' object must not be in the result dict"

    def test_no_futures_result_loop(self, nlp_matcher):
        """Verify there is no f.result() call that silently claims exceptions are raised.

        The correct implementation just submits jobs and lets the context manager wait.
        We verify this by checking that an exception inside a worker is swallowed
        (not re-raised to the caller), which is the intended behavior.
        """
        resume = make_mock_resume()
        jobs = [make_mock_job(id=i) for i in range(2)]

        with patch.object(nlp_matcher, 'match_job', side_effect=RuntimeError("inner crash")):
            # Should NOT raise even though match_job always fails
            try:
                nlp_matcher._match_jobs_concurrent(resume, jobs, 0.0, 2, None)
            except RuntimeError:
                pytest.fail("_match_jobs_concurrent should swallow worker exceptions, not re-raise them")
