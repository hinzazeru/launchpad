"""
End-to-end tests for the Scheduler API endpoints.

Tests the full CRUD lifecycle for scheduled searches, including:
- Create, Read, Update, Delete operations
- Toggle enable/disable
- Run now functionality
- Scheduler status endpoint
"""

import pytest
from datetime import datetime


class TestSchedulerCRUD:
    """Test scheduler CRUD operations."""

    def test_list_schedules_empty(self, client, db_session):
        """GET /api/scheduler/schedules returns empty list initially."""
        response = client.get("/api/scheduler/schedules")
        assert response.status_code == 200
        data = response.json()
        assert data["schedules"] == []
        assert data["total"] == 0

    def test_create_schedule_success(self, client, db_session):
        """POST /api/scheduler/schedules creates a new schedule."""
        payload = {
            "name": "Daily PM Search",
            "keyword": "Product Manager",
            "location": "Canada",
            "resume_filename": "test_resume.txt",
            "run_times": ["08:00", "16:00"],
            "timezone": "America/Toronto",
            "max_results": 25,
            "export_to_sheets": True,
            "enabled": True,
        }
        response = client.post("/api/scheduler/schedules", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "Daily PM Search"
        assert data["keyword"] == "Product Manager"
        assert data["location"] == "Canada"
        assert data["resume_filename"] == "test_resume.txt"
        assert data["run_times"] == ["08:00", "16:00"]
        assert data["timezone"] == "America/Toronto"
        assert data["enabled"] is True
        assert "id" in data
        assert "created_at" in data

    def test_create_schedule_validation_error(self, client, db_session):
        """POST /api/scheduler/schedules fails with missing required fields."""
        payload = {
            "name": "Missing Keyword Schedule"
            # Missing required: keyword, resume_filename
        }
        response = client.post("/api/scheduler/schedules", json=payload)
        assert response.status_code == 422  # Validation error

    def test_create_schedule_invalid_run_times(self, client, db_session):
        """POST /api/scheduler/schedules fails with invalid time format."""
        payload = {
            "name": "Invalid Times",
            "keyword": "Developer",
            "resume_filename": "test.txt",
            "run_times": ["8am", "4pm"],  # Invalid format, should be HH:MM
        }
        response = client.post("/api/scheduler/schedules", json=payload)
        assert response.status_code == 422

    def test_get_schedule_by_id(self, client, db_session):
        """GET /api/scheduler/schedules/{id} returns schedule details."""
        # Create a schedule first
        payload = {
            "name": "Test Schedule",
            "keyword": "Python Developer",
            "resume_filename": "resume.txt",
        }
        create_response = client.post("/api/scheduler/schedules", json=payload)
        schedule_id = create_response.json()["id"]

        # Get by ID
        response = client.get(f"/api/scheduler/schedules/{schedule_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == schedule_id
        assert data["name"] == "Test Schedule"

    def test_get_schedule_not_found(self, client, db_session):
        """GET /api/scheduler/schedules/{id} returns 404 for non-existent ID."""
        response = client.get("/api/scheduler/schedules/99999")
        assert response.status_code == 404

    def test_update_schedule(self, client, db_session):
        """PUT /api/scheduler/schedules/{id} updates schedule fields."""
        # Create a schedule
        payload = {
            "name": "Original Name",
            "keyword": "Original Keyword",
            "resume_filename": "resume.txt",
        }
        create_response = client.post("/api/scheduler/schedules", json=payload)
        schedule_id = create_response.json()["id"]

        # Update it
        update_payload = {
            "name": "Updated Name",
            "keyword": "Updated Keyword",
            "max_results": 50,
        }
        response = client.put(f"/api/scheduler/schedules/{schedule_id}", json=update_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["keyword"] == "Updated Keyword"
        assert data["max_results"] == 50

    def test_delete_schedule(self, client, db_session):
        """DELETE /api/scheduler/schedules/{id} removes the schedule."""
        # Create a schedule
        payload = {
            "name": "To Delete",
            "keyword": "Delete Me",
            "resume_filename": "resume.txt",
        }
        create_response = client.post("/api/scheduler/schedules", json=payload)
        schedule_id = create_response.json()["id"]

        # Delete it
        response = client.delete(f"/api/scheduler/schedules/{schedule_id}")
        assert response.status_code == 200

        # Verify it's gone
        get_response = client.get(f"/api/scheduler/schedules/{schedule_id}")
        assert get_response.status_code == 404

    def test_list_schedules_after_create(self, client, db_session):
        """GET /api/scheduler/schedules returns created schedules."""
        # Create two schedules
        for i in range(2):
            payload = {
                "name": f"Schedule {i}",
                "keyword": f"Keyword {i}",
                "resume_filename": "resume.txt",
            }
            client.post("/api/scheduler/schedules", json=payload)

        response = client.get("/api/scheduler/schedules")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["schedules"]) == 2


class TestSchedulerActions:
    """Test scheduler action endpoints (toggle, run-now)."""

    def test_toggle_schedule_enabled(self, client, db_session):
        """POST /api/scheduler/schedules/{id}/toggle toggles enabled state."""
        # Create enabled schedule
        payload = {
            "name": "Toggle Test",
            "keyword": "Test",
            "resume_filename": "resume.txt",
            "enabled": True,
        }
        create_response = client.post("/api/scheduler/schedules", json=payload)
        schedule_id = create_response.json()["id"]

        # Toggle to disabled
        response = client.post(f"/api/scheduler/schedules/{schedule_id}/toggle")
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False

        # Toggle back to enabled
        response = client.post(f"/api/scheduler/schedules/{schedule_id}/toggle")
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True

    def test_run_now_starts_background_search(self, client, db_session):
        """POST /api/scheduler/schedules/{id}/run-now triggers background execution."""
        payload = {
            "name": "Run Now Test",
            "keyword": "Immediate Search",
            "resume_filename": "resume.txt",
        }
        create_response = client.post("/api/scheduler/schedules", json=payload)
        schedule_id = create_response.json()["id"]

        response = client.post(f"/api/scheduler/schedules/{schedule_id}/run-now")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == schedule_id
        assert "message" in data
        assert "search_id" in data


class TestSchedulerStatus:
    """Test scheduler status endpoint."""

    def test_get_scheduler_status(self, client, db_session):
        """GET /api/scheduler/status returns scheduler operational status."""
        response = client.get("/api/scheduler/status")
        assert response.status_code == 200
        data = response.json()
        
        # Should have running status and schedule count
        assert "running" in data
        assert "active_schedules" in data
        assert isinstance(data["running"], bool)
        assert isinstance(data["active_schedules"], int)


class TestRecentSearchesTriggerSource:
    """Test that trigger_source is correctly returned in recent searches."""

    def test_recent_searches_includes_trigger_source(self, client, db_session):
        """GET /api/analytics/performance/recent-searches includes trigger_source field."""
        response = client.get("/api/analytics/performance/recent-searches")
        assert response.status_code == 200
        data = response.json()
        
        # Should return searches array (may be empty)
        assert "searches" in data
        
        # If there are searches, each should have trigger_source
        for search in data["searches"]:
            assert "trigger_source" in search
            assert search["trigger_source"] in ["manual", "scheduled"]
