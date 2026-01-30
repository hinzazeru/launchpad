# LinkedIn Job Matcher - Implementation Tasks

## Relevant Files

### Core Application Files
- `src/main.py` - Main application entry point and CLI interface
- `src/config.py` - Configuration management and loading
- `src/config.yaml` - Default configuration file with settings

### Database Layer
- `src/database/db.py` - Database connection and initialization
- `src/database/models.py` - SQLAlchemy models for resumes, jobs, matches, tracking
- `src/database/crud.py` - CRUD operations for database entities
- `src/database/test_crud.py` - Unit tests for CRUD operations

### Resume Management
- `src/resume/parser.py` - Resume parsing logic for text/markdown
- `src/resume/storage.py` - Resume storage and retrieval
- `src/resume/test_parser.py` - Unit tests for resume parser
- `src/resume/test_storage.py` - Unit tests for resume storage

### Job Import
- `src/importers/file_importer.py` - File-based job import (PDF, text, JSON/CSV)
- `src/importers/api_importer.py` - 3rd party API integration (Apify)
- `src/importers/validators.py` - Job posting validation and freshness filter
- `src/importers/test_file_importer.py` - Unit tests for file importer
- `src/importers/test_api_importer.py` - Unit tests for API importer
- `src/importers/test_validators.py` - Unit tests for validators

### Matching Engine
- `src/matching/engine.py` - Core matching algorithm (includes experience matching and scoring)
- `src/matching/skills_matcher.py` - NLP-based skill matching using sentence-transformers
- `src/matching/skill_extractor.py` - Extracts skills from job descriptions (180-skill dictionary)
- `src/matching/test_matching.py` - Unit tests for matching engine and skills matcher

### Email Notifications
- `src/notifications/email_notifier.py` - Gmail OAuth 2.0 auth, email sending, and HTML templates (combined)
- `src/notifications/test_email_notifier.py` - Unit tests for email notifier
- `docs/EMAIL_SETUP.md` - Email/Gmail OAuth setup documentation

### Scheduling
- `src/scheduler/job_scheduler.py` - Job scheduling system (APScheduler)
- `docs/SCHEDULER.md` - Scheduler setup and configuration documentation
- `src/scheduler/test_scheduler.py` - Unit tests for scheduler (TODO: not yet created)

### Application Tracking
- `src/tracking/tracker.py` - Application status tracking (TODO: not yet created)
- `src/tracking/test_tracker.py` - Unit tests for tracker (TODO: not yet created)
- Note: Database model `ApplicationTracking` exists in `src/database/models.py`


### Google Sheets Integration
- `src/integrations/sheets_connector.py` - Google Sheets OAuth and export functionality
- `src/integrations/test_sheets_connector.py` - Unit tests for Sheets connector
- `docs/SHEETS_SETUP.md` - Google Sheets setup documentation

### Telegram Bot
- `src/bot/telegram_bot.py` - Telegram bot for remote control
- `run_telegram_bot.py` - Bot runner script
- `docs/TELEGRAM_BOT.md` - Telegram bot setup and usage documentation

### Resume Targeting (Streamlit Web App)
- `src/targeting/__init__.py` - Targeting module initialization (TODO: not yet created)
- `src/targeting/role_analyzer.py` - Role alignment scoring against job descriptions (TODO: not yet created)
- `src/targeting/bullet_rewriter.py` - Gemini-powered bullet point rewriting (TODO: not yet created)
- `src/targeting/exporter.py` - Tailored resume file generation (TODO: not yet created)
- `src/web/__init__.py` - Web module initialization (TODO: not yet created)
- `src/web/app.py` - Main Streamlit application (TODO: not yet created)
- `src/web/components.py` - Reusable Streamlit UI components (TODO: not yet created)
- `run_targeter.py` - Streamlit app entry point (TODO: not yet created)
- `docs/RESUME_TARGETER.md` - Resume targeting usage documentation (TODO: not yet created)

### Supporting Files
- `requirements.txt` - Python dependencies
- `config.yaml` - Main configuration file
- `config.yaml.example` - Example configuration file
- `.env.example` - Example environment variables file
- `dataset.json` - Mock data for testing without API calls
- `run_telegram_bot.py` - Telegram bot runner script
- `README.md` - Project documentation and setup instructions (TODO: not yet created)
- `docs/user_guide.md` - User documentation (TODO: not yet created)
- `docs/developer_guide.md` - Developer documentation (TODO: not yet created)
- `tests/integration/test_e2e.py` - End-to-end integration tests (TODO: not yet created)
- `tests/fixtures/` - Test data fixtures (sample resumes, job postings)

### Notes

- Unit tests should typically be placed alongside the code files they are testing (e.g., `matching_engine.py` and `test_matching_engine.py` in the same directory).
- Use `pytest [optional/path/to/test/file]` to run tests. Running without a path executes all tests found by pytest.

## Instructions for Completing Tasks

**IMPORTANT:** As you complete each task, you must check it off in this markdown file by changing `- [ ]` to `- [x]`. This helps track progress and ensures you don't skip any steps.

Example:
- `- [ ] 1.1 Read file` → `- [x] 1.1 Read file` (after completing)

Update the file after completing each sub-task, not just after completing an entire parent task.

## Tasks

- [x] 0.0 Create feature branch
  - [x] 0.1 Create and checkout a new branch (e.g., `git checkout -b feature/linkedin-job-matcher`)

- [x] 1.0 Set up project structure and dependencies
  - [x] 1.1 Create directory structure (`src/`, `tests/`, `docs/`, subdirectories)
  - [x] 1.2 Initialize Python project with virtual environment (`python -m venv venv`)
  - [x] 1.3 Create `requirements.txt` with initial dependencies (SQLAlchemy, spaCy, sentence-transformers, APScheduler, google-auth, google-api-python-client, PyYAML, click, pytest, PyPDF2)
  - [x] 1.4 Install dependencies (`pip install -r requirements.txt`)
  - [x] 1.5 Create `.gitignore` file (exclude `venv/`, `__pycache__/`, `.env`, `*.db`)
  - [x] 1.6 Create `.env.example` file with placeholder environment variables
  - [x] 1.7 Initialize `__init__.py` files in all package directories

- [x] 2.0 Implement and test database schema and data persistence layer
  - [x] 2.1 Create `src/database/db.py` with database connection setup (SQLite/PostgreSQL)
  - [x] 2.2 Create `src/database/models.py` with SQLAlchemy models:
    - [x] 2.2.1 Resume model (id, skills, experience_years, job_titles, education, created_at, updated_at)
    - [x] 2.2.2 JobPosting model (id, title, company, description, required_skills, experience_required, posting_date, import_date, source, url, location)
    - [x] 2.2.3 MatchResult model (id, job_id, resume_id, match_score, matching_skills, experience_alignment, generated_date)
    - [x] 2.2.4 ApplicationTracking model (id, job_id, status, status_date, notes)
  - [x] 2.3 Create `src/database/crud.py` with CRUD operations for each model
  - [x] 2.4 Create `src/database/test_crud.py` with unit tests for CRUD operations
  - [x] 2.5 Run tests and verify database operations work correctly (`pytest src/database/test_crud.py`)

- [x] 3.0 Implement and test resume parsing and storage module
  - [x] 3.1 Create `src/resume/parser.py` with resume parsing logic:
    - [x] 3.1.1 Implement function to read text/markdown files
    - [x] 3.1.2 Implement skill extraction using NLP (spaCy)
    - [x] 3.1.3 Implement experience years extraction (regex patterns)
    - [x] 3.1.4 Implement job titles extraction
    - [x] 3.1.5 Implement education extraction
  - [x] 3.2 Create `src/resume/storage.py` with resume storage operations
  - [x] 3.3 Create `src/resume/test_parser.py` with unit tests for parser
  - [x] 3.4 Create `tests/fixtures/sample_resume.txt` with test resume data
  - [x] 3.5 Create `src/resume/test_storage.py` with unit tests for storage
  - [x] 3.6 Run tests and verify resume parsing works correctly (`pytest src/resume/`)

- [x] 4.0 Implement and test job posting import system (file-based)
  - [x] 4.1 Create `src/importers/file_importer.py` with file import logic:
    - [x] 4.1.1 Implement PDF file parser (using PyPDF2)
    - [x] 4.1.2 Implement text/markdown file parser
    - [x] 4.1.3 Implement JSON parser
    - [x] 4.1.4 Implement CSV parser
    - [x] 4.1.5 Implement job data extraction (title, company, skills, experience, posting_date, etc.)
  - [x] 4.2 Create `src/importers/validators.py` with validation logic:
    - [x] 4.2.1 Implement 24-hour freshness filter
    - [x] 4.2.2 Implement required fields validation
  - [x] 4.3 Create `src/importers/test_file_importer.py` with unit tests
  - [x] 4.4 Create `src/importers/test_validators.py` with unit tests
  - [x] 4.5 Create `tests/fixtures/sample_jobs.json` and `sample_jobs.csv` with test data
  - [x] 4.6 Run tests and verify file import works correctly (`pytest src/importers/`)

- [x] 5.0 Implement and test 3rd party API integration for job fetching
  - [x] 5.1 Research Apify LinkedIn Job Scraper API documentation
  - [x] 5.2 Create `src/importers/api_importer.py` with API integration:
    - [x] 5.2.1 Implement Apify API client initialization
    - [x] 5.2.2 Implement job search function with configurable parameters (keywords, location, job_type)
    - [x] 5.2.3 Implement rate limiting logic
    - [x] 5.2.4 Implement error handling and retry logic
    - [x] 5.2.5 Implement job data normalization from API response to standard format
  - [x] 5.3 Create `src/importers/test_api_importer.py` with unit tests (mock API calls)
  - [x] 5.4 Run tests and verify API integration works correctly (`pytest src/importers/test_api_importer.py`)

- [x] 6.0 Implement and test NLP-based matching engine with PM skills dictionary
  - [ ] 6.1 Create `src/matching/pm_skills.yaml` with Product Management skills dictionary:
    - [ ] 6.1.1 Add PM-specific skills (roadmapping, stakeholder management, A/B testing, PRD writing, OKRs, user stories, backlog management, etc.)
    - [ ] 6.1.2 Add skill synonyms and related terms
  - [x] 6.2 Create `src/matching/skills_matcher.py` with NLP-based skill matching (Note: implemented as skills_matcher.py instead of nlp_matcher.py):
    - [x] 6.2.1 Load PM skills dictionary
    - [x] 6.2.2 Implement semantic similarity matching using sentence-transformers
    - [x] 6.2.3 Implement PM skills boosting logic
    - [x] 6.2.4 Calculate skill match score (0-100)
  - [x] 6.3 Experience matching implemented in `src/matching/engine.py` (Note: combined into engine.py instead of separate file):
    - [x] 6.3.1 Implement years of experience comparison
    - [x] 6.3.2 Implement job title seniority matching
    - [x] 6.3.3 Calculate experience match score (0-100)
  - [x] 6.4 Weighted scoring implemented in `src/matching/engine.py` (Note: combined into engine.py instead of separate scorer.py):
    - [x] 6.4.1 Implement configurable weight system (skills vs. experience)
    - [x] 6.4.2 Implement final match score calculation
    - [x] 6.4.3 Implement matching criteria highlighting
  - [x] 6.5 Create `src/matching/engine.py` to orchestrate matching process
  - [x] 6.6 Create `src/matching/test_matching.py` with unit tests (Note: combined tests instead of separate files)
  - [x] 6.7 Tests included in test_matching.py
  - [x] 6.8 Tests included in test_matching.py
  - [x] 6.9 Run tests and verify matching engine works correctly (`pytest src/matching/`)

- [x] 7.0 Implement and test Gmail OAuth 2.0 authentication and email notifications
  - [x] 7.1 Set up Google Cloud Project and enable Gmail API (documented in docs/EMAIL_SETUP.md)
  - [x] 7.2 Create OAuth 2.0 credentials (Client ID and Client Secret)
  - [x] 7.3 OAuth 2.0 authentication implemented in `src/notifications/email_notifier.py` (Note: combined into single file instead of separate auth.py):
    - [x] 7.3.1 Implement OAuth flow for first-time authentication
    - [x] 7.3.2 Implement token storage and refresh logic
    - [x] 7.3.3 Implement credentials validation
  - [x] 7.4 HTML email templates implemented in `src/notifications/email_notifier.py` (Note: combined into single file instead of separate templates.py):
    - [x] 7.4.1 Create email header with subject line
    - [x] 7.4.2 Create job card layout (title, company, match score, matching skills, experience alignment)
    - [x] 7.4.3 Create "View Job" button/link
    - [x] 7.4.4 Add mobile-responsive CSS
  - [x] 7.5 Email sending implemented in `src/notifications/email_notifier.py` (Note: combined into single file instead of separate sender.py):
    - [x] 7.5.1 Implement Gmail API send message function
    - [x] 7.5.2 Implement top-matched jobs filtering (configurable threshold)
    - [x] 7.5.3 Implement immediate send (no batching)
  - [x] 7.6 Create `src/notifications/test_email_notifier.py` with unit tests (Note: combined tests)
  - [x] 7.7 Tests included in test_email_notifier.py
  - [x] 7.8 Run tests and verify email functionality works correctly (`pytest src/notifications/`)

- [x] 8.0 Implement and test job scheduling system (on-demand and automated)
  - [x] 8.1 Duplicate detection implemented via database unique constraints (Note: no separate duplicate_detector.py, handled in api_importer.py):
    - [x] 8.1.1 Implement job title + company name normalization (lowercase, trim)
    - [x] 8.1.2 Implement duplicate checking against database
  - [x] 8.2 Create `src/scheduler/job_scheduler.py` with scheduling logic (Note: named job_scheduler.py instead of scheduler.py):
    - [x] 8.2.1 Implement on-demand search trigger function (run_now())
    - [x] 8.2.2 Implement APScheduler setup for automated searches
    - [x] 8.2.3 Implement configurable schedule intervals (daily, weekly, custom)
    - [x] 8.2.4 Implement enable/disable scheduled searches
    - [x] 8.2.5 Integrate duplicate detection in scheduled runs
  - [x] 8.3 Duplicate detection tested as part of importer tests
  - [ ] 8.4 Create `src/scheduler/test_scheduler.py` with unit tests
  - [ ] 8.5 Run tests and verify scheduling works correctly (`pytest src/scheduler/`)

- [ ] ~~9.0 Implement and test application tracking functionality~~ (Deprioritized - not needed for current workflow)
  - Note: Database model exists in `src/database/models.py` if needed later

- [x] 10.0 Create and test configuration management system
  - [x] 10.1 Create `config.yaml` with default configuration (Note: in project root, not src/):
    - [x] 10.1.1 Add email settings (Gmail address)
    - [x] 10.1.2 Add notification preferences (min_score, max_jobs_per_email)
    - [x] 10.1.3 Add schedule settings (enabled, interval)
    - [x] 10.1.4 Add matching thresholds and weights (skills: 50%, experience: 50%)
    - [x] 10.1.5 Add database settings (path, type)
    - [x] 10.1.6 Add API settings (service, credentials_path)
    - [x] 10.1.7 Add comments explaining each setting
  - [x] 10.2 Create `src/config.py` with configuration loader:
    - [x] 10.2.1 Implement YAML file loading
    - [x] 10.2.2 Implement configuration validation
    - [x] 10.2.3 Implement environment variable override support
    - [x] 10.2.4 Implement default value fallbacks
  - [x] 10.3 Create `src/test_config.py` with unit tests
  - [x] 10.4 Run tests and verify configuration loading works correctly (`pytest src/test_config.py`)

- [ ] 11.0 End-to-end integration testing and documentation
  - [ ] 11.1 Create `tests/integration/test_e2e.py` with end-to-end test scenarios:
    - [ ] 11.1.1 Test full workflow: upload resume → import jobs → match → send email
    - [ ] 11.1.2 Test scheduled search workflow
    - [ ] 11.1.3 Test duplicate detection across multiple imports
    - [ ] 11.1.4 Test application tracking workflow
  - [ ] 11.2 Run integration tests and fix any issues (`pytest tests/integration/`)
  - [ ] 11.3 Create `README.md` with:
    - [ ] 11.3.1 Project overview and features
    - [ ] 11.3.2 Installation instructions
    - [ ] 11.3.3 Configuration setup guide
    - [ ] 11.3.4 Gmail OAuth setup instructions
    - [ ] 11.3.5 Usage examples for Telegram bot commands
    - [ ] 11.3.6 Troubleshooting section
  - [ ] 11.4 Create `docs/user_guide.md` with detailed user documentation
  - [ ] 11.5 Create `docs/developer_guide.md` with architecture and development documentation
  - [ ] 11.6 Review all documentation for accuracy and completeness

- [x] 13.0 Enhancements and Bug Fixes (Post-MVP)
  - [x] 13.1 Implement mock data mode for testing without API costs:
    - [x] 13.1.1 Add `apify.use_mock_data` and `apify.mock_data_file` configuration options
    - [x] 13.1.2 Implement `_load_mock_data()` method in `ApifyJobImporter` to load jobs from local JSON file
    - [x] 13.1.3 Update `search_jobs()` to return mock data when enabled
    - [x] 13.1.4 Skip freshness validation and duplicate checking in mock mode
    - [x] 13.1.5 Add `[MOCK MODE]` logging to indicate when mock data is being used
  - [x] 13.2 Implement complete job logging to Google Sheets:
    - [x] 13.2.1 Create `log_all_jobs_to_sheets()` method in `SheetsConnector`
    - [x] 13.2.2 Export ALL jobs (not just high matches) to "Logs" sheet with 16 detailed columns
    - [x] 13.2.3 Include Timestamp, Match Scores, Skills Analysis, Job Metadata, and Description Preview
    - [x] 13.2.4 Integrate logging into `JobScheduler.run_now()` to auto-log after each search
  - [x] 13.3 Enhance Telegram bot success messages:
    - [x] 13.3.1 Update `/search` command to query recent match results (last 5 minutes)
    - [x] 13.3.2 Count total jobs analyzed and high-quality matches (≥70%)
    - [x] 13.3.3 Display top 5 matches with emoji indicators (🔥 ≥85%, ✨ ≥75%, ⭐ ≥70%)
    - [x] 13.3.4 Add clickable Google Sheets link using Markdown format
    - [x] 13.3.5 Show job title, company, and match score for each top match
  - [x] 13.4 Enhance match result data completeness:
    - [x] 13.4.1 Add `posting_date` field to match result dictionary in `JobMatcher.match_jobs()`
    - [x] 13.4.2 Add `description` field to match result dictionary
    - [x] 13.4.3 Add `experience_required` field to match result dictionary
    - [x] 13.4.4 Ensure all fields are properly populated for Google Sheets export
  - [x] 13.5 Fix critical bugs in job scheduler:
    - [x] 13.5.1 Fix resume query removing non-existent `is_active` field, query by `created_at` instead
    - [x] 13.5.2 Move scheduler component initialization before `if not self.enabled` check
    - [x] 13.5.3 Add null value handling for `search_location` and `max_results` config values
    - [x] 13.5.4 Fix module import error changing `validation` to `validators`
    - [x] 13.5.5 Fix method name from `match_all_jobs()` to `match_jobs()`
    - [x] 13.5.6 Remove non-existent `auto_send` attribute check from EmailNotifier
  - [x] 13.6 Update project documentation:
    - [x] 13.6.1 Update PRD with new Google Sheets logging requirements (7.9-7.11)
    - [x] 13.6.2 Update PRD with enhanced Telegram bot message requirements (8.5-8.6)
    - [x] 13.6.3 Add mock data mode design decision to PRD (Design Decision #11)
    - [x] 13.6.4 Add complete job logging design decision to PRD (Design Decision #12)
    - [x] 13.6.5 Update tasks file with completed enhancements and bug fixes

- [x] 14.0 Implement Matching Engine Versioning System
  - [x] 14.1 Add version configuration to matching engine:
    - [x] 14.1.1 Add `matching.engine_version` field to `config.yaml` (set to "1.0.0" as baseline)
    - [x] 14.1.2 Add `Config.get_engine_version()` method to retrieve engine version
    - [x] 14.1.3 Add version validation to ensure semantic versioning format (v{major}.{minor}.{patch})
  - [x] 14.2 Update JobMatcher to track engine version:
    - [x] 14.2.1 Read engine version from config in `JobMatcher.__init__()`
    - [x] 14.2.2 Add `engine_version` field to match result dictionary in `match_job()` method
    - [x] 14.2.3 Include engine version in all match results returned by `match_jobs()` method
  - [x] 14.3 Update database models to store engine version:
    - [x] 14.3.1 Add `engine_version` column to `MatchResult` model (String, nullable for backwards compatibility)
    - [x] 14.3.2 Create database migration script to add the column to existing databases
    - [x] 14.3.3 Update `create_match_result()` in CRUD operations to accept and store engine_version
  - [ ] 14.4 Update Google Sheets export to include engine version:
    - [ ] 14.4.1 Add "Engine Version" as the 17th column in Logs sheet header
    - [ ] 14.4.2 Update `log_all_jobs_to_sheets()` method to extract engine_version from match results
    - [ ] 14.4.3 Ensure engine version is written to the Logs sheet for all job entries
    - [ ] 14.4.4 Update `export_matches_batch()` to include engine version in high-match exports (optional)
  - [ ] 14.5 Add engine version tracking documentation:
    - [ ] 14.5.1 Create `docs/MATCHING_ENGINE_VERSIONS.md` with version history and changelog
    - [ ] 14.5.2 Document v1.0.0 baseline implementation (50/50 weights, step-based experience scoring)
    - [ ] 14.5.3 Add instructions for updating version when making algorithm changes
    - [ ] 14.5.4 Document semantic versioning scheme (major/minor/patch guidelines)
  - [ ] 14.6 Test engine version tracking:
    - [ ] 14.6.1 Run a test search and verify engine version appears in database
    - [ ] 14.6.2 Verify engine version appears in Google Sheets Logs
    - [ ] 14.6.3 Test with different version numbers to ensure tracking works correctly

- [x] 15.0 Fix Telegram Bot Job Count and Add LinkedIn Links
  - [x] 15.1 Fix "Total jobs analyzed: 0" issue in Telegram bot:
    - [x] 15.1.1 Identify root cause: scheduler was not saving MatchResult records to database
    - [x] 15.1.2 Update `job_scheduler.py` to call `matcher.save_match_results()` after matching
    - [x] 15.1.3 Add database commit after saving match results
    - [x] 15.1.4 Add logging for match result save operations
  - [x] 15.2 Fix match score format mismatch:
    - [x] 15.2.1 Identify bug: scores stored as 0-1 but Telegram bot expected 0-100
    - [x] 15.2.2 Update `save_match_results()` in `engine.py` to convert scores to 0-100 format
    - [x] 15.2.3 Ensure compatibility with existing Telegram bot score comparisons (≥70, ≥75, ≥85)
  - [x] 15.3 Add LinkedIn job links to Telegram bot output:
    - [x] 15.3.1 Update `/search` command to include clickable LinkedIn URLs for top 5 matches
    - [x] 15.3.2 Use Markdown link format: `[Job Title](linkedin_url)`
    - [x] 15.3.3 Handle cases where job URL may be missing (fallback to plain text title)

- [x] 16.0 Implement Google Sheets Cleanup Feature
  - [x] 16.1 Add `cleanup_old_matches()` method to SheetsConnector:
    - [x] 16.1.1 Read date column from "Job Matches" sheet
    - [x] 16.1.2 Identify rows older than specified days (default: 7)
    - [x] 16.1.3 Delete old rows using batch delete (bottom-to-top to avoid index shift)
    - [x] 16.1.4 Return cleanup results (deleted count, remaining count, success status)
  - [x] 16.2 Add auto-cleanup during `/search` command:
    - [x] 16.2.1 Call `cleanup_old_matches()` before exporting new matches in `job_scheduler.py`
    - [x] 16.2.2 Log cleanup results (deleted count or "no old entries")
    - [x] 16.2.3 Continue with export even if cleanup fails (non-blocking)
  - [x] 16.3 Add manual `/cleanup` command to Telegram bot:
    - [x] 16.3.1 Register `/cleanup` command handler
    - [x] 16.3.2 Implement `cleanup_command()` method
    - [x] 16.3.3 Display cleanup results (deleted/remaining counts)
    - [x] 16.3.4 Update `/help` command to include `/cleanup`

- [x] 17.0 Implement Automated Job Search with Push Notifications
  - [x] 17.1 Update configuration for scheduled searches:
    - [x] 17.1.1 Add `scheduling.end_time` for time window (default: 22:00)
    - [x] 17.1.2 Update `scheduling.start_time` default to 08:00
    - [x] 17.1.3 Update `scheduling.interval_hours` default to 4
    - [x] 17.1.4 Add `scheduling.notify_on_new_matches` setting
    - [x] 17.1.5 Add `scheduling.only_notify_new` setting
  - [x] 17.2 Add notification tracking to database:
    - [x] 17.2.1 Add `notified_at` column to `MatchResult` model
    - [x] 17.2.2 Add `get_unnotified_matches()` CRUD function
    - [x] 17.2.3 Add `mark_matches_as_notified()` CRUD function
  - [x] 17.3 Update job scheduler with time window and notifications:
    - [x] 17.3.1 Parse `start_time` and `end_time` for schedule window
    - [x] 17.3.2 Schedule searches at specific hours within window (e.g., 08:00, 12:00, 16:00, 20:00)
    - [x] 17.3.3 Add `_send_telegram_notification()` method for push notifications
    - [x] 17.3.4 Add `set_telegram_callback()` method for bot integration
    - [x] 17.3.5 Add `update_schedule()` method for dynamic schedule changes
    - [x] 17.3.6 Add `get_scheduled_times()` helper method
    - [x] 17.3.7 Only notify about NEW matches (not previously notified)
  - [x] 17.4 Add `/schedule` command to Telegram bot:
    - [x] 17.4.1 `/schedule` - View current schedule status
    - [x] 17.4.2 `/schedule on` - Enable automated searches
    - [x] 17.4.3 `/schedule off` - Disable automated searches
    - [x] 17.4.4 `/schedule <hours>` - Set interval (e.g., `/schedule 4`)
    - [x] 17.4.5 `/schedule HH:MM-HH:MM` - Set time window (e.g., `/schedule 08:00-22:00`)
  - [x] 17.5 Add push notification support:
    - [x] 17.5.1 Register notification callback with scheduler
    - [x] 17.5.2 Implement `_send_push_notification()` method in bot
    - [x] 17.5.3 Format notification with top 5 new matches and LinkedIn links
  - [x] 17.6 Add config persistence:
    - [x] 17.6.1 Add `Config.set()` method for updating config values
    - [x] 17.6.2 Add `Config.save()` method for persisting changes to YAML

- [x] 18.0 Implement Keyword Profiles for Flexible Search Configuration
  - [x] 18.1 Update config.yaml with profile structure:
    - [x] 18.1.1 Add `scheduling.active_profile` setting
    - [x] 18.1.2 Add `scheduling.profiles` dict with named profiles
    - [x] 18.1.3 Create default, local, and remote profile examples
  - [x] 18.2 Update JobScheduler for profile support:
    - [x] 18.2.1 Add `_get_profile_keywords()` method
    - [x] 18.2.2 Add `get_profiles()` method
    - [x] 18.2.3 Add `set_active_profile()` method
    - [x] 18.2.4 Add `create_profile()` method
    - [x] 18.2.5 Add `delete_profile()` method
    - [x] 18.2.6 Update `get_status()` to include profile info
  - [x] 18.3 Add Telegram bot commands:
    - [x] 18.3.1 `/profiles` - List all profiles with keywords
    - [x] 18.3.2 `/profile <name>` - Switch to profile
    - [x] 18.3.3 `/profile create <name> <keywords>` - Create profile
    - [x] 18.3.4 `/profile delete <name>` - Delete profile
    - [x] 18.3.5 Update `/help` with profile commands

## Next Up: Quick Wins

- [ ] 19.0 Telegram Bot Quick Wins (Low Effort, High Value)
  - [x] 19.1 Add `/mute` command to pause notifications:
    - [x] 19.1.1 Add `scheduling.muted` config option
    - [x] 19.1.2 Implement `/mute` toggle command in Telegram bot
    - [x] 19.1.3 Skip push notifications when muted (scheduler still runs)
    - [x] 19.1.4 Show mute status in `/status` command
  - [ ] 19.2 Add minimum score threshold to `/search` command:
    - [ ] 19.2.1 Parse `--min-score` or `-m` argument from `/search` command
    - [ ] 19.2.2 Pass threshold to scheduler/matcher
    - [ ] 19.2.3 Update `/help` with new syntax: `/search [keywords] --min-score 80`
  - [x] 19.3 Add job freshness indicator to match output:
    - [x] 19.3.1 Calculate days since posting for each job
    - [x] 19.3.2 Add "stale" indicator (⏰) for jobs posted >2 days ago, fresh indicator (🕐) for ≤2 days
    - [x] 19.3.3 Show posting age in Telegram match output (e.g., "Posted 1d ago")
    - **Done:** Added `format_job_freshness()` helper in `telegram_bot.py` and `_format_job_freshness()` method in `job_scheduler.py`. Updated both `/matches` command and push notifications to show freshness.
  - [ ] 19.4 Add `/skills` command to show current resume skills:
    - [ ] 19.4.1 Query latest resume from database
    - [ ] 19.4.2 Display skills grouped or as comma-separated list
    - [ ] 19.4.3 Show experience years and other resume metadata
  - [ ] 19.5 Add daily summary option:
    - [ ] 19.5.1 Add `scheduling.daily_summary` config option
    - [ ] 19.5.2 Add `scheduling.summary_time` config option (default: 20:00)
    - [ ] 19.5.3 Implement daily summary job that aggregates all matches from the day
    - [ ] 19.5.4 Send single consolidated notification at end of day
  - [x] 19.6 Add salary extraction from job descriptions:
    - [x] 19.6.1 Add `salary` column to JobPosting model in `models.py`
    - [x] 19.6.2 Create `extract_salary_from_description()` function in `skill_extractor.py`
    - [x] 19.6.3 Integrate salary extraction in `api_importer.py` during job normalization
    - [x] 19.6.4 Update CRUD and database schema with salary field
    - [x] 19.6.5 Display salary in `/matches` command output (💰 emoji)
    - [x] 19.6.6 Display salary in push notification messages
    - [x] 19.6.7 Backfill existing jobs with extracted salary data
    - **Done:** Added regex-based salary extraction supporting $120K-$150K, $120,000-$150,000, CAD formats. Validates salary range (40K-500K) to filter false positives. 22% of existing jobs now have salary data.

## Coming Up: Improvements

- [ ] 20.0 Create PM Skills Dictionary for Enhanced Matching
  - [ ] 20.1 Create `src/matching/pm_skills.yaml` with structured PM skills:
    - [ ] 20.1.1 Define skill categories (Strategy, Technical, Analytics, Agile, Leadership)
    - [ ] 20.1.2 Add skill synonyms (e.g., "PRD" = "Product Requirements Document")
    - [ ] 20.1.3 Add related terms for NLP boosting
    - [ ] 20.1.4 Add skill importance weights by category
  - [ ] 20.2 Update SkillsMatcher to use PM dictionary:
    - [ ] 20.2.1 Load PM skills dictionary on initialization
    - [ ] 20.2.2 Implement synonym expansion for skill matching
    - [ ] 20.2.3 Apply category-based boosting for PM-specific terms
  - [ ] 20.3 Test PM skills matching:
    - [ ] 20.3.1 Add test cases for PM skill synonyms
    - [ ] 20.3.2 Verify PM skills boost match scores appropriately

- [ ] 21.0 Add Match Analytics via Telegram
  - [ ] 21.1 Implement `/analytics` command:
    - [ ] 21.1.1 Calculate average match score over configurable period (7/30 days)
    - [ ] 21.1.2 Identify top 5 most common skill gaps across all jobs
    - [ ] 21.1.3 Show match score distribution (how many 70-80%, 80-90%, 90%+)
    - [ ] 21.1.4 Display total jobs analyzed and high-match percentage
  - [ ] 21.2 Add skill gap insights:
    - [ ] 21.2.1 Track which skills appear most in job requirements
    - [ ] 21.2.2 Compare against resume skills to identify learning opportunities
    - [ ] 21.2.3 Show trending skills (appearing more frequently recently)

- [ ] 22.0 Add Scheduler Unit Tests
  - [ ] 22.1 Create `src/scheduler/test_scheduler.py`:
    - [ ] 22.1.1 Test schedule time window parsing
    - [ ] 22.1.2 Test scheduled hours calculation
    - [ ] 22.1.3 Test `update_schedule()` method
    - [ ] 22.1.4 Test notification callback registration
  - [ ] 22.2 Run tests and verify coverage (`pytest src/scheduler/`)

- [x] 23.0 Scheduler Bug Fixes
  - [x] 23.1 Fix scheduler not firing scheduled jobs:
    - [x] 23.1.1 Identify issue: BackgroundScheduler has thread contention with async Telegram bot
    - [x] 23.1.2 Change from BackgroundScheduler to AsyncIOScheduler (still didn't work)
    - [x] 23.1.3 Try python-telegram-bot's JobQueue with Defaults timezone (worked when Mac awake)
    - [x] 23.1.4 Root cause: Mac sleep suspends Python process, causing missed jobs
    - [x] 23.1.5 Final fix: Use macOS launchd for scheduling (can wake Mac from sleep)
  - [x] 23.2 Implement launchd scheduler:
    - [x] 23.2.1 Create `scripts/run_scheduled_search.sh` - job execution script
    - [x] 23.2.2 Create `scripts/com.linkedinjobmatcher.search.plist` - launchd config
    - [x] 23.2.3 Schedule: 08:00, 12:00, 16:00, 20:00 daily
    - [x] 23.2.4 Auto-sleep only if display is off (respects active user)
    - [x] 23.2.5 Install to ~/Library/LaunchAgents/
  - [x] 23.3 Update documentation:
    - [x] 23.3.1 Create `docs/LAUNCHD_SCHEDULER.md` with setup, rollback, and troubleshooting
    - [x] 23.3.2 Update `docs/SCHEDULER.md` with JobQueue and timezone info
    - [x] 23.3.3 Update `docs/ARCHITECTURE.md` with technical implementation details

- [x] 23.5 Database Performance Optimization
  - [x] 23.5.1 Add composite index `ix_job_postings_title_company` to JobPosting model
  - [x] 23.5.2 Apply index to existing SQLite database
  - [x] 23.5.3 Verify query plan uses index for duplicate checking

- [x] 23.6 Skill Matching Refinement
  - [x] 23.6.1 Identify root cause: LinkedIn API returns generic industry tags, not actual skills
  - [x] 23.6.2 Create `src/matching/skill_extractor.py`:
    - [x] 180-skill dictionary across 7 categories (PM, Technical, Methodologies, etc.)
    - [x] Regex-based extraction from job description text
    - [x] Falls back to LinkedIn tags if description is empty
  - [x] 23.6.3 Integrate skill extractor into `src/matching/engine.py`
  - [x] 23.6.4 Update resume with 32 additional PM skills (19 → 51 total)
  - [x] 23.6.5 Results: skill scores improved from ~50% to 60-85% with accurate gaps
  - [x] 23.6.6 Update `docs/ARCHITECTURE.md` with skill extraction documentation

- [ ] 24.0 Documentation
  - [ ] 24.1 Create `README.md` with:
    - [ ] 24.1.1 Project overview and features
    - [ ] 24.1.2 Installation instructions
    - [ ] 24.1.3 Configuration setup guide
    - [ ] 24.1.4 Telegram bot commands reference
  - [ ] 24.2 Additional docs:
    - [ ] 24.2.1 Review and update `docs/SHEETS_SETUP.md`

---

## Improvement Options

Based on code review report (`Review/output_review_report.md`) dated January 2, 2026.
These improvements enhance reliability, performance, and maintainability.

### Immediate (Quick Wins)

- [x] 25.0 Error Handling & Logging Improvements
  - [x] 25.1 Add try/except to `scheduled_job_callback` in `src/bot/telegram_bot.py`:
    - **Why:** Currently no error handling around `bot.scheduler.run_scheduled_search()`. If it raises an exception, the scheduled job fails silently.
    - **Location:** `src/bot/telegram_bot.py` line ~96
    - **Fix:** Wrap in try/except, log errors with `logger.error(msg, exc_info=True)`
    - **Done:** Added try/except with error logging and Telegram notification on failure
  - [x] 25.2 Replace `print()` with `logger.error()` in `Config.save()`:
    - **Why:** Inconsistent error reporting; print() may not be captured in logs
    - **Location:** `src/config.py` line ~217
    - **Fix:** Change `print(f"Error saving config: {e}")` to `logger.error(f"Error saving config: {e}", exc_info=True)`
    - **Done:** Added logging import and replaced print() with logger.error()
  - [x] 25.3 Remove unused `nltk` dependency:
    - **Why:** Listed in requirements.txt but never imported/used. Project uses spacy and sentence-transformers for NLP.
    - **Location:** `requirements.txt`
    - **Fix:** Remove `nltk==3.8.1` line
    - **Done:** Removed from requirements.txt

### Short-term (This Week)

- [x] 26.0 Database Query Optimization
  - [x] 26.1 Fix inefficient `get_job_by_title_company` query:
    - **Why:** Currently loads ALL jobs into memory then iterates in Python to find match. Very slow with large datasets.
    - **Location:** `src/database/crud.py` lines 201-224
    - **Fix:** Replace manual iteration with SQLAlchemy query using `func.lower()` and `func.trim()`:
      ```python
      from sqlalchemy import func
      return db.query(JobPosting).filter(
          func.lower(func.trim(JobPosting.title)) == normalized_title,
          func.lower(func.trim(JobPosting.company)) == normalized_company
      ).first()
      ```
    - **Done:** Implemented SQL-level case-insensitive comparison with whitespace normalization. Moved `func` import to module level for reuse. All 20 tests pass.

- [x] 27.0 Granular Exception Handling in Job Search Pipeline
  - [x] 27.1 Break up large try/except block in `run_scheduled_search`:
    - **Why:** Single broad try/except catches all errors but prevents specific recovery. When bot hung during Sheets export, it was hard to diagnose.
    - **Location:** `src/scheduler/job_scheduler.py` lines 298-541
    - **Fix:** Separate try/except blocks for:
      - Stage 1: Resume fetch (critical - abort if fails)
      - Stage 2: Apify job fetching (critical - abort if fails)
      - Stage 3: Database import (continue with warning if fails)
      - Stage 4: Job matching (continue with warning if fails, includes rollback on save failure)
      - Stage 5: Google Sheets export (non-critical - continue if fails)
      - Stage 6: Telegram notifications (non-critical - continue if fails)
    - Each stage logs `[Stage N/6]` prefix with SUCCESS/FAILED/SKIPPED/WARNING status
    - **Done:** Refactored with 6 clearly-labeled stages, granular error handling, and graceful degradation for non-critical operations

- [x] 27.5 Location-Aware Job Matching
  - [x] 27.5.1 Add location filter to Stage 4 matching query:
    - **Why:** Jobs from other regions (e.g., US jobs when searching Canada) were appearing in results because matching ran against all jobs in database regardless of location
    - **Location:** `src/scheduler/job_scheduler.py` Stage 4
    - **Fix:** Filter jobs by `JobPosting.location.ilike(f"%{location_filter}%")` for regular searches
    - **Remote handling:** Skip location filter for remote searches (keywords ending in "Remote") since remote jobs can be listed from any location
    - **Done:** Implemented location-aware filtering; US jobs (Phoenix, NY, Ohio) now excluded from Canada searches

- [x] 27.6 Job Freshness Filter
  - [x] 27.6.1 Add configurable freshness filter to focus on recent listings:
    - **Why:** Month-old job postings are stale and useless; tool should focus on new listings
    - **Config:** Added `matching.max_job_age_days` (default: 7) to `config.yaml`
    - **Location:** `src/scheduler/job_scheduler.py` Stage 4
    - **Fix:** Filter jobs where `posting_date >= cutoff_date` OR (`posting_date IS NULL` AND `import_date >= cutoff_date`)
    - **Done:** Reduced matched jobs from 50 to 11 by excluding jobs older than 7 days

### Medium-term (When Needed)

- [ ] 28.0 Async Improvements for Non-Blocking Operations
  - [ ] 28.1 Wrap Google Sheets operations in `run_in_executor()`:
    - **Why:** Sheets API calls block the main thread. We experienced the bot hanging during Sheets cleanup (fixed with TOKENIZERS_PARALLELISM but could still be slow).
    - **Location:** `src/scheduler/job_scheduler.py` where `self.sheets_connector` methods are called
    - **Fix:** Use `asyncio.get_event_loop().run_in_executor(None, blocking_func)` for Sheets calls
    - **Note:** Full async refactoring is overkill for this project, but Sheets export is a good candidate
  - [ ] 28.2 Improve `_send_push_notification` async pattern:
    - **Why:** Current implementation uses problematic `asyncio.run()` fallback that can conflict with running event loops
    - **Location:** `src/bot/telegram_bot.py` lines 923-930
    - **Fix:** Ensure consistently uses `asyncio.create_task()` or proper await pattern

- [ ] 29.0 Test Coverage Improvements
  - [ ] 29.1 Add test for `crud.get_unnotified_matches`:
    - **Why:** Complex SQL logic with subqueries, currently untested
    - **Location:** `src/database/test_crud.py`
    - **Test cases:**
      - No unnotified matches exist
      - Some unnotified matches above score threshold
      - Some below threshold (should be excluded)
      - Jobs already notified (should be excluded)

- [ ] 30.0 Dependency Management
  - [ ] 30.1 Separate development dependencies into `requirements-dev.txt`:
    - **Why:** pytest, black, flake8, etc. shouldn't be in production deployments
    - **Move to requirements-dev.txt:**
      - pytest==7.4.3
      - pytest-mock==3.12.0
      - pytest-cov==4.1.0
      - black==23.12.1
      - flake8==6.1.0
  - [ ] 30.2 Add explicit database rollbacks in transactional operations:
    - **Why:** Partial data corruption possible if error occurs mid-transaction
    - **Location:** `src/scheduler/job_scheduler.py` in `run_scheduled_search`, multi-step CRUD operations
    - **Fix:** Add `db.rollback()` in except blocks for multi-step database writes

- [x] 31.0 Domain Expertise Matching
  - **Why:** Current matching catches PM skills but misses domain-specific requirements (e.g., "ecommerce", "headless CMS", "fintech"). A 99% match may require expertise the candidate doesn't have.
  - **Example:** Orium role requires "expertise in ecommerce, headless CMS, composable architecture" - not captured by skill matching.
  - [x] 31.1 Create domain expertise dictionary:
    - [x] 31.1.1 Create `data/domain_expertise.json` with industry/platform domains
    - [x] 31.1.2 Define categories: Industries (ecommerce, fintech, healthcare, etc.), Platforms (Shopify, Salesforce, SAP), Technologies (headless CMS, MACH, composable)
    - [x] 31.1.3 Add keyword patterns for each domain (e.g., "ecommerce" matches "e-commerce", "online retail", "digital commerce")
  - [x] 31.2 Build domain extraction from job descriptions:
    - [x] 31.2.1 Create `extract_domain_requirements()` function in `skill_extractor.py`
    - [x] 31.2.2 Identify required vs. preferred domains (look for "must have", "required" vs. "nice to have")
    - [x] 31.2.3 Store extracted domains in JobPosting model (new `required_domains` field)
  - [x] 31.3 Add domain matching to resume:
    - [x] 31.3.1 Add `domains` field to Resume model
    - [x] 31.3.2 Allow users to specify their domain expertise in resume
    - [x] 31.3.3 Create `/domains` Telegram command to view/update domain expertise
  - [ ] 31.4 Integrate domain matching into scoring (Future enhancement):
    - [ ] 31.4.1 Add domain match component to overall score formula
    - [x] 31.4.2 Flag jobs with domain mismatch (⚠️ warning in output)
    - [ ] 31.4.3 Option to filter out jobs requiring domains user lacks
  - [x] 31.5 Display domain info in match output:
    - [x] 31.5.1 Show required domains in `/matches` output
    - [x] 31.5.2 Show domain match/mismatch status
    - [x] 31.5.3 Add domain column to Google Sheets export
  - **Done:** Created 44-domain dictionary across 3 categories (industries, platforms, technologies). Added `extract_domain_requirements()` with context-aware required/preferred detection. Created `/domains` command to manage user expertise. Shows ⚠️ warnings in `/matches` for missing domains. Backfilled 347 existing jobs with domain data.

- [ ] 32.0 Resume Bullet Point Targeter (Streamlit Web App)
  - **Goal:** Build interactive web app to rewrite resume bullets for specific job descriptions
  - **Success Metric:** Improved ATS matching and interview selection rates
  - **Reference:** See plan at `.claude/plans/logical-brewing-otter.md` for full architecture details

  - [ ] 32.1 Phase 1: MVP - Core Infrastructure
    - [ ] 32.1.1 Create `src/targeting/__init__.py` module structure
    - [ ] 32.1.2 Create `src/targeting/role_analyzer.py`:
      - [ ] Define `RoleAnalysis` and `BulletScore` dataclasses
      - [ ] Implement `analyze_role()` using NLP similarity (reuse SkillsMatcher patterns)
      - [ ] Implement `analyze_all_roles()` for full resume analysis
    - [ ] 32.1.3 Create `src/web/__init__.py` module structure
    - [ ] 32.1.4 Create `src/web/app.py` basic Streamlit app:
      - [ ] Add sidebar with job dropdown (from MatchResult/JobPosting)
      - [ ] Add resume file selector (.txt/.md)
      - [ ] Display role-by-role alignment scores
      - [ ] Add basic export to .txt functionality
    - [ ] 32.1.5 Create `run_targeter.py` entry point script
    - [ ] 32.1.6 Add `streamlit>=1.29.0` to `requirements.txt`
    - [ ] 32.1.7 Test MVP: verify role alignment scores display correctly

  - [ ] 32.2 Phase 2: Gemini Integration
    - [ ] 32.2.1 Add `BULLET_REWRITE_PROMPT` template to `src/integrations/gemini_client.py`
    - [ ] 32.2.2 Create `src/targeting/bullet_rewriter.py`:
      - [ ] Implement `BulletRewriter` class following existing Gemini patterns
      - [ ] Extract JD requirements for context
      - [ ] Generate 2-3 bullet alternatives for low-scoring bullets
      - [ ] Use temperature 0.35 for balanced creativity/consistency
    - [ ] 32.2.3 Update `src/web/app.py` with bullet-level analysis:
      - [ ] Show bullet scores with color indicators (green ≥70%, yellow 50-70%, red <50%)
      - [ ] Display AI suggestions as radio button options
      - [ ] Add custom edit text input for each bullet
    - [ ] 32.2.4 Create `src/targeting/exporter.py`:
      - [ ] Implement `export_txt()` to generate tailored resume file
      - [ ] Use filename template: `Resume_Tailored_{company}_{date}.txt`
      - [ ] Apply user-selected bullet replacements
    - [ ] 32.2.5 Test Phase 2: verify AI suggestions appear and export works

  - [ ] 32.3 Phase 3: Polish & UX
    - [ ] 32.3.1 Add diff/preview view before export:
      - [ ] Implement `generate_diff_view()` in exporter
      - [ ] Show side-by-side original vs. modified in Streamlit
    - [ ] 32.3.2 Add progress indicators during Gemini API calls
    - [ ] 32.3.3 Implement error handling for API failures (graceful degradation)
    - [ ] 32.3.4 Add Streamlit page configuration (title, favicon, wide layout)
    - [ ] 32.3.5 Style improvements using Streamlit theming
    - [ ] 32.3.6 Test end-to-end workflow with multiple jobs/resumes

  - [ ] 32.4 Configuration & Documentation
    - [ ] 32.4.1 Add `targeting` section to `config.yaml.example`
    - [ ] 32.4.2 Create `docs/RESUME_TARGETER.md` with usage instructions

  - [ ] 32.5 Phase 4: Future Enhancements
    - [ ] 32.5.1 JSON Resume Format:
      - [ ] Design JSON schema for structured resumes (roles, bullets, skills, dates)
      - [ ] Create JSON resume editor/converter in Streamlit
      - [ ] Update ResumeParser to handle JSON format
      - [ ] Add skill tagging per bullet for precise matching
      - [ ] Support resume versioning and change history
    - [ ] 32.5.2 Enhanced Resume Library:
      - [ ] Add resume deletion from library
      - [ ] Add resume rename/edit metadata
      - [ ] Import existing resumes to JSON format
    - [ ] 32.5.3 Batch Analysis:
      - [ ] Analyze one resume against multiple jobs
      - [ ] Compare alignment across job opportunities
