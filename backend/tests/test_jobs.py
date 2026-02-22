from datetime import datetime, timedelta
import pytest
from src.database.models import JobPosting, MatchResult, Resume


def test_read_jobs_empty(client, db_session):
    """Test that empty database returns empty job list."""
    response = client.get("/api/jobs")
    assert response.status_code == 200
    data = response.json()
    assert data["jobs"] == []
    assert data["total"] == 0


def test_read_jobs_with_data(client, db_session):
    """Test listing jobs with data in database."""
    # Create a Resume first (required for foreign key)
    resume = Resume(skills=["Python", "Agile"], experience_years=5.0)
    db_session.add(resume)
    db_session.commit()
    db_session.refresh(resume)

    # Add dummy job
    job = JobPosting(
        title="Senior Product Manager",
        company="Tech Corp",
        description="We need a PM.",
        posting_date=datetime.now(),
        url="http://example.com/job",
        location="Remote"
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    # Create MatchResult with correct field names
    match = MatchResult(
        job_id=job.id,
        resume_id=resume.id,
        match_score=85.5,
        matching_skills=["Agile"],
        experience_alignment="Good match"
    )
    db_session.add(match)
    db_session.commit()

    response = client.get("/api/jobs")
    assert response.status_code == 200
    data = response.json()
    assert len(data["jobs"]) >= 1
    # Find our job in the list
    job_titles = [j["title"] for j in data["jobs"]]
    assert "Senior Product Manager" in job_titles


def test_read_job_detail(client, db_session):
    """Test getting a single job by ID."""
    # Create a Resume first
    resume = Resume(skills=["Python"], experience_years=3.0)
    db_session.add(resume)
    db_session.commit()
    db_session.refresh(resume)

    # Add dummy job
    job = JobPosting(
        title="Specific Job",
        company="Specific Corp",
        description="Details here.",
        posting_date=datetime.now(),
        url="http://example.com/job2",
        location="New York"
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    job_id = job.id

    # Create MatchResult
    match = MatchResult(
        job_id=job.id,
        resume_id=resume.id,
        match_score=99.0
    )
    db_session.add(match)
    db_session.commit()

    response = client.get(f"/api/jobs/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Specific Job"


def test_job_not_found(client):
    """Test 404 for non-existent job."""
    response = client.get("/api/jobs/99999")
    assert response.status_code == 404


@pytest.mark.skip(reason="Fetch endpoint not implemented - Task 2.3 marked but endpoint missing")
def test_fetch_jobs_trigger(client):
    """Test triggering job fetch from scraper."""
    response = client.post("/api/jobs/fetch", params={"profile": "pm"})
    assert response.status_code in [200, 202]


# ---------------------------------------------------------------------------
# None-filtering in list fields (Issue #1 read-path guard)
# ---------------------------------------------------------------------------

class TestNoneFilteringInResponse:
    """Verify that None entries in DB list columns are filtered from API responses.

    These tests use MatchResult rows with intentional None values in list columns
    (simulating rows written before the write-path fix). The router's read-path
    defence should strip them so no consumer ever sees a None in a list field.
    """

    def _make_data(self, db_session):
        """Create a minimal resume + job in the DB and return their IDs."""
        resume = Resume(skills=["Python"], experience_years=5.0)
        db_session.add(resume)
        db_session.commit()
        db_session.refresh(resume)

        job = JobPosting(
            title="Test Job",
            company="Test Corp",
            description="A test job.",
            posting_date=datetime.now(),
            url="http://example.com/test",
            location="Remote",
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)
        return resume, job

    def test_matching_skills_nones_filtered(self, client, db_session):
        resume, job = self._make_data(db_session)
        match = MatchResult(
            job_id=job.id,
            resume_id=resume.id,
            match_score=75.0,
            matching_skills=["Python", None, "SQL"],
        )
        db_session.add(match)
        db_session.commit()

        response = client.get("/api/jobs")
        assert response.status_code == 200
        jobs = response.json()["jobs"]
        assert len(jobs) >= 1
        found = next(j for j in jobs if j["title"] == "Test Job")
        assert None not in found["matching_skills"], (
            f"matching_skills contains None: {found['matching_skills']}"
        )
        assert "Python" in found["matching_skills"]
        assert "SQL" in found["matching_skills"]

    def test_gemini_strengths_nones_filtered(self, client, db_session):
        resume, job = self._make_data(db_session)
        match = MatchResult(
            job_id=job.id,
            resume_id=resume.id,
            match_score=80.0,
            matching_skills=["Python"],
            gemini_strengths=["Strong backend", None, "5 years exp"],
            match_engine="gemini",
        )
        db_session.add(match)
        db_session.commit()

        response = client.get("/api/jobs")
        assert response.status_code == 200
        jobs = response.json()["jobs"]
        found = next(j for j in jobs if j["title"] == "Test Job")
        assert None not in found["gemini_strengths"], (
            f"gemini_strengths contains None: {found['gemini_strengths']}"
        )
        assert len(found["gemini_strengths"]) == 2

    def test_gemini_gaps_nones_filtered(self, client, db_session):
        resume, job = self._make_data(db_session)
        match = MatchResult(
            job_id=job.id,
            resume_id=resume.id,
            match_score=70.0,
            matching_skills=["Python"],
            gemini_gaps=[None, "Missing Kubernetes"],
            match_engine="gemini",
        )
        db_session.add(match)
        db_session.commit()

        response = client.get("/api/jobs")
        assert response.status_code == 200
        jobs = response.json()["jobs"]
        found = next(j for j in jobs if j["title"] == "Test Job")
        assert None not in found["gemini_gaps"], (
            f"gemini_gaps contains None: {found['gemini_gaps']}"
        )
        assert found["gemini_gaps"] == ["Missing Kubernetes"]

    def test_missing_domains_nones_filtered(self, client, db_session):
        resume, job = self._make_data(db_session)
        match = MatchResult(
            job_id=job.id,
            resume_id=resume.id,
            match_score=65.0,
            matching_skills=["Python"],
            missing_domains=["fintech", None],
        )
        db_session.add(match)
        db_session.commit()

        response = client.get("/api/jobs")
        assert response.status_code == 200
        jobs = response.json()["jobs"]
        found = next(j for j in jobs if j["title"] == "Test Job")
        assert None not in found["missing_domains"], (
            f"missing_domains contains None: {found['missing_domains']}"
        )
        assert found["missing_domains"] == ["fintech"]

    def test_clean_data_passes_through_unchanged(self, client, db_session):
        """When no Nones in DB, the list values reach the response exactly."""
        resume, job = self._make_data(db_session)
        match = MatchResult(
            job_id=job.id,
            resume_id=resume.id,
            match_score=90.0,
            matching_skills=["Python", "SQL", "AWS"],
            gemini_strengths=["Strong Python"],
            gemini_gaps=["Missing Go"],
            missing_domains=["fintech"],
            match_engine="gemini",
        )
        db_session.add(match)
        db_session.commit()

        response = client.get("/api/jobs")
        assert response.status_code == 200
        jobs = response.json()["jobs"]
        found = next(j for j in jobs if j["title"] == "Test Job")
        assert found["matching_skills"] == ["Python", "SQL", "AWS"]
        assert found["gemini_strengths"] == ["Strong Python"]
        assert found["gemini_gaps"] == ["Missing Go"]
        assert found["missing_domains"] == ["fintech"]


class TestNoneFilteringInDetailResponse:
    """Same None-filtering guards must apply to the GET /api/jobs/{id} detail endpoint.

    The list endpoint had guards added in the code review fix; the detail endpoint
    also returns these fields and must strip legacy None entries from DB rows.
    """

    def _make_job_with_match(self, db_session, **match_kwargs):
        resume = Resume(skills=["Python"], experience_years=5.0)
        db_session.add(resume)
        db_session.commit()
        db_session.refresh(resume)

        job = JobPosting(
            title="Detail Test Job",
            company="Detail Corp",
            description="A detail test job.",
            posting_date=datetime.now(),
            url="http://example.com/detail",
            location="Remote",
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        match = MatchResult(
            job_id=job.id,
            resume_id=resume.id,
            match_score=80.0,
            matching_skills=["Python"],
            **match_kwargs,
        )
        db_session.add(match)
        db_session.commit()
        return job.id

    def test_detail_gemini_strengths_nones_filtered(self, client, db_session):
        job_id = self._make_job_with_match(
            db_session,
            gemini_strengths=["Strong Python", None, "5 years exp"],
            match_engine="gemini",
        )
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert None not in data["gemini_strengths"]
        assert len(data["gemini_strengths"]) == 2

    def test_detail_gemini_gaps_nones_filtered(self, client, db_session):
        job_id = self._make_job_with_match(
            db_session,
            gemini_gaps=[None, "Missing Kubernetes"],
            match_engine="gemini",
        )
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert None not in data["gemini_gaps"]
        assert data["gemini_gaps"] == ["Missing Kubernetes"]

    def test_detail_missing_domains_nones_filtered(self, client, db_session):
        job_id = self._make_job_with_match(
            db_session,
            missing_domains=["fintech", None],
        )
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert None not in data["missing_domains"]
        assert data["missing_domains"] == ["fintech"]

    def test_detail_clean_data_passes_through_unchanged(self, client, db_session):
        job_id = self._make_job_with_match(
            db_session,
            gemini_strengths=["Strong Python"],
            gemini_gaps=["Missing Go"],
            missing_domains=["fintech"],
            match_engine="gemini",
        )
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["gemini_strengths"] == ["Strong Python"]
        assert data["gemini_gaps"] == ["Missing Go"]
        assert data["missing_domains"] == ["fintech"]
