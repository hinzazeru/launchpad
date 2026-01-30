# Performance Analytics Implementation Plan

## Goal
Track and visualize system performance to identify bottlenecks and monitor AI/external API latency.

## Metrics to Track
1.  **Job Search Performance**:
    *   Total duration.
    *   Breakdown: Apify Fetching vs. Local DB Import vs. AI Matching.
    *   Job count vs. Duration correlation.
2.  **AI Latency**:
    *   Resume Analysis duration (Gemini).
    *   Bullet Point Rewrite duration (Gemini).
    *   Token usage (if available/relevant).
3.  **System Health**:
    *   Success/Error rates for Search and Analysis.
    *   External API failures.

## Proposed Architecture

### Database Schema
New table `performance_metrics`:
- `id`: PK
- `event_type`: string (e.g., `search_job`, `analyze_resume`, `generate_suggestions`)
- `duration_ms`: integer
- `status`: string (`success`, `error`)
- `created_at`: datetime
- `meta`: JSON (e.g., `{ "jobs_count": 50, "model": "gemini-1.5-flash" }`)

### Backend Implementation
1.  **Performance Service**: A lightweight service to log metrics to the DB asynchronously.
2.  **Instrumentation**:
    *   Decorators for functions (cleanest).
    *   Or explicit timing logic in `search_jobs` (since it's a generator, decorators are tricky).
3.  **API Endpoints**:
    *   `GET /analytics/performance`: Returns aggregated stats (avg latency, error rate) and time-series data.

## UI Design (Analytics Page)
Add a new "System Performance" tab or section:
1.  **Latency Cards**: "Avg Search Time", "Avg AI Response".
2.  **Performance Trend**: Line chart showing response times over the last 30 days.
3.  **Breakdown**: Stacked bar chart for Search steps (Fetch/Match/Export).

## Plan with "Other Examples"
The user asked for other examples. I propose adding:
*   **"Cost" Proxy**: Track number of AI calls or "credits" used (if relevant for Apify).
*   **Database Health**: Query execution times for complex match queries.

## User Review Required
> [!NOTE]
> I will instrument the `search_jobs` generator manually to capture stage-specific timings (Fetching vs Matching), as a simple decorator won't capture the internal steps of a streaming response.

## Steps
1.  Create `PerformanceMetric` model in `src/database/models.py`.
2.  Create `PerformanceLogger` service.
3.  Instrument `backend/routers/search.py` and `backend/routers/analysis.py`.
4.  Add endpoint to `backend/routers/analytics.py`.
5.  Update Frontend `Analytics` page with new charts.
