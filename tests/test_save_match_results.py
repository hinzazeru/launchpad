"""Tests for None-sanitization at write time in save_match_results().

Covers:
- matching_skills with None entries are stripped before INSERT
- missing_domains with None entries are stripped before INSERT
- ai_strengths / ai_concerns / ai_recommendations with None stripped (Gemini path)
- NLP path (no ai_ fields) saves correctly without error
- Valid non-None lists pass through unchanged
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base
from src.database import crud
from src.matching.engine import JobMatcher


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def resume_and_job(db_session):
    resume = crud.create_resume(db_session, skills=["Python"], experience_years=5.0)
    job = crud.create_job_posting(
        db_session,
        title="Software Engineer",
        company="Acme Corp",
        posting_date=datetime.utcnow(),
    )
    return resume, job


@pytest.fixture
def nlp_matcher():
    with patch('src.matching.engine.get_config') as mock_cfg:
        cfg = MagicMock()
        cfg.get.side_effect = lambda key, default=None: {
            "matching.engine": "nlp",
        }.get(key, default)
        cfg.get_matching_weights.return_value = {'skills': 0.45, 'experience': 0.35, 'domains': 0.20}
        cfg.get_min_match_score.return_value = 0.0
        cfg.get_engine_version.return_value = "1.0"
        mock_cfg.return_value = cfg
        matcher = JobMatcher(mode="nlp", preload_cache=False)
    return matcher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_nlp_match(job_id, **overrides):
    base = {
        'overall_score': 0.75,
        'match_engine': 'nlp',
        'job_id': job_id,
        'resume_years': 5,
        'job_years_required': 4,
        'matching_skills': ['Python', 'SQL'],
        'missing_domains': [],
        'engine_version': '1.0',
        'domain_score': 0.6,
    }
    base.update(overrides)
    return base


def make_gemini_match(job_id, **overrides):
    base = {
        'overall_score': 0.87,
        'match_engine': 'gemini',
        'job_id': job_id,
        'resume_years': 5,
        'job_years_required': 4,
        'matching_skills': ['Python', 'SQL'],
        'missing_domains': [],
        'gemini_reasoning': 'Strong fit',
        'ai_match_score': 87.0,
        'ai_skills_score': 85.0,
        'ai_experience_score': 90.0,
        'ai_seniority_fit': 80.0,
        'ai_domain_score': 75.0,
        'ai_strengths': ['Strong Python'],
        'ai_concerns': ['Missing Kubernetes'],
        'ai_recommendations': ['Highlight backend work'],
        'skill_matches': [],
        'skill_gaps_detailed': [],
        'match_confidence': 0.9,
        'engine_version': '1.0',
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# matching_skills sanitization
# ---------------------------------------------------------------------------

class TestMatchingSkillsSanitization:
    def test_nones_in_middle_stripped(self, nlp_matcher, db_session, resume_and_job):
        resume, job = resume_and_job
        match = make_nlp_match(job.id, matching_skills=["Python", None, "SQL", None])

        saved = nlp_matcher.save_match_results(db_session, resume.id, [match])

        assert None not in saved[0].matching_skills
        assert saved[0].matching_skills == ["Python", "SQL"]

    def test_all_none_saves_as_empty_list(self, nlp_matcher, db_session, resume_and_job):
        resume, job = resume_and_job
        match = make_nlp_match(job.id, matching_skills=[None, None])

        saved = nlp_matcher.save_match_results(db_session, resume.id, [match])

        assert saved[0].matching_skills == []

    def test_none_input_saves_as_empty_list(self, nlp_matcher, db_session, resume_and_job):
        resume, job = resume_and_job
        match = make_nlp_match(job.id, matching_skills=None)

        saved = nlp_matcher.save_match_results(db_session, resume.id, [match])

        assert saved[0].matching_skills == []

    def test_valid_list_passes_through_unchanged(self, nlp_matcher, db_session, resume_and_job):
        resume, job = resume_and_job
        match = make_nlp_match(job.id, matching_skills=["Python", "SQL", "AWS"])

        saved = nlp_matcher.save_match_results(db_session, resume.id, [match])

        assert saved[0].matching_skills == ["Python", "SQL", "AWS"]


# ---------------------------------------------------------------------------
# missing_domains sanitization
# ---------------------------------------------------------------------------

class TestMissingDomainsSanitization:
    def test_nones_stripped_from_missing_domains(self, nlp_matcher, db_session, resume_and_job):
        resume, job = resume_and_job
        match = make_nlp_match(job.id, missing_domains=["fintech", None, "banking"])

        saved = nlp_matcher.save_match_results(db_session, resume.id, [match])

        assert None not in saved[0].missing_domains
        assert saved[0].missing_domains == ["fintech", "banking"]

    def test_all_none_missing_domains_saves_as_empty(self, nlp_matcher, db_session, resume_and_job):
        resume, job = resume_and_job
        match = make_nlp_match(job.id, missing_domains=[None])

        saved = nlp_matcher.save_match_results(db_session, resume.id, [match])

        assert saved[0].missing_domains == []


# ---------------------------------------------------------------------------
# Gemini AI field sanitization
# ---------------------------------------------------------------------------

class TestGeminiFieldSanitization:
    def test_ai_strengths_nones_stripped(self, nlp_matcher, db_session, resume_and_job):
        resume, job = resume_and_job
        match = make_gemini_match(
            job.id,
            ai_strengths=["Strong Python", None, "5 years exp"],
        )

        saved = nlp_matcher.save_match_results(db_session, resume.id, [match])

        assert None not in saved[0].ai_strengths
        assert len(saved[0].ai_strengths) == 2

    def test_ai_concerns_nones_stripped(self, nlp_matcher, db_session, resume_and_job):
        resume, job = resume_and_job
        match = make_gemini_match(job.id, ai_concerns=[None, "Missing Kubernetes"])

        saved = nlp_matcher.save_match_results(db_session, resume.id, [match])

        assert saved[0].ai_concerns == ["Missing Kubernetes"]

    def test_ai_recommendations_nones_stripped(self, nlp_matcher, db_session, resume_and_job):
        resume, job = resume_and_job
        match = make_gemini_match(
            job.id,
            ai_recommendations=["Apply now", None, "Mention open-source"],
        )

        saved = nlp_matcher.save_match_results(db_session, resume.id, [match])

        assert None not in saved[0].ai_recommendations
        assert len(saved[0].ai_recommendations) == 2

    def test_all_ai_lists_none_input_saves_as_none(self, nlp_matcher, db_session, resume_and_job):
        """When Gemini returns None for all list fields, DB gets None (not an error)."""
        resume, job = resume_and_job
        match = make_gemini_match(
            job.id,
            ai_strengths=None,
            ai_concerns=None,
            ai_recommendations=None,
        )

        saved = nlp_matcher.save_match_results(db_session, resume.id, [match])

        # None input → cleaned to [] by _clean_list
        assert saved[0].ai_strengths == []
        assert saved[0].ai_concerns == []
        assert saved[0].ai_recommendations == []

    def test_gemini_match_with_clean_data_saves_correctly(self, nlp_matcher, db_session, resume_and_job):
        """Valid Gemini data with no Nones passes through without modification."""
        resume, job = resume_and_job
        match = make_gemini_match(
            job.id,
            ai_strengths=["Python", "SQL"],
            ai_concerns=["Missing K8s"],
            ai_recommendations=["Highlight backend"],
        )

        saved = nlp_matcher.save_match_results(db_session, resume.id, [match])

        assert saved[0].ai_strengths == ["Python", "SQL"]
        assert saved[0].ai_concerns == ["Missing K8s"]
        assert saved[0].ai_recommendations == ["Highlight backend"]


# ---------------------------------------------------------------------------
# NLP path (no AI fields)
# ---------------------------------------------------------------------------

class TestNlpMatchSave:
    def test_nlp_match_saves_without_ai_fields(self, nlp_matcher, db_session, resume_and_job):
        """NLP matches don't set ai_* fields; save_match_results must not error."""
        resume, job = resume_and_job
        match = make_nlp_match(job.id)

        saved = nlp_matcher.save_match_results(db_session, resume.id, [match])

        assert len(saved) == 1
        assert saved[0].match_engine == 'nlp'
        # AI fields should be None (not set for NLP matches)
        assert saved[0].ai_strengths is None
        assert saved[0].ai_concerns is None

    def test_saves_correct_score(self, nlp_matcher, db_session, resume_and_job):
        resume, job = resume_and_job
        match = make_nlp_match(job.id, overall_score=0.72)

        saved = nlp_matcher.save_match_results(db_session, resume.id, [match])

        assert saved[0].match_score == pytest.approx(72.0)

    def test_saves_multiple_results(self, nlp_matcher, db_session, resume_and_job):
        resume, job = resume_and_job
        matches = [
            make_nlp_match(job.id, overall_score=0.8, matching_skills=["Python"]),
            make_nlp_match(job.id, overall_score=0.6, matching_skills=["SQL"]),
        ]

        saved = nlp_matcher.save_match_results(db_session, resume.id, matches)

        assert len(saved) == 2
