# Scheduled Runs for Web App

## Overview

Add scheduled job search capability to the web app, reusing components from the Telegram scheduler. Scheduled runs behave identically to user-driven searches, with tracking to distinguish between them.

### User Requirements
- **Frequency**: Fixed daily times (e.g., 8am, 12pm, 4pm, 8pm)
- **Multiple schedules**: Yes - different keywords can have separate schedules
- **UI Location**: Separate "Schedule" tab in Get Jobs page
- **Notifications**: Continue using Telegram for scheduled run notifications

---

## Design Decisions

| Topic | Decision |
|-------|----------|
| **Concurrency** | Skip new runs if previous is still in progress (`max_instances=1`) |
| **Error Handling** | Log errors and wait for next scheduled time (no auto-retry) |
| **Persistence** | Store schedules in DB, reload via `load_schedules_from_db()` at startup |
| **Timezones** | Store `run_times` as local time strings (e.g., "08:00") with timezone column |
| **API Schemas** | Dedicated Pydantic classes: `ScheduleCreate`, `ScheduleUpdate`, `ScheduleResponse` |
| **Indexing** | No extra indexes needed (small table) |
| **FK Deletion** | `ON DELETE SET NULL` — preserve SearchPerformance history |

---

## Tasks

### Phase 1: Database ✅
- [x] Add `ScheduledSearch` model to `src/database/models.py`
- [x] Add `trigger_source` column to `SearchPerformance` model
- [x] Add `schedule_id` foreign key to `SearchPerformance` model (ON DELETE SET NULL)
- [x] Run database migration (add columns to SQLite)

### Phase 2: Backend Pydantic Schemas ✅
- [x] Create `backend/schemas/scheduler.py`
- [x] Define `ScheduleCreate` schema with `run_times` validation (HH:MM format)
- [x] Define `ScheduleUpdate` schema (all fields optional)
- [x] Define `ScheduleResponse` schema

### Phase 3: Backend Scheduler Service ✅
- [x] Create `backend/services/webapp_scheduler.py`
- [x] Implement `WebAppScheduler` class with APScheduler
- [x] Configure `max_instances=1` to prevent overlapping runs
- [x] Add `load_schedules_from_db()` method (called at startup)
- [x] Add `add_schedule()` / `remove_schedule()` methods
- [x] Add `execute_scheduled_search()` method (reuses search pipeline)
- [x] Add `calculate_next_run()` helper for fixed times
- [x] Log errors on failure, update `last_run_status` to 'error'

### Phase 4: Backend API ✅
- [x] Create `backend/routers/scheduler.py`
- [x] Implement `GET /scheduler/schedules` - List all schedules
- [x] Implement `POST /scheduler/schedules` - Create new schedule
- [x] Implement `GET /scheduler/schedules/{id}` - Get schedule details
- [x] Implement `PUT /scheduler/schedules/{id}` - Update schedule
- [x] Implement `DELETE /scheduler/schedules/{id}` - Delete schedule
- [x] Implement `POST /scheduler/schedules/{id}/toggle` - Enable/disable
- [x] Implement `POST /scheduler/schedules/{id}/run-now` - Trigger immediate run
- [x] Implement `GET /scheduler/status` - Get scheduler status
- [x] Register router in `backend/main.py`
- [x] Add scheduler startup/shutdown hooks in `main.py`

### Phase 5: Search Pipeline Modification ✅
- [x] Add `trigger_source` parameter to search pipeline
- [x] Add `schedule_id` parameter to search pipeline
- [x] Record trigger source in `SearchPerformance` table
- [x] Update `PerformanceLogger` to track source

### Phase 6: Frontend API Integration ✅
- [x] Add `ScheduledSearch` TypeScript interface to `api.ts`
- [x] Add `useSchedules()` hook
- [x] Add `useCreateSchedule()` hook
- [x] Add `useUpdateSchedule()` hook
- [x] Add `useDeleteSchedule()` hook
- [x] Add `useToggleSchedule()` hook
- [x] Add `useRunScheduleNow()` hook

### Phase 7: Frontend Schedule Tab ✅
- [x] Create `frontend/src/components/schedules/ScheduleList.tsx`
- [x] Create `frontend/src/components/schedules/ScheduleForm.tsx`
- [x] Add \"Schedule\" tab to `GetJobs.tsx`
- [x] Implement schedule list with enable/disable toggles
- [x] Implement schedule form modal/sheet
- [x] Add \"Run Now\" button functionality

### Phase 8: Scheduled Run Indicators ✅
- [x] Add trigger source column to Recent Searches table (`PerformanceTab.tsx`)
- [x] Add Clock/User icons for scheduled vs manual runs
- [x] Add \"Scheduled\" badge to Job Matches page (optional)

### Phase 9: Telegram Notifications ✅ (Already implemented in webapp_scheduler.py)
- [x] Import Telegram notification code into `webapp_scheduler.py`
- [x] Format notification message with schedule name
- [x] Send notification on scheduled search completion
- [x] Include match count and top matches in notification

### Phase 10: E2E Testing ✅
- [x] Created `backend/tests/test_scheduler.py` with 14 test cases
- [x] Tests cover: CRUD operations, toggle, run-now, status, trigger_source

---

## Architecture

### Reusable Components
- **Search pipeline** (`backend/routers/search.py`) - 6-stage search execution
- **Telegram notifications** (`src/bot/telegram_bot.py`) - Push notifications for new matches
- **Config pattern** - Schedule times from config.yaml

### New Components
- **Backend scheduler service** - APScheduler running in FastAPI with `max_instances=1`
- **Schedule storage** - Database table for scheduled search configs
- **Pydantic schemas** - Request/response validation for scheduler API
- **Schedule API endpoints** - CRUD for schedules + enable/disable
- **Frontend Schedule tab** - UI for managing schedules
- **Search origin tracking** - Flag in SearchPerformance to track scheduled vs manual

---

## Database Schema

### New Table: `scheduled_searches`
```python
class ScheduledSearch(Base):
    __tablename__ = 'scheduled_searches'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)  # e.g., "Morning PM Search"
    keyword = Column(String(200), nullable=False)
    location = Column(String(200), default="Canada")
    job_type = Column(String(50), nullable=True)
    experience_level = Column(String(50), nullable=True)
    work_arrangement = Column(String(50), nullable=True)
    max_results = Column(Integer, default=25)
    resume_filename = Column(String(255), nullable=False)
    export_to_sheets = Column(Boolean, default=True)

    # Schedule config (fixed times approach)
    enabled = Column(Boolean, default=True)
    run_times = Column(JSON, default=["08:00", "12:00", "16:00", "20:00"])
    timezone = Column(String(50), default="America/Toronto")

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    last_run_status = Column(String(20), nullable=True)  # 'success' | 'error'
```

### Modify: `SearchPerformance`
```python
trigger_source = Column(String(20), default='manual')  # 'manual' | 'scheduled'
schedule_id = Column(Integer, ForeignKey('scheduled_searches.id', ondelete='SET NULL'), nullable=True)
```

---

## Pydantic Schemas

### `backend/schemas/scheduler.py`
```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
import re

class ScheduleCreate(BaseModel):
    name: str = Field(..., max_length=100)
    keyword: str = Field(..., max_length=200)
    location: str = Field(default="Canada", max_length=200)
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    work_arrangement: Optional[str] = None
    max_results: int = Field(default=25, ge=1, le=100)
    resume_filename: str
    export_to_sheets: bool = True
    enabled: bool = True
    run_times: list[str] = ["08:00", "12:00", "16:00", "20:00"]
    timezone: str = "America/Toronto"

    @field_validator('run_times')
    @classmethod
    def validate_run_times(cls, v):
        pattern = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')
        for time in v:
            if not pattern.match(time):
                raise ValueError(f"Invalid time format: {time}. Use HH:MM (24-hour)")
        return v

class ScheduleUpdate(BaseModel):
    name: Optional[str] = None
    keyword: Optional[str] = None
    location: Optional[str] = None
    # ... all fields optional

class ScheduleResponse(BaseModel):
    id: int
    name: str
    keyword: str
    enabled: bool
    run_times: list[str]
    timezone: str
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    last_run_status: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/scheduler/schedules` | List all scheduled searches |
| POST | `/scheduler/schedules` | Create new schedule |
| GET | `/scheduler/schedules/{id}` | Get schedule details |
| PUT | `/scheduler/schedules/{id}` | Update schedule |
| DELETE | `/scheduler/schedules/{id}` | Delete schedule |
| POST | `/scheduler/schedules/{id}/toggle` | Enable/disable schedule |
| POST | `/scheduler/schedules/{id}/run-now` | Trigger immediate run |
| GET | `/scheduler/status` | Get scheduler status |

---

## Files to Create

1. `backend/schemas/scheduler.py` - Pydantic schemas for scheduler API
2. `backend/services/webapp_scheduler.py` - APScheduler service
3. `backend/routers/scheduler.py` - Schedule CRUD endpoints
4. `frontend/src/components/schedules/ScheduleList.tsx`
5. `frontend/src/components/schedules/ScheduleForm.tsx`

## Files to Modify

1. `src/database/models.py` - Add `ScheduledSearch` model + modify `SearchPerformance`
2. `backend/main.py` - Register scheduler router + startup/shutdown
3. `backend/routers/search.py` - Add trigger_source tracking
4. `frontend/src/pages/GetJobs.tsx` - Add Schedule tab
5. `frontend/src/services/api.ts` - Add schedule types and API hooks
6. `frontend/src/components/analytics/PerformanceTab.tsx` - Show trigger source

---

## Telegram Notification Format

```
🔔 Scheduled Search Complete: "Senior PM"

Found 3 new high-quality matches (70%+):
1. Senior PM @ Shopify (85%)
2. Product Manager @ Stripe (78%)
3. Lead PM @ Unity (72%)

View in Job Matches: [webapp_url]
```
