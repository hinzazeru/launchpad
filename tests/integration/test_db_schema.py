"""Integration tests for database schema integrity.

Verifies that models create correct tables, constraints work, and
nullable AI fields accept NULL values.
"""

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import IntegrityError

from src.database.models import Base, Resume, JobPosting, MatchResult, SearchJob
from datetime import datetime, timezone


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def fresh_engine():
    """Engine WITHOUT tables created — tests verify create_all."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    yield eng
    eng.dispose()


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestAllTablesCreated:

    def test_create_all_creates_expected_tables(self, fresh_engine):
        """Base.metadata.create_all should create all model tables."""
        Base.metadata.create_all(fresh_engine)

        inspector = inspect(fresh_engine)
        tables = set(inspector.get_table_names())

        expected = {
            "resumes",
            "job_postings",
            "match_results",
            "application_tracking",
            "liked_bullets",
            "scheduled_searches",
            "search_performance",
            "api_call_metrics",
            "search_jobs",
        }
        assert expected.issubset(tables), f"Missing tables: {expected - tables}"


class TestJobPostingUniqueConstraint:

    def test_duplicate_title_company_raises_integrity_error(self, engine):
        """Inserting two jobs with same (title, company) should raise."""
        Session = sessionmaker(bind=engine)
        session = Session()

        job1 = JobPosting(
            title="Engineer",
            company="Acme",
            posting_date=datetime.now(timezone.utc),
        )
        session.add(job1)
        session.commit()

        job2 = JobPosting(
            title="Engineer",
            company="Acme",
            posting_date=datetime.now(timezone.utc),
        )
        session.add(job2)

        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()
        session.close()

    def test_different_title_same_company_allowed(self, engine):
        """Different titles at the same company should be fine."""
        Session = sessionmaker(bind=engine)
        session = Session()

        job1 = JobPosting(
            title="Frontend Engineer",
            company="Acme",
            posting_date=datetime.now(timezone.utc),
        )
        job2 = JobPosting(
            title="Backend Engineer",
            company="Acme",
            posting_date=datetime.now(timezone.utc),
        )
        session.add_all([job1, job2])
        session.commit()  # Should not raise

        assert session.query(JobPosting).count() == 2
        session.close()


class TestMatchResultAIFieldsNullable:

    def test_all_ai_columns_accept_null(self, engine):
        """All AI-specific columns on MatchResult should accept NULL."""
        Session = sessionmaker(bind=engine)
        session = Session()

        # Create prerequisite records
        resume = Resume(skills=["Python"], experience_years=5.0)
        session.add(resume)
        session.flush()

        job = JobPosting(
            title="Test Job",
            company="Test Co",
            posting_date=datetime.now(timezone.utc),
        )
        session.add(job)
        session.flush()

        # Create a match with ALL AI fields explicitly set to None
        match = MatchResult(
            job_id=job.id,
            resume_id=resume.id,
            match_score=50.0,
            match_engine="nlp",
            # All AI fields null
            ai_match_score=None,
            skills_score=None,
            experience_score=None,
            seniority_fit=None,
            domain_score=None,
            ai_strengths=None,
            ai_concerns=None,
            ai_recommendations=None,
            skill_matches=None,
            skill_gaps_detailed=None,
            match_confidence=None,
            gemini_score=None,
            gemini_reasoning=None,
            gemini_strengths=None,
            gemini_gaps=None,
            bullet_suggestions=None,
        )
        session.add(match)
        session.commit()  # Should not raise

        # Verify all nulls persisted
        saved = session.query(MatchResult).first()
        assert saved.ai_match_score is None
        assert saved.skills_score is None
        assert saved.experience_score is None
        assert saved.seniority_fit is None
        assert saved.domain_score is None
        assert saved.ai_strengths is None
        assert saved.ai_concerns is None
        assert saved.ai_recommendations is None
        assert saved.skill_matches is None
        assert saved.skill_gaps_detailed is None
        assert saved.match_confidence is None
        assert saved.gemini_score is None
        assert saved.gemini_reasoning is None
        assert saved.gemini_strengths is None
        assert saved.gemini_gaps is None
        assert saved.bullet_suggestions is None

        session.close()


class TestSearchJobSchema:

    def test_search_job_unique_search_id(self, engine):
        """search_id should be unique."""
        Session = sessionmaker(bind=engine)
        session = Session()

        sj1 = SearchJob(
            search_id="same-id",
            keyword="test",
            resume_filename="test.md",
            trigger_source="manual",
        )
        session.add(sj1)
        session.commit()

        sj2 = SearchJob(
            search_id="same-id",
            keyword="test2",
            resume_filename="test2.md",
            trigger_source="manual",
        )
        session.add(sj2)

        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()
        session.close()

    def test_search_job_defaults(self, engine):
        """SearchJob should have sensible defaults for status fields."""
        Session = sessionmaker(bind=engine)
        session = Session()

        sj = SearchJob(
            search_id="test-defaults",
            keyword="Engineer",
            resume_filename="resume.md",
            trigger_source="manual",
        )
        session.add(sj)
        session.commit()

        saved = session.query(SearchJob).first()
        assert saved.status == "pending"
        assert saved.stage == "initializing"
        assert saved.progress == 0
        assert saved.cancellation_requested is False

        session.close()
