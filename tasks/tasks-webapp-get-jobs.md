# Web App: Add "Get Jobs" Feature

## Overview

Add a new "Get Jobs" page to the web app with full search parameters, real-time progress tracking via SSE, and results display.

**Status:** Complete

---

## Files Created

| File | Purpose |
|------|---------|
| `backend/routers/search.py` | New search router with SSE streaming endpoint |
| `frontend/src/pages/GetJobs.tsx` | New page with search form + progress display |

## Files to Modify

| File | Change |
|------|--------|
| `backend/main.py` | Register search router |
| `frontend/src/App.tsx` | Add `/get-jobs` route |
| `frontend/src/components/Layout.tsx` | Add "Get Jobs" nav item |
| `frontend/src/services/api.ts` | Add search types and SSE client |

---

## Task List

### Phase 1: Backend

- [x] **1.1** Create `backend/routers/search.py` with Pydantic models
  - JobSearchRequest, SearchProgress, SearchResult models
  - SearchStage enum (initializing, fetching, importing, matching, exporting, completed, error)

- [x] **1.2** Implement `GET /api/search/defaults` endpoint
  - Return search defaults from config.yaml

- [x] **1.3** Implement `POST /api/search/jobs` SSE endpoint
  - Create async generator for SSE streaming
  - Wire up StreamingResponse with proper headers

- [x] **1.4** Implement search pipeline execution
  - Stage 1: Load resume, validate inputs
  - Stage 2: Call ApifyJobImporter.search_jobs()
  - Stage 3: Import jobs to DB with Gemini domain extraction
  - Stage 4: Run JobMatcher.match_jobs() + Gemini rerank
  - Stage 5: Export to Google Sheets
  - Stage 6: Return final results

- [x] **1.5** Register search router in `backend/main.py`

- [x] **1.6** Add path validation security to search router

### Phase 2: Frontend

- [x] **2.1** Add search types to `frontend/src/services/api.ts`
  - JobSearchParams, SearchProgress, SearchResult, SearchDefaults interfaces

- [x] **2.2** Implement SSE client in `frontend/src/services/api.ts`
  - searchJobs() with fetch + ReadableStream for POST+SSE
  - getSearchDefaults()
  - useSearchDefaults() React Query hook

- [x] **2.3** Create `frontend/src/pages/GetJobs.tsx` - Search Form
  - Keyword input (required)
  - Location input with default
  - Job type select dropdown
  - Experience level select dropdown
  - Work arrangement select dropdown
  - Max results number input
  - Resume selector (from useResumes hook)
  - Export to Sheets checkbox
  - Start Search button

- [x] **2.4** Create `frontend/src/pages/GetJobs.tsx` - Progress Display
  - Vertical stepper component with 6 stages
  - Animated progress bar
  - Real-time stats display (jobs found, matches, exported)
  - Error state handling

- [x] **2.5** Create `frontend/src/pages/GetJobs.tsx` - Results Display
  - Summary stat cards
  - Top 5 matches list with links
  - "View in Google Sheets" button
  - "Search Again" button

- [x] **2.6** Update `frontend/src/components/Layout.tsx`
  - Add "Get Jobs" nav item with Search icon

- [x] **2.7** Update `frontend/src/App.tsx`
  - Import GetJobs page
  - Add Route for /get-jobs

### Phase 3: Testing & Polish

- [x] **3.1** Test SSE streaming end-to-end
- [x] **3.2** Test error handling (Apify failure, no resume, etc.)
- [x] **3.3** Test with real Apify API call
- [x] **3.4** Verify Google Sheets export works
- [x] **3.5** Enhancement: Show fetched jobs when no matches found

---

## Technical Details

### Search Parameters

| Parameter | Type | Default | Options |
|-----------|------|---------|---------|
| keyword | string | required | - |
| location | string | "United States" | - |
| job_type | string | null | Full-time, Part-time, Contract, Temporary, Internship |
| experience_level | string | null | Entry level, Mid-Senior level, Director, Executive |
| work_arrangement | string | null | Remote, Hybrid, On-site |
| max_results | int | 25 | 1-100 |
| resume_filename | string | required | - |
| export_to_sheets | bool | true | - |

### SSE Progress Stages

| Stage | Progress | What Happens |
|-------|----------|--------------|
| initializing | 0-10% | Load resume, validate inputs |
| fetching | 10-40% | Call Apify LinkedIn scraper |
| importing | 40-50% | Save jobs to DB, extract domains |
| matching | 50-80% | Run NLP matching + Gemini rerank |
| exporting | 80-95% | Export to Google Sheets |
| completed | 100% | Return results |

### Key References

- Pipeline logic: `src/scheduler/job_scheduler.py` lines 164-503
- Apify params: `src/importers/api_importer.py` lines 90-172
- Config defaults: `config.yaml` search section
- Existing page patterns: `frontend/src/pages/Dashboard.tsx`, `Library.tsx`
