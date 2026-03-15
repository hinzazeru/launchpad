"""Tests for admin rematch endpoints and _do_rematch background worker.

Covers:
- rematch_job (single job): success (Gemini), skip (NLP), 404 cases, auth
- _do_rematch (bulk worker): success, skip, missing records, exception-then-continue
- rematch_stale: queues stale jobs, none_found when empty
- rematch_by_gap: queues jobs by skill gap, none_found when no match
"""
import itertools
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database.models import Base, JobPosting, MatchResult, Resume
from backend.routers import admin as admin_module
from backend.routers.admin import _do_rematch

# ── Constants ─────────────────────────────────────────────────────────────────

ADMIN_TOKEN = "test-admin-token"

GEMINI_RESULT = {
    "match_engine": "gemini",
    "overall_score": 0.87,
    "matching_skills": ["Python", "SQL", "AWS"],
    "ai_match_score": 87.0,
    "ai_skills_score": 90.0,
    "ai_experience_score": 85.0,
    "ai_seniority_fit": 80.0,
    "ai_domain_score": 75.0,
    "ai_strengths": ["Strong backend"],
    "ai_concerns": ["No React"],
    "ai_recommendations": ["Highlight Python"],
    "skill_matches": [{"job_skill": "Python", "resume_skill": "Python", "confidence": 0.95}],
    "skill_gaps_detailed": [{"skill": "React", "importance": "nice_to_have", "transferable_from": None}],
    "match_confidence": 0.9,
}

NLP_RESULT = {
    "match_engine": "nlp",
    "overall_score": 0.65,
    "matching_skills": ["Python"],
}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def engine():
    """Fresh in-memory SQLite DB per test. StaticPool ensures all sessions
    share the same underlying connection (required for in-memory SQLite)."""
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


@pytest.fixture
def client(Session):
    """TestClient wrapping only the admin router, with DB and config patched."""
    app = FastAPI()
    app.include_router(admin_module.router, prefix="/api/admin")

    with patch("backend.routers.admin.SessionLocal", Session), \
         patch("backend.routers.admin.get_config") as mock_cfg:
        mock_cfg.return_value.get.return_value = ADMIN_TOKEN
        yield TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def auth_headers():
    return {"Authorization": f"Bearer {ADMIN_TOKEN}"}


def make_resume(session):
    resume = Resume(skills=["Python", "SQL"], experience_years=5.0)
    session.add(resume)
    session.flush()
    return resume


_job_counter = itertools.count(1)


def make_job(session):
    n = next(_job_counter)
    job = JobPosting(
        title=f"Senior Engineer {n}",
        company=f"Acme Corp {n}",
        posting_date=datetime.utcnow(),
    )
    session.add(job)
    session.flush()
    return job


def make_match(session, job_id, resume_id, match_score=60.0, engine="nlp",
               ai_match_score=None, skill_gaps_detailed=None):
    match = MatchResult(
        job_id=job_id,
        resume_id=resume_id,
        match_score=match_score,
        matching_skills=["Python"],
        match_engine=engine,
        ai_match_score=ai_match_score,
        skill_gaps_detailed=skill_gaps_detailed,
    )
    session.add(match)
    session.flush()
    return match


# ── rematch_job endpoint tests ────────────────────────────────────────────────

class TestRematchJobEndpoint:

    def test_success_updates_match_score_and_matching_skills(self, client, db):
        resume = make_resume(db)
        job = make_job(db)
        match = make_match(db, job.id, resume.id)
        db.commit()

        mock_matcher = MagicMock()
        mock_matcher.match_job.return_value = GEMINI_RESULT

        with patch("backend.services.matcher_service.get_job_matcher", return_value=mock_matcher):
            resp = client.post(f"/api/admin/rematch-job/{job.id}", headers=auth_headers())

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "updated"
        assert data["job_id"] == job.id
        assert data["ai_match_score"] == 87.0
        assert data["matching_skills"] == ["Python", "SQL", "AWS"]
        assert "React" in data["skill_gaps"]

        # Verify DB was updated
        db.refresh(match)
        assert match.match_score == pytest.approx(87.0)
        assert match.matching_skills == ["Python", "SQL", "AWS"]
        assert match.ai_match_score == 87.0
        assert match.match_engine == "gemini"

    def test_success_updates_all_ai_fields(self, client, db):
        resume = make_resume(db)
        job = make_job(db)
        match = make_match(db, job.id, resume.id)
        db.commit()

        mock_matcher = MagicMock()
        mock_matcher.match_job.return_value = GEMINI_RESULT

        with patch("backend.services.matcher_service.get_job_matcher", return_value=mock_matcher):
            client.post(f"/api/admin/rematch-job/{job.id}", headers=auth_headers())

        db.refresh(match)
        assert match.skills_score == 90.0
        assert match.experience_score == 85.0
        assert match.seniority_fit == 80.0
        assert match.domain_score == 75.0
        assert match.ai_strengths == ["Strong backend"]
        assert match.ai_concerns == ["No React"]
        assert match.ai_recommendations == ["Highlight Python"]
        assert match.match_confidence == 0.9
        assert len(match.skill_matches) == 1
        assert len(match.skill_gaps_detailed) == 1

    def test_skips_when_nlp_result_leaves_db_unchanged(self, client, db):
        resume = make_resume(db)
        job = make_job(db)
        original_score = 55.0
        match = make_match(db, job.id, resume.id, match_score=original_score)
        db.commit()

        mock_matcher = MagicMock()
        mock_matcher.match_job.return_value = NLP_RESULT

        with patch("backend.services.matcher_service.get_job_matcher", return_value=mock_matcher):
            resp = client.post(f"/api/admin/rematch-job/{job.id}", headers=auth_headers())

        assert resp.status_code == 200
        assert resp.json()["status"] == "skipped"

        db.refresh(match)
        assert match.match_score == original_score  # unchanged

    def test_404_when_job_not_found(self, client):
        resp = client.post("/api/admin/rematch-job/99999", headers=auth_headers())
        assert resp.status_code == 404

    def test_404_when_no_match_record(self, client, db):
        resume = make_resume(db)
        job = make_job(db)
        db.commit()

        resp = client.post(f"/api/admin/rematch-job/{job.id}", headers=auth_headers())
        assert resp.status_code == 404

    def test_404_when_resume_missing(self, client, db):
        resume = make_resume(db)
        job = make_job(db)
        # Create match pointing to a non-existent resume
        match = MatchResult(
            job_id=job.id,
            resume_id=99999,
            match_score=60.0,
            match_engine="nlp",
        )
        db.add(match)
        db.commit()

        resp = client.post(f"/api/admin/rematch-job/{job.id}", headers=auth_headers())
        assert resp.status_code == 404

    def test_401_without_auth_header(self, client):
        resp = client.post("/api/admin/rematch-job/1")
        assert resp.status_code in (401, 403)

    def test_401_with_wrong_token(self, client):
        resp = client.post(
            "/api/admin/rematch-job/1",
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 401


# ── _do_rematch worker tests ──────────────────────────────────────────────────

class TestDoRematchWorker:

    def test_updates_match_score_and_matching_skills(self, Session, db):
        resume = make_resume(db)
        job = make_job(db)
        match = make_match(db, job.id, resume.id)
        db.commit()

        mock_matcher = MagicMock()
        mock_matcher.match_job.return_value = GEMINI_RESULT

        with patch("backend.routers.admin.SessionLocal", Session), \
             patch("backend.services.matcher_service.get_job_matcher", return_value=mock_matcher):
            _do_rematch("test", [job.id])

        db.refresh(match)
        assert match.match_score == pytest.approx(87.0)
        assert match.matching_skills == ["Python", "SQL", "AWS"]
        assert match.match_engine == "gemini"
        assert match.ai_match_score == 87.0

    def test_updates_all_ai_fields(self, Session, db):
        resume = make_resume(db)
        job = make_job(db)
        match = make_match(db, job.id, resume.id)
        db.commit()

        mock_matcher = MagicMock()
        mock_matcher.match_job.return_value = GEMINI_RESULT

        with patch("backend.routers.admin.SessionLocal", Session), \
             patch("backend.services.matcher_service.get_job_matcher", return_value=mock_matcher):
            _do_rematch("test", [job.id])

        db.refresh(match)
        assert match.skills_score == 90.0
        assert match.experience_score == 85.0
        assert match.seniority_fit == 80.0
        assert match.domain_score == 75.0
        assert match.ai_strengths == ["Strong backend"]
        assert match.ai_concerns == ["No React"]
        assert match.ai_recommendations == ["Highlight Python"]
        assert match.match_confidence == 0.9

    def test_skips_nlp_result_leaves_score_unchanged(self, Session, db):
        resume = make_resume(db)
        job = make_job(db)
        original_score = 45.0
        match = make_match(db, job.id, resume.id, match_score=original_score)
        db.commit()

        mock_matcher = MagicMock()
        mock_matcher.match_job.return_value = NLP_RESULT

        with patch("backend.routers.admin.SessionLocal", Session), \
             patch("backend.services.matcher_service.get_job_matcher", return_value=mock_matcher):
            _do_rematch("test", [job.id])

        db.refresh(match)
        assert match.match_score == original_score

    def test_skips_missing_job_id_gracefully(self, Session, db):
        mock_matcher = MagicMock()
        mock_matcher.match_job.return_value = GEMINI_RESULT

        with patch("backend.routers.admin.SessionLocal", Session), \
             patch("backend.services.matcher_service.get_job_matcher", return_value=mock_matcher):
            _do_rematch("test", [99999])  # should not raise

        mock_matcher.match_job.assert_not_called()

    def test_exception_on_one_job_continues_to_next(self, Session, db):
        """If the first job raises an exception, the second job is still processed."""
        resume = make_resume(db)
        job1 = make_job(db)
        job2 = make_job(db)
        match1 = make_match(db, job1.id, resume.id, match_score=60.0)
        match2 = make_match(db, job2.id, resume.id, match_score=60.0)
        db.commit()

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Simulated Gemini failure")
            return GEMINI_RESULT

        mock_matcher = MagicMock()
        mock_matcher.match_job.side_effect = side_effect

        with patch("backend.routers.admin.SessionLocal", Session), \
             patch("backend.services.matcher_service.get_job_matcher", return_value=mock_matcher):
            _do_rematch("test", [job1.id, job2.id])

        db.refresh(match1)
        db.refresh(match2)
        assert match1.match_score == 60.0          # failed, score unchanged
        assert match2.match_score == pytest.approx(87.0)  # succeeded

    def test_processes_multiple_jobs(self, Session, db):
        resume = make_resume(db)
        job1 = make_job(db)
        job2 = make_job(db)
        match1 = make_match(db, job1.id, resume.id)
        match2 = make_match(db, job2.id, resume.id)
        db.commit()

        mock_matcher = MagicMock()
        mock_matcher.match_job.return_value = GEMINI_RESULT

        with patch("backend.routers.admin.SessionLocal", Session), \
             patch("backend.services.matcher_service.get_job_matcher", return_value=mock_matcher):
            _do_rematch("test", [job1.id, job2.id])

        db.refresh(match1)
        db.refresh(match2)
        assert match1.match_score == pytest.approx(87.0)
        assert match2.match_score == pytest.approx(87.0)
        assert mock_matcher.match_job.call_count == 2


# ── rematch_stale endpoint tests ──────────────────────────────────────────────

class TestRematchStale:

    def test_returns_none_found_when_no_stale_jobs(self, client):
        resp = client.post("/api/admin/rematch-stale", headers=auth_headers())
        assert resp.status_code == 200
        assert resp.json()["status"] == "none_found"
        assert resp.json()["queued"] == 0

    def test_queues_stale_jobs_in_background(self, client, db):
        resume = make_resume(db)
        job = make_job(db)
        # Stale: match_engine=gemini but ai_match_score is NULL
        make_match(db, job.id, resume.id, engine="gemini", ai_match_score=None)
        db.commit()

        with patch("backend.routers.admin._do_rematch") as mock_rematch:
            resp = client.post("/api/admin/rematch-stale", headers=auth_headers())

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "started"
        assert data["queued"] >= 1
        # _do_rematch is called via FastAPI BackgroundTasks
        mock_rematch.assert_called_once()
        assert mock_rematch.call_args[0][0] == "rematch-stale"
        assert job.id in mock_rematch.call_args[0][1]

    def test_does_not_queue_non_gemini_matches(self, client, db):
        resume = make_resume(db)
        job = make_job(db)
        # NLP match — should not be considered stale for rematch_stale
        make_match(db, job.id, resume.id, engine="nlp", ai_match_score=None)
        db.commit()

        resp = client.post("/api/admin/rematch-stale", headers=auth_headers())
        assert resp.status_code == 200
        assert resp.json()["status"] == "none_found"


# ── rematch_by_gap endpoint tests ─────────────────────────────────────────────

class TestRematchByGap:

    def test_returns_none_found_when_no_matching_gap(self, client):
        resp = client.post(
            "/api/admin/rematch-by-gap?skill=nonexistentskillxyz",
            headers=auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "none_found"

    def test_queues_jobs_with_matching_skill_gap(self, client, db):
        resume = make_resume(db)
        job = make_job(db)
        make_match(
            db, job.id, resume.id,
            skill_gaps_detailed=[{"skill": "Kubernetes", "importance": "must_have"}],
        )
        db.commit()

        with patch("backend.routers.admin._do_rematch_by_gap") as mock_rematch:
            resp = client.post(
                "/api/admin/rematch-by-gap?skill=kubernetes",  # case-insensitive
                headers=auth_headers(),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "started"
        assert data["skill"] == "kubernetes"
        assert data["queued"] >= 1
        # _do_rematch_by_gap is called via FastAPI BackgroundTasks
        mock_rematch.assert_called_once()
        assert mock_rematch.call_args[0][0] == "kubernetes"

    def test_does_not_queue_jobs_without_skill_gaps(self, client, db):
        resume = make_resume(db)
        job = make_job(db)
        # Match with no skill_gaps_detailed
        make_match(db, job.id, resume.id)
        db.commit()

        resp = client.post(
            "/api/admin/rematch-by-gap?skill=python",
            headers=auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "none_found"
