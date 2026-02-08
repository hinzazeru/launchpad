# Project Review Recommendations (2026-02-06)

## Quick Understanding Of The Codebase
- Backend: FastAPI app serving API endpoints, SSE search progress, and scheduling endpoints. Runs job searches via Apify/BrightData providers and persists results in SQLite using SQLAlchemy.
- Matching: Dual-mode NLP (sentence-transformers) and Gemini LLM matching, with rich AI insights saved to the DB.
- Frontend: React + React Query + Zustand; background job search polling and analytics dashboards.
- Integrations: Apify/BrightData fetch, Google Sheets export, Telegram bot scheduling/notifications, Gemini-based analysis.

## Suggested Improvements

### Functionality
1. Application tracking endpoints + UI wiring
   - You already have `ApplicationTracking` in `src/database/models.py`, but there is no clear API/UI path to use it.
   - Add CRUD endpoints in `backend/routers/` and wire a simple UI panel for status updates (Saved/Applied/Interviewing/etc.).
   - Benefit: turns the tool into a true end-to-end job workflow, not just discovery.

2. Per-profile resume selection and rules
   - `ScheduledSearch` supports `resume_filename`, but the Telegram scheduler still uses the latest resume in `src/scheduler/job_scheduler.py`.
   - Extend scheduler profiles to include `resume_filename`, `min_score`, and `location` so each profile can be tailored.
   - Benefit: more accurate matches per profile and fewer manual config changes.

3. Source and freshness filtering in UI
   - Freshness logic exists (see config and matching), but UI search filters don’t expose it.
   - Add filters for `max_job_age_days`, `source`, and `work_arrangement` in the web UI and pass to API.
   - Benefit: tighter control over results and improved relevance.

4. Resume formats beyond txt/md
   - The system already supports PDF for job imports, but resumes are still limited.
   - Add PDF and DOCX resume parsing in `src/resume/` and expose it in `backend/routers/resumes.py`.
   - Benefit: lower friction for new users and a broader resume intake.

5. Feedback loop for matching weights
   - Add “thumbs up/down” or “not relevant” feedback per job and track it.
   - Use this feedback to tune weights or to build a lightweight learning-to-rank signal.
   - Benefit: personalization improves relevance over time.

6. Cancellation for long-running searches
   - Add an endpoint to cancel a `SearchJob` and plumb through to the frontend search state.
   - Benefit: better UX and cost control for expensive Gemini calls.

### Performance
1. Batch and/or bulk insert job postings
   - `src/importers/apify_provider.py` and `src/importers/brightdata_provider.py` query for duplicates per job, then insert one by one.
   - Improve by preloading existing keys and using `bulk_save_objects` or `INSERT OR IGNORE` with a unique constraint.
   - Benefit: large speedup on imports and reduced DB churn.

2. Add DB-level de-duplication
   - Add a unique constraint on normalized (`title`, `company`, `posting_date`) or on `url` when present in `src/database/models.py`.
   - Benefit: simpler code and fewer duplicate checks across providers.

3. Offload Gemini extraction to a background queue
   - Domain/summary/requirements extraction is done inline after import (serial per job).
   - Move Gemini extraction to a background worker (or scheduled task) and update jobs asynchronously.
   - Benefit: search completes faster and Gemini costs become easier to throttle.

4. Reuse model instances (avoid reloading embeddings)
   - `JobMatcher` and `SkillsMatcher` load `SentenceTransformer` per instantiation.
   - Promote them to app-level singletons (FastAPI lifespan or cached factory).
   - Benefit: big latency reduction and lower memory churn per request.

5. Persist embeddings on disk
   - Current embedding cache is in-memory only (`SkillsMatcher._cache`).
   - Use a simple on-disk cache (sqlite or pickle) keyed by skill text, or prebuild embeddings for the static skill dictionary.
   - Benefit: faster cold starts and stable performance after restarts.

6. Batch matching operations
   - Matching loops through jobs sequentially; embedding work per job can be batched.
   - Consider batching job skill embeddings and running cosine similarity in bulk.
   - Benefit: reduces overall matching time for large result sets.

7. Optimize API payload size for job lists
   - `Job` includes full `description` in list responses, which can be large.
   - Add a `fields` or `include_description` parameter to `backend/routers/jobs.py` and default list responses to summary-only.
   - Benefit: faster frontend loads and lower bandwidth.

8. Scheduled cleanup for `SearchJob` records
   - `SearchJob` has `expires_at` but no cleanup routine is visible.
   - Add a cleanup task to remove expired jobs and large result blobs.
   - Benefit: prevents DB bloat and keeps analytics fast.

## Highest-Impact Short List
1. Bulk insert + unique constraint for job postings.
2. Singleton `JobMatcher`/`SkillsMatcher` to avoid reloading models.
3. Async Gemini extraction after import.
4. Search cancellation endpoint.
5. Application tracking endpoints + UI.
