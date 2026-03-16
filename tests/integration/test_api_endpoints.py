"""Integration tests for API read endpoints.

Pre-seeds the DB with realistic data and tests the jobs list/detail/analytics
endpoints via TestClient. Mounts individual routers to avoid backend/tests/conftest.py.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.database.models import JobPosting, MatchResult, Resume
from backend.routers import jobs as jobs_module
from backend.routers import search as search_module
from tests.integration.conftest import make_job, make_resume, make_match


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_jobs_client(Session):
    """Build a TestClient with the jobs router mounted."""
    app = FastAPI()
    app.include_router(jobs_module.router, prefix="/api/jobs")

    # Override the get_db dependency to use our test Session
    from src.database.db import get_db

    def override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _seed_jobs(session, count=3):
    """Seed the DB with jobs + matches and return them."""
    resume = make_resume(session)
    jobs = []
    matches = []
    for i in range(count):
        job = make_job(
            session,
            title=f"Engineer Role {i+1}",
            company=f"Company {i+1}",
            location="Toronto, Canada",
            required_skills=["Python", "SQL", "React"],
            structured_requirements={"must_have_skills": [{"name": "Python"}, {"name": "SQL"}]},
        )
        match = make_match(
            session, job.id, resume.id,
            match_score=90.0 - (i * 10),
            ai_match_score=90.0 - (i * 10),
            matching_skills=["Python", "SQL"],
            ai_strengths=[f"Strength {i+1}"],
            ai_concerns=[f"Concern {i+1}"],
            skill_gaps_detailed=[
                {"skill": "React", "importance": "nice_to_have", "transferable_from": None}
            ],
        )
        jobs.append(job)
        matches.append(match)

    session.commit()
    return resume, jobs, matches


# ── Job List Tests ────────────────────────────────────────────────────────────

class TestJobsList:

    def test_returns_seeded_jobs(self, Session, db):
        _seed_jobs(db, count=3)
        client = _make_jobs_client(Session)

        resp = client.get("/api/jobs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert data["filtered"] == 3
        assert len(data["jobs"]) == 3

    def test_jobs_sorted_by_score_desc(self, Session, db):
        _seed_jobs(db, count=3)
        client = _make_jobs_client(Session)

        resp = client.get("/api/jobs?sort_by=score&sort_order=desc")
        jobs = resp.json()["jobs"]
        scores = [j["match_score"] for j in jobs]
        assert scores == sorted(scores, reverse=True)

    def test_min_score_filter(self, Session, db):
        _seed_jobs(db, count=3)  # scores: 90, 80, 70
        client = _make_jobs_client(Session)

        resp = client.get("/api/jobs?min_score=80")
        data = resp.json()
        # Only jobs with score >= 80 should be returned
        assert all(j["match_score"] >= 80 for j in data["jobs"])
        assert data["filtered"] == 2

    def test_max_score_filter(self, Session, db):
        _seed_jobs(db, count=3)  # scores: 90, 80, 70
        client = _make_jobs_client(Session)

        resp = client.get("/api/jobs?max_score=80")
        data = resp.json()
        assert all(j["match_score"] <= 80 for j in data["jobs"])

    def test_search_by_title(self, Session, db):
        _seed_jobs(db, count=3)
        client = _make_jobs_client(Session)

        resp = client.get("/api/jobs?search=Role 1")
        data = resp.json()
        assert data["filtered"] >= 1
        assert any("Role 1" in j["title"] for j in data["jobs"])

    def test_search_by_company(self, Session, db):
        _seed_jobs(db, count=3)
        client = _make_jobs_client(Session)

        resp = client.get("/api/jobs?search=Company 2")
        data = resp.json()
        assert data["filtered"] >= 1
        assert any("Company 2" in j["company"] for j in data["jobs"])

    def test_limit_parameter(self, Session, db):
        _seed_jobs(db, count=5)
        client = _make_jobs_client(Session)

        resp = client.get("/api/jobs?limit=2")
        data = resp.json()
        assert data["filtered"] <= 2

    def test_hearted_only_filter(self, Session, db):
        resume = make_resume(db)
        j1 = make_job(db, title="Hearted Job")
        j2 = make_job(db, title="Normal Job")
        make_match(db, j1.id, resume.id, user_status="hearted")
        make_match(db, j2.id, resume.id, user_status=None)
        db.commit()

        client = _make_jobs_client(Session)
        resp = client.get("/api/jobs?hearted_only=true")
        data = resp.json()
        assert data["filtered"] == 1
        assert data["jobs"][0]["user_status"] == "hearted"

    def test_ignored_jobs_excluded_by_default(self, Session, db):
        resume = make_resume(db)
        j1 = make_job(db, title="Normal Job")
        j2 = make_job(db, title="Ignored Job")
        make_match(db, j1.id, resume.id, user_status=None)
        make_match(db, j2.id, resume.id, user_status="ignored")
        db.commit()

        client = _make_jobs_client(Session)
        resp = client.get("/api/jobs")
        data = resp.json()
        assert data["filtered"] == 1
        assert data["jobs"][0]["title"] == "Normal Job"


# ── Job Detail Tests ──────────────────────────────────────────────────────────

class TestJobDetail:

    def test_returns_full_job_details(self, Session, db):
        resume, jobs, matches = _seed_jobs(db, count=1)
        client = _make_jobs_client(Session)

        resp = client.get(f"/api/jobs/{jobs[0].id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == jobs[0].id
        assert data["title"] == jobs[0].title
        assert data["company"] == jobs[0].company
        assert data["match_score"] == 90.0
        assert data["match_engine"] == "gemini"

    def test_includes_ai_fields(self, Session, db):
        resume, jobs, matches = _seed_jobs(db, count=1)
        client = _make_jobs_client(Session)

        resp = client.get(f"/api/jobs/{jobs[0].id}")
        data = resp.json()
        assert "matching_skills" in data
        assert len(data["matching_skills"]) > 0
        assert "skill_gaps" in data
        assert "critical_skill_gaps" in data

    def test_404_for_nonexistent_job(self, Session, db):
        client = _make_jobs_client(Session)
        resp = client.get("/api/jobs/99999")
        assert resp.status_code == 404


# ── Job Status Update Tests ───────────────────────────────────────────────────

class TestJobStatusUpdate:

    def test_heart_job(self, Session, db):
        resume, jobs, matches = _seed_jobs(db, count=1)
        client = _make_jobs_client(Session)

        resp = client.patch(
            f"/api/jobs/{jobs[0].id}/status",
            json={"user_status": "hearted"}
        )
        assert resp.status_code == 200
        assert resp.json()["user_status"] == "hearted"

        # Verify persisted
        db.refresh(matches[0])
        assert matches[0].user_status == "hearted"

    def test_ignore_job(self, Session, db):
        resume, jobs, matches = _seed_jobs(db, count=1)
        client = _make_jobs_client(Session)

        resp = client.patch(
            f"/api/jobs/{jobs[0].id}/status",
            json={"user_status": "ignored"}
        )
        assert resp.status_code == 200
        assert resp.json()["user_status"] == "ignored"

    def test_clear_status(self, Session, db):
        resume, jobs, matches = _seed_jobs(db, count=1)
        matches[0].user_status = "hearted"
        db.commit()

        client = _make_jobs_client(Session)
        resp = client.patch(
            f"/api/jobs/{jobs[0].id}/status",
            json={"user_status": None}
        )
        assert resp.status_code == 200
        assert resp.json()["user_status"] is None

    def test_invalid_status_returns_400(self, Session, db):
        resume, jobs, matches = _seed_jobs(db, count=1)
        client = _make_jobs_client(Session)

        resp = client.patch(
            f"/api/jobs/{jobs[0].id}/status",
            json={"user_status": "invalid_status"}
        )
        assert resp.status_code == 400

    def test_404_for_nonexistent_match(self, Session, db):
        client = _make_jobs_client(Session)
        resp = client.patch(
            "/api/jobs/99999/status",
            json={"user_status": "hearted"}
        )
        assert resp.status_code == 404


# ── Stats Summary Tests ───────────────────────────────────────────────────────

class TestStatsSummary:

    def test_returns_correct_counts(self, Session, db):
        _seed_jobs(db, count=3)  # scores: 90, 80, 70
        client = _make_jobs_client(Session)

        resp = client.get("/api/jobs/stats/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_jobs"] == 3
        assert data["high_match_count"] == 1  # only 90 >= 85
        assert 70 <= data["average_match_score"] <= 90

    def test_empty_db_returns_zeros(self, Session, db):
        client = _make_jobs_client(Session)

        resp = client.get("/api/jobs/stats/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_jobs"] == 0
        assert data["average_match_score"] == 0


# ── Search Defaults Tests ────────────────────────────────────────────────────

class TestSearchDefaults:

    def test_returns_default_config(self, Session, db, mock_config):
        app = FastAPI()
        app.include_router(search_module.router, prefix="/api/search")

        with patch("backend.routers.search.get_config", return_value=mock_config):
            client = TestClient(app)
            resp = client.get("/api/search/defaults")

        assert resp.status_code == 200
        data = resp.json()
        assert "location" in data
        assert "max_results" in data
        assert data["location"] == "United States"
        assert data["max_results"] == 50
