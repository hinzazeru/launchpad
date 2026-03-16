"""Shared fixtures for integration tests.

Uses isolated in-memory SQLite with StaticPool (same pattern as test_admin_rematch.py).
Mounts individual routers on fresh FastAPI apps to avoid triggering
backend/tests/conftest.py module-level mocks.
"""

import itertools
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database.models import Base, Resume, JobPosting, MatchResult, SearchJob
from backend.routers import search as search_module
from backend.limiter import limiter


# ── Database fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def engine():
    """Fresh in-memory SQLite DB per test."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture
def Session(engine):
    return sessionmaker(bind=engine)


@pytest.fixture
def db(Session):
    session = Session()
    yield session
    session.close()


# ── Resume fixture ────────────────────────────────────────────────────────────

@pytest.fixture
def fake_resume_dir(tmp_path):
    """Create a temp directory with a minimal parseable resume."""
    resume_dir = tmp_path / "resumes"
    resume_dir.mkdir()
    resume_file = resume_dir / "test_resume.md"
    resume_file.write_text(
        "# John Doe\n\n"
        "## Summary\n"
        "Senior Software Engineer with 8 years of experience.\n\n"
        "## Skills\n"
        "### Technical\n"
        "- Python\n"
        "- SQL\n"
        "- AWS\n"
        "- Docker\n"
        "- FastAPI\n\n"
        "### Domains\n"
        "- financial_services\n"
        "- b2b_saas\n\n"
        "## Experience\n"
        "### Senior Engineer | Acme Corp | 2020 - 2024\n"
        "- Built microservices in Python\n"
        "- Managed AWS infrastructure\n\n"
        "### Engineer | Beta Inc | 2016 - 2020\n"
        "- Developed APIs with Flask\n"
        "- Wrote SQL queries for analytics\n"
    )
    return resume_dir


# ── Sample data ───────────────────────────────────────────────────────────────

_job_counter = itertools.count(1)


def make_job(session, title="Senior Engineer", company=None, description=None,
             location="Toronto, Canada", posting_date=None, url=None,
             required_skills=None, required_domains=None,
             structured_requirements=None):
    """Create a JobPosting in the test DB."""
    n = next(_job_counter)
    job = JobPosting(
        title=title if title != "Senior Engineer" else f"Senior Engineer {n}",
        company=company or f"TestCorp {n}",
        description=description or ("A" * 300),  # >200 chars to pass filter
        location=location,
        posting_date=posting_date or datetime.now(timezone.utc),
        url=url or f"https://linkedin.com/jobs/{n}",
        required_skills=required_skills or ["Python", "SQL"],
        required_domains=required_domains,
        structured_requirements=structured_requirements,
    )
    session.add(job)
    session.flush()
    return job


def make_resume(session, skills=None, experience_years=8.0, domains=None):
    """Create a Resume in the test DB."""
    resume = Resume(
        skills=skills or ["Python", "SQL", "AWS", "Docker", "FastAPI"],
        experience_years=experience_years,
        domains=domains or ["financial_services", "b2b_saas"],
    )
    session.add(resume)
    session.flush()
    return resume


def make_match(session, job_id, resume_id, match_score=75.0, engine="gemini",
               ai_match_score=None, matching_skills=None, ai_strengths=None,
               ai_concerns=None, skill_gaps_detailed=None, skill_matches=None,
               user_status=None):
    """Create a MatchResult in the test DB."""
    match = MatchResult(
        job_id=job_id,
        resume_id=resume_id,
        match_score=match_score,
        match_engine=engine,
        matching_skills=matching_skills or ["Python", "SQL"],
        ai_match_score=ai_match_score or match_score,
        ai_strengths=ai_strengths or ["Strong backend skills"],
        ai_concerns=ai_concerns or ["No React experience"],
        skill_matches=skill_matches or [
            {"job_skill": "Python", "resume_skill": "Python", "confidence": 0.95},
        ],
        skill_gaps_detailed=skill_gaps_detailed or [
            {"skill": "React", "importance": "nice_to_have", "transferable_from": None},
        ],
        user_status=user_status,
    )
    session.add(match)
    session.flush()
    return match


# ── Shared search client builder ──────────────────────────────────────────────

def make_search_client(Session, fake_resume_dir, mock_provider, mock_matcher,
                       mock_config, reranker=None):
    """Build a TestClient with search router, rate limiter disabled, and all
    external services patched.  Returns (client, active_patches).

    Call ``stop_patches(ctx)`` in a finally block to clean up.
    """
    app = FastAPI()
    app.state.limiter = limiter
    limiter.enabled = False
    app.include_router(search_module.router, prefix="/api/search")

    patches = {
        "backend.routers.search.SessionLocal": Session,
        "backend.routers.search.RESUME_LIBRARY_DIR": fake_resume_dir,
        "backend.routers.search.get_job_provider": MagicMock(return_value=mock_provider),
        "backend.routers.search.get_job_matcher": MagicMock(return_value=mock_matcher),
        "backend.routers.search.get_gemini_reranker": MagicMock(return_value=reranker),
        "backend.routers.search.get_config": MagicMock(return_value=mock_config),
    }
    ctx = [patch(target, val) for target, val in patches.items()]
    for c in ctx:
        c.start()

    return TestClient(app), ctx


def stop_patches(ctx):
    for c in ctx:
        c.stop()


def start_search(client, keyword="Senior Engineer", resume="test_resume.md",
                 location="Canada", max_results=25, export_to_sheets=False):
    """POST to start a search job and return the response."""
    return client.post("/api/search/jobs/start", json={
        "keyword": keyword,
        "location": location,
        "max_results": max_results,
        "resume_filename": resume,
        "export_to_sheets": export_to_sheets,
    })


# ── Sample data fixtures (consumed by mock_job_provider / mock_job_matcher) ──

@pytest.fixture
def sample_raw_jobs():
    """Raw job dicts as returned by a provider's search_jobs_async."""
    return [
        {
            "title": "Senior Python Engineer",
            "companyName": "AlphaCo",
            "description": "We need a senior Python engineer. " * 30,
            "location": "Toronto, Canada",
            "url": "https://linkedin.com/jobs/100",
            "postedAt": datetime.now(timezone.utc).isoformat(),
        },
        {
            "title": "Backend Developer",
            "companyName": "BetaCo",
            "description": "Backend developer with SQL experience. " * 30,
            "location": "Vancouver, Canada",
            "url": "https://linkedin.com/jobs/101",
            "postedAt": datetime.now(timezone.utc).isoformat(),
        },
        {
            "title": "Data Engineer",
            "companyName": "GammaCo",
            "description": "Data engineer needed for our team. " * 30,
            "location": "Remote, United States",
            "url": "https://linkedin.com/jobs/102",
            "postedAt": datetime.now(timezone.utc).isoformat(),
        },
    ]


@pytest.fixture
def sample_match_results():
    """Match result dicts as returned by matcher.match_jobs."""
    return [
        {
            "job_id": 1,
            "job_title": "Senior Python Engineer",
            "company": "AlphaCo",
            "location": "Toronto, Canada",
            "url": "https://linkedin.com/jobs/100",
            "overall_score": 0.88,
            "match_engine": "gemini",
            "matching_skills": ["Python", "SQL", "AWS"],
            "ai_match_score": 88.0,
            "ai_skills_score": 90.0,
            "ai_experience_score": 85.0,
            "ai_seniority_fit": 80.0,
            "ai_domain_score": 75.0,
            "ai_strengths": ["Strong Python background"],
            "ai_concerns": ["No React"],
            "ai_recommendations": ["Highlight cloud experience"],
            "skill_matches": [
                {"job_skill": "Python", "resume_skill": "Python", "confidence": 0.95},
            ],
            "skill_gaps_detailed": [
                {"skill": "React", "importance": "nice_to_have", "transferable_from": None},
            ],
            "match_confidence": 0.9,
        },
        {
            "job_id": 2,
            "job_title": "Backend Developer",
            "company": "BetaCo",
            "location": "Vancouver, Canada",
            "url": "https://linkedin.com/jobs/101",
            "overall_score": 0.72,
            "match_engine": "gemini",
            "matching_skills": ["Python", "SQL"],
            "ai_match_score": 72.0,
            "ai_skills_score": 70.0,
            "ai_experience_score": 75.0,
            "ai_seniority_fit": 70.0,
            "ai_domain_score": 60.0,
            "ai_strengths": ["Relevant experience"],
            "ai_concerns": ["Missing Kubernetes"],
            "ai_recommendations": ["Focus on backend strengths"],
            "skill_matches": [
                {"job_skill": "Python", "resume_skill": "Python", "confidence": 0.9},
            ],
            "skill_gaps_detailed": [
                {"skill": "Kubernetes", "importance": "must_have", "transferable_from": "Docker"},
            ],
            "match_confidence": 0.8,
        },
    ]


# ── Mock provider fixture ────────────────────────────────────────────────────

@pytest.fixture
def mock_job_provider(sample_raw_jobs):
    """A mock job provider that returns fake jobs."""
    provider = MagicMock()
    provider.search_jobs_async = AsyncMock(return_value=sample_raw_jobs)
    provider.normalize_job = MagicMock(side_effect=lambda job: {
        "title": job.get("title", ""),
        "company": job.get("companyName", ""),
        "description": job.get("description", ""),
        "location": job.get("location", ""),
        "url": job.get("url", ""),
        "posting_date": job.get("postedAt", ""),
    })
    provider.import_jobs = MagicMock(return_value=len(sample_raw_jobs))
    return provider


# ── Mock matcher fixture ──────────────────────────────────────────────────────

class FakeGeminiStats:
    """Mimics the GeminiStats namedtuple from engine.py."""
    def __init__(self):
        self.attempted = 3
        self.succeeded = 3
        self.failed = 0
        self.failure_reasons = []


@pytest.fixture
def mock_job_matcher(sample_match_results):
    """A mock matcher that returns deterministic results."""
    matcher = MagicMock()
    matcher.match_jobs.return_value = (sample_match_results, FakeGeminiStats())
    matcher.save_match_results = MagicMock()
    return matcher


# ── Mock config fixture ───────────────────────────────────────────────────────

@pytest.fixture
def mock_config():
    """A mock config that returns sensible defaults."""
    config = MagicMock()
    config.get = MagicMock(side_effect=lambda key, default=None: {
        "matching.engine": "auto",
        "matching.max_job_age_days": 7,
        "matching.gemini_rerank.blend_weights.ai": 0.75,
        "matching.gemini_rerank.blend_weights.nlp": 0.25,
        "gemini.enabled": False,
        "gemini.api_key": None,
        "search.default_location": "United States",
        "search.default_max_results": 50,
        "search.default_job_type": None,
        "search.default_experience_level": None,
        "search.default_work_arrangement": None,
        "search.default_posted_when": "Past 24 hours",
        "sheets.spreadsheet_id": None,
    }.get(key, default))
    return config
