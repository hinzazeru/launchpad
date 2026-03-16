"""Integration tests for the full search pipeline (POST /search/jobs/start).

Tests the happy path through all 5 stages:
  fetch → import → match → export → complete

Uses in-memory SQLite and mocked external services (provider, matcher, Gemini).
FastAPI BackgroundTasks run synchronously inside TestClient, so the pipeline
completes before the response is inspected.
"""

import uuid
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.database.models import SearchJob
from backend.routers import search as search_module
from tests.integration.conftest import (
    make_search_client, stop_patches, start_search, make_job, make_resume,
)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestPipelineHappyPath:

    def test_full_pipeline_completes_with_correct_results(
        self, Session, db, fake_resume_dir, mock_job_provider, mock_job_matcher, mock_config
    ):
        """Start a search, verify the endpoint returns a pending search_id,
        then verify the pipeline ran all stages and persisted correct results."""
        client, ctx = make_search_client(
            Session, fake_resume_dir, mock_job_provider, mock_job_matcher, mock_config
        )
        try:
            resp = start_search(client)
            assert resp.status_code == 200
            data = resp.json()
            assert "search_id" in data
            assert data["status"] == "pending"

            search_id = data["search_id"]

            # BackgroundTasks run synchronously in TestClient, so job is done
            job = db.query(SearchJob).filter(SearchJob.search_id == search_id).first()
            assert job is not None
            assert job.keyword == "Senior Engineer"
            assert job.resume_filename == "test_resume.md"

            # Pipeline completed all stages
            assert job.status == "completed"
            assert job.stage == "completed"
            assert job.progress == 100

            # Result JSON is correct
            result = job.result
            assert result is not None
            assert result["success"] is True
            assert result["jobs_fetched"] == 3  # sample_raw_jobs has 3
            assert result["jobs_matched"] >= 0
            assert result["exported_to_sheets"] == 0  # export_to_sheets=False

            # Progress counters populated
            assert job.jobs_found == 3

            # Provider and matcher were called
            mock_job_provider.search_jobs_async.assert_called_once()
            mock_job_provider.import_jobs.assert_called_once()
            mock_job_matcher.match_jobs.assert_called_once()
        finally:
            stop_patches(ctx)


class TestPipelineHandlesNoJobs:

    def test_empty_provider_completes_with_zero_jobs(
        self, Session, db, fake_resume_dir, mock_job_matcher, mock_config
    ):
        """When the provider returns no jobs, pipeline should complete gracefully."""
        empty_provider = MagicMock()
        empty_provider.search_jobs_async = AsyncMock(return_value=[])
        empty_provider.normalize_job = MagicMock()
        empty_provider.import_jobs = MagicMock(return_value=0)

        client, ctx = make_search_client(
            Session, fake_resume_dir, empty_provider, mock_job_matcher, mock_config
        )
        try:
            resp = start_search(client)
            search_id = resp.json()["search_id"]

            job = db.query(SearchJob).filter(SearchJob.search_id == search_id).first()
            assert job.status == "completed"
            assert job.result["jobs_fetched"] == 0
            assert job.result["jobs_matched"] == 0

            # Matcher should NOT have been called
            mock_job_matcher.match_jobs.assert_not_called()
        finally:
            stop_patches(ctx)


class TestPipelineMatchFailure:

    def test_matcher_exception_sets_status_failed(
        self, Session, db, fake_resume_dir, mock_job_provider, mock_config
    ):
        """If the matcher raises, the SearchJob should be marked as failed."""
        failing_matcher = MagicMock()
        failing_matcher.match_jobs.side_effect = RuntimeError("Model loading failed")

        # Seed jobs so the DB query in stage 4 finds something
        session = Session()
        make_resume(session)
        make_job(session, title="Senior Engineer", location="Canada",
                 posting_date=None)
        session.commit()
        session.close()

        client, ctx = make_search_client(
            Session, fake_resume_dir, mock_job_provider, failing_matcher, mock_config
        )
        try:
            resp = start_search(client)
            search_id = resp.json()["search_id"]

            sj = db.query(SearchJob).filter(SearchJob.search_id == search_id).first()
            assert sj.status == "failed"
            assert "Model loading failed" in (sj.error or "")
        finally:
            stop_patches(ctx)


class TestPipelineDeduplication:

    def test_duplicate_raw_jobs_are_deduplicated(
        self, Session, db, fake_resume_dir, mock_job_matcher, mock_config
    ):
        """Duplicate (title, company) pairs in raw jobs should be reduced."""
        dup_jobs = [
            {"title": "Engineer", "companyName": "SameCo",
             "description": "x" * 300, "location": "Canada",
             "url": "https://a.com/1", "postedAt": "2026-01-01"},
            {"title": "Engineer", "companyName": "SameCo",
             "description": "x" * 300, "location": "Canada",
             "url": "https://a.com/2", "postedAt": "2026-01-01"},
            {"title": "Different Role", "companyName": "OtherCo",
             "description": "y" * 300, "location": "Canada",
             "url": "https://b.com/1", "postedAt": "2026-01-01"},
        ]

        provider = MagicMock()
        provider.search_jobs_async = AsyncMock(return_value=dup_jobs)
        provider.normalize_job = MagicMock(side_effect=lambda j: {
            "title": j["title"], "company": j["companyName"],
            "description": j["description"], "location": j["location"],
            "url": j["url"], "posting_date": j["postedAt"],
        })
        provider.import_jobs = MagicMock(return_value=2)

        client, ctx = make_search_client(
            Session, fake_resume_dir, provider, mock_job_matcher, mock_config
        )
        try:
            resp = start_search(client)
            search_id = resp.json()["search_id"]

            sj = db.query(SearchJob).filter(SearchJob.search_id == search_id).first()
            # After dedup, only 2 unique jobs remain
            assert sj.jobs_found == 2
        finally:
            stop_patches(ctx)


class TestPipelineFiltersShortDescriptions:

    def test_short_descriptions_excluded_from_matching(
        self, Session, db, fake_resume_dir, mock_job_provider, mock_config
    ):
        """Jobs with description < 200 chars should be excluded at match stage."""
        session = Session()
        make_resume(session)
        make_job(session, title="Senior Engineer Short", description="Too short",
                 location="Canada")
        make_job(session, title="Senior Engineer Long", description="A" * 300,
                 location="Canada")
        session.commit()
        session.close()

        call_args_holder = {}
        def capture_match_jobs(resume_obj, jobs, **kwargs):
            call_args_holder["jobs"] = jobs
            return ([], None)

        matcher = MagicMock()
        matcher.match_jobs.side_effect = capture_match_jobs
        matcher.save_match_results = MagicMock()

        client, ctx = make_search_client(
            Session, fake_resume_dir, mock_job_provider, matcher, mock_config
        )
        try:
            start_search(client)

            if "jobs" in call_args_holder:
                for j in call_args_holder["jobs"]:
                    assert len(j.description or "") >= 200
        finally:
            stop_patches(ctx)


class TestCancelSearchJob:

    def test_cancel_sets_cancellation_flag(self, Session, db):
        """POST /jobs/{search_id}/cancel should set cancellation_requested."""
        app = FastAPI()
        app.include_router(search_module.router, prefix="/api/search")

        with patch("backend.routers.search.SessionLocal", Session):
            client = TestClient(app)

            session = Session()
            sid = str(uuid.uuid4())
            sj = SearchJob(
                search_id=sid, status="running", stage="fetching",
                progress=30, keyword="Test", resume_filename="test.md",
                trigger_source="manual",
            )
            session.add(sj)
            session.commit()
            session.close()

            resp = client.post(f"/api/search/jobs/{sid}/cancel")
            assert resp.status_code == 200

            refreshed = db.query(SearchJob).filter(SearchJob.search_id == sid).first()
            assert refreshed.cancellation_requested is True

    def test_cancel_completed_job_returns_400(self, Session, db):
        app = FastAPI()
        app.include_router(search_module.router, prefix="/api/search")

        with patch("backend.routers.search.SessionLocal", Session):
            client = TestClient(app)

            session = Session()
            sid = str(uuid.uuid4())
            sj = SearchJob(
                search_id=sid, status="completed", stage="completed",
                progress=100, keyword="Test", resume_filename="test.md",
                trigger_source="manual",
            )
            session.add(sj)
            session.commit()
            session.close()

            resp = client.post(f"/api/search/jobs/{sid}/cancel")
            assert resp.status_code == 400


class TestGetSearchStatus:

    def test_get_status_returns_current_progress(self, Session, db):
        app = FastAPI()
        app.include_router(search_module.router, prefix="/api/search")

        with patch("backend.routers.search.SessionLocal", Session):
            client = TestClient(app)

            session = Session()
            sid = str(uuid.uuid4())
            sj = SearchJob(
                search_id=sid, status="running", stage="matching",
                progress=60, message="Matching 10 jobs...",
                keyword="Engineer", resume_filename="test.md",
                trigger_source="manual", jobs_found=15,
            )
            session.add(sj)
            session.commit()
            session.close()

            resp = client.get(f"/api/search/jobs/{sid}/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "running"
            assert data["stage"] == "matching"
            assert data["progress"] == 60
            assert data["jobs_found"] == 15

    def test_get_status_404_for_unknown_id(self, Session, db):
        app = FastAPI()
        app.include_router(search_module.router, prefix="/api/search")

        with patch("backend.routers.search.SessionLocal", Session):
            client = TestClient(app)
            resp = client.get("/api/search/jobs/nonexistent-id/status")
            assert resp.status_code == 404
