# Product Requirements Document: LinkedIn Job Matcher

## Introduction/Overview

The LinkedIn Job Matcher is an automated tool designed to streamline and optimize the job search process for job seekers. Instead of manually searching LinkedIn for relevant positions, comparing each posting to their resume, and deciding whether to apply, users can leverage this tool to automatically discover, analyze, and prioritize job opportunities that align with their qualifications.

The tool solves the problem of time-consuming, inefficient job searches by automating the discovery of recent LinkedIn job postings, intelligently matching them against the user's resume based on skills and experience level, and highlighting high-potential opportunities through email notifications. By tracking application status, the tool also helps users stay organized throughout their job search journey.

**Problem Statement:** Manually searching for relevant jobs on LinkedIn, comparing them to one's resume, and deciding whether to apply is time-consuming and inefficient.

**Solution:** An automated system that finds recent, relevant LinkedIn job postings, analyzes them against a user's resume, flags high-potential opportunities, and tracks application progress.

## Goals

1. **Automate Job Discovery:** Reduce manual effort in finding relevant job postings by accepting multiple input formats (PDF, text, structured data).
2. **Intelligent Matching:** Provide accurate job-to-resume matching based on skills and experience level to surface the most relevant opportunities.
3. **Increase Efficiency:** Save users significant time (target: 80%+ reduction in manual search time) by automating the comparison and prioritization process.
4. **Improve Job Search Success:** Help users identify and apply to positions where they have a strong fit, increasing application-to-interview conversion rates.
5. **Enable Flexible Scheduling:** Support both on-demand searches and automated scheduled searches to fit different user workflows.
6. **Maintain Organization:** Track application status to help users manage their job search pipeline effectively.

## User Stories

**As a job seeker**, I want to:

1. **Upload my resume in plain text or Markdown format** so that the tool can understand my skills, experience, and qualifications without complex parsing requirements.

2. **Import job postings from multiple sources** (PDF exports, text files, structured JSON/CSV data, or automatically via 3rd party API services like Apify) so that I can use the tool regardless of how I've collected job information or automate the collection process entirely.

3. **Receive email notifications with top-matched jobs** so that I can quickly review high-potential opportunities without checking a separate dashboard or application.

4. **See why a job is recommended** (matching skills, experience level alignment, relevant job titles) so that I can make informed decisions about which positions to pursue.

5. **Trigger job searches on-demand** so that I can get immediate results when I have time to review opportunities.

6. **Set up automated scheduled searches** (daily or weekly) so that new job postings are continuously analyzed without manual intervention.

7. **Track which jobs I've applied to** so that I can avoid duplicate applications and maintain an organized record of my job search progress.

8. **View application status** (saved, applied, interviewing, rejected, offer) so that I can manage my entire job search pipeline in one place.

9. **Export high-scoring job matches to Google Sheets** so that I can review, annotate, and track opportunities in a familiar spreadsheet format for quality control and long-term reference.

10. **Control the job matcher remotely via Telegram** so that I can trigger searches, check status, and view top matches from my mobile device when away from my computer.

## Functional Requirements

### Core Functionality

1. **Resume Management**
   - 1.1: The system must accept user resumes in plain text (.txt) or Markdown (.md) format.
   - 1.2: The system must parse the resume to extract key information including: skills/technologies, years of experience, previous job titles, and education.
   - 1.3: The system must store the parsed resume data for repeated matching operations.

2. **Job Posting Import**
   - 2.1: The system must support importing job postings from PDF files.
   - 2.2: The system must support importing job postings from plain text files.
   - 2.3: The system must support importing job postings from structured data formats (JSON/CSV).
   - 2.4: The system must support integration with 3rd party API services (e.g., Apify, ScraperAPI, Bright Data) to automatically fetch LinkedIn job postings based on search criteria.
   - 2.5: The system must allow users to configure API service credentials and search parameters (keywords, location, job type, etc.) for automated job fetching.
   - 2.6: The system must handle API rate limits and errors gracefully, with retry logic and appropriate error messages.
   - 2.7: The system must extract relevant job information including: job title, required skills, experience level, company name, location, posting date, job description, and job URL.
   - 2.8: The system must validate that imported job postings contain minimum required fields before processing.
   - 2.9: The system must reject job postings older than 24 hours from the posting date, regardless of import source (manual or automated).

3. **Job Matching Engine**
   - 3.1: The system must compare job postings against the user's resume based on skills matching using NLP-based similarity rather than exact keyword matching.
   - 3.2: The system must use a predefined Product Management skills dictionary to boost and prioritize PM-related terms (e.g., "roadmapping," "stakeholder management," "A/B testing," "PRD writing," "OKRs," "user stories") in the NLP matching algorithm.
   - 3.3: The system must recognize skill synonyms and related technologies using NLP (e.g., "React" and "React.js", "ML" and "Machine Learning", "Product Manager" and "PM").
   - 3.4: The system must evaluate experience level compatibility by comparing required years of experience and job title seniority.
   - 3.5: The system must generate a match score (0-100) for each job posting based on a weighted combination of skills match (50% default) and experience level match (50% default).
   - 3.6: The system must allow match score weights to be configurable via the configuration file (YAML/JSON), enabling users to adjust the importance of skills vs. experience.
   - 3.7: The system must rank job postings by match score in descending order.
   - 3.8: The system must identify and highlight specific matching criteria (which skills match, how experience aligns) for each job.
   - 3.9: The system must track and record which matching engine version was used to generate each match result, enabling historical tracking and algorithm comparison.

4. **Email Notifications**
   - 4.1: The system must send email notifications via Gmail using OAuth 2.0 authentication for secure, passwordless access.
   - 4.2: The system must send email notifications immediately when new matched jobs are found (no batching or digest mode).
   - 4.3: Email notifications must include top-matched jobs based on configurable threshold (e.g., top 10 or score > 70).
   - 4.4: Email notifications must include: job title, company name, match score, key matching points, and a link to the original job posting.
   - 4.5: The system must allow users to configure email notification preferences (minimum match score, maximum number of jobs per email).
   - 4.6: The system must format email notifications in a clear, scannable format (HTML preferred with plain text fallback).

5. **Search Scheduling**
   - 5.1: The system must support on-demand job searches triggered manually by the user.
   - 5.2: The system must support scheduled automatic searches that run at configured intervals (daily, weekly, or custom schedule).
   - 5.3: The system must allow users to enable/disable scheduled searches.
   - 5.4: The system must prevent duplicate processing of the same job posting by matching on job title + company name combination.
   - 5.5: The system must normalize job titles and company names (case-insensitive, trim whitespace) before duplicate detection.

6. **Application Tracking**
   - 6.1: The system must store a record of each job posting with its match score and analysis.
   - 6.2: The system must allow users to mark job status as: Saved, Applied, Interviewing, Rejected, or Offer.
   - 6.3: The system must display the application status alongside job information in emails and reports.
   - 6.4: The system must track the date when status changes occur.
   - 6.5: The system must allow users to add notes to individual job postings.

7. **Google Sheets Integration**
   - 7.1: The system must support exporting job matches to Google Sheets using OAuth 2.0 authentication for secure, passwordless access.
   - 7.2: The system must automatically export high-scoring matches (above configurable threshold, default 70%) to a designated Google Sheet when new matches are found.
   - 7.3: The system must create and format the spreadsheet with columns for: Job Title, Company, Location, Overall Score, Skills Score, Experience Score, Matching Skills, Skill Gaps, Posted Date, and Job URL.
   - 7.4: The system must apply professional formatting including: blue header row with white text, frozen header row for scrolling, and clean data rows with black text on white background.
   - 7.5: The system must support batch export operations to efficiently write multiple job matches in a single API call.
   - 7.6: The system must prevent duplicate exports by checking existing spreadsheet data before adding new rows.
   - 7.7: The system must allow users to configure: spreadsheet ID, sheet name, export threshold score, and whether to auto-export after each search.
   - 7.8: The system must reuse existing Google OAuth credentials (from Gmail setup) for Sheets access, with a separate token file for Sheets API authorization.
   - 7.9: The system must export ALL retrieved job postings (not just high-scoring matches) to a separate "Logs" sheet for analysis and quality control purposes.
   - 7.10: The Logs sheet must include detailed columns: Timestamp, Job Title, Company, Location, Match Score, Skills Score, Experience Score, Matching Skills, Missing Skills, Required Skills, Experience Required, LinkedIn URL, Job ID, Resume ID, Posted Date, Description Preview, and Engine Version.
   - 7.11: The system must automatically log all jobs to the Logs sheet after each search run, providing a complete audit trail of all jobs analyzed by the matching algorithm.

8. **Telegram Bot Remote Control**
   - 8.1: The system must provide a Telegram bot interface for remote control and monitoring of the job matcher.
   - 8.2: The system must authenticate the Telegram bot using a bot token obtained from @BotFather.
   - 8.3: The system must restrict bot access to authorized users only via a configured allowed_user_id for security.
   - 8.4: The system must support the following bot commands:
     - `/start` - Welcome message and quick help
     - `/help` - Display all available commands with descriptions
     - `/search` - Trigger an immediate job search remotely
     - `/status` - Display scheduler status, configuration, and statistics
     - `/matches` - Show top 5 recent job matches with scores
     - `/config` - Display current configuration settings
   - 8.5: The system must send notifications via Telegram when job searches complete, including total jobs analyzed count, high-quality matches count (≥70%), top results, and a clickable link to the Google Sheets spreadsheet.
   - 8.6: The system must format Telegram messages with clear structure, emojis for readability (🔥 for ≥85%, ✨ for ≥75%, ⭐ for ≥70%), and relevant job details including title, company, and match score.
   - 8.7: The system must integrate with the job scheduler to enable remote triggering of searches.
   - 8.8: The system must be deployable to free cloud platforms (Railway, Render, Fly.io) to run 24/7.
   - 8.9: The system must support environment variable configuration for secure credential management in cloud environments.

9. **Data Persistence**
   - 9.1: The system must store resume data, job postings, match results, and application status in a database for persistent storage.
   - 9.2: The system must store ALL retrieved job postings with their match scores, regardless of score value, for review and quality control purposes.
   - 9.3: The system must maintain a history of all processed job postings to avoid reprocessing and enable duplicate detection.
   - 9.4: The system must allow users to query the database directly to review stored jobs, match scores, and historical data.
   - 9.5: The system must allow users to update their resume, which should trigger re-matching of saved job postings.

## Non-Goals (Out of Scope)

The following features are explicitly **not** included in this version:

1. **Direct LinkedIn Scraping:** The tool will not build or maintain its own LinkedIn scraper. Instead, it will leverage 3rd party API services (like Apify) for automated job posting collection, or accept manual imports via supported file formats.

2. **One-Click Apply:** The tool will not submit job applications on behalf of the user. It only identifies and recommends opportunities.

3. **Cover Letter Generation:** Automated creation of customized cover letters is not included.

4. **Resume Optimization:** The tool will not suggest improvements to the user's resume or provide resume editing features.

5. **Salary Analysis:** Comparing job salaries or providing salary recommendations is out of scope.

6. **Company Research:** Detailed company information, reviews, or culture analysis is not included.

7. **Interview Preparation:** Interview scheduling, preparation materials, or coaching features are not included.

8. **Mobile Application:** A native mobile app is not included; the tool will be a command-line or web-based application.

9. **Multi-User/Team Features:** Sharing job searches, collaborative filtering, or team-based features are not supported.

10. **Advanced Resume Formats:** Complex resume parsing for PDF resumes with varied layouts is not supported (only plain text/Markdown).

11. **Multi-Resume Support:** The ability to maintain multiple resume profiles for different job types (e.g., one for backend roles, one for full-stack roles) is not included in this version but may be added as a future enhancement.

12. **Advanced Export Formats:** While Google Sheets export is supported, exporting to other formats (CSV files, Notion, Airtable, etc.) is not included in this version.

## Design Considerations

### User Interface
- The tool should primarily operate via command-line interface (CLI) for technical users, with potential for a simple web dashboard in future iterations.
- Email notifications should be well-formatted, mobile-responsive HTML emails with clear call-to-action buttons.
- If a web interface is built, it should include: a dashboard showing recent matches, a table for tracking applications with sortable columns, and a settings page for configuration.

### Email Design
- Subject line should be clear and actionable (e.g., "5 New Job Matches Found - 85% Match Score or Higher")
- Each job in the email should have a card-like layout with: company logo (if available), job title, company name, match score (visual indicator like progress bar or stars), top 3-5 matching skills, experience alignment note, and "View Job" button linking to the original posting.

### Configuration Management
- Users should configure settings via a configuration file (YAML or JSON) including: email address, notification preferences, schedule settings, matching thresholds, match score weights (skills vs. experience), and data storage location.
- The configuration file should include default values that work out-of-the-box, with clear comments explaining each setting.

## Technical Considerations

### Technology Stack Suggestions
- **Language:** Python (recommended for text processing, scheduling, and email capabilities) or Node.js/TypeScript
- **Database:** SQLite (lightweight, embedded) or PostgreSQL (if more robust querying is needed)
- **Email Service:** Gmail API with OAuth 2.0 authentication (using libraries like `google-auth` and `google-api-python-client` for Python, or `googleapis` for Node.js) for secure, passwordless email sending
- **Scheduling:** `APScheduler` (Python) or `node-cron` (Node.js) for automated searches
- **NLP & Text Processing:** NLP libraries like `spaCy`, `sentence-transformers`, or `nltk` (Python) for semantic skill matching and experience extraction. Regular expressions for structured data parsing.
- **Job Data API Services:** Apify (LinkedIn Job Scraper actors), ScraperAPI, Bright Data, or similar platforms for automated job posting collection. These services provide pre-built scrapers and handle anti-bot protections, rate limiting, and proxy management.
- **Product Management Skills Dictionary:** A curated JSON/YAML file containing PM-specific skills, competencies, and common synonyms to boost matching accuracy for Product Management roles.

### Data Storage
- Store resume data in a structured format (JSON or database table) with fields for: skills array, experience years, job titles array, education, and last updated timestamp
- Store job postings with fields for: job_id (unique), title, company, description, required_skills array, experience_required, posting_date, import_date, source, and original_url
- Store match results with fields for: job_id, resume_id, match_score, matching_skills array, experience_alignment, generated_date
- Store application tracking with fields for: job_id, status, status_date, user_notes

### Security
- Email credentials should be stored securely (environment variables or encrypted configuration)
- API service credentials (API keys, tokens) should be stored securely using environment variables or encrypted configuration files
- User data (resume, job postings, application status) should be stored locally or with proper access controls if using a remote database
- API requests should use HTTPS and validate SSL certificates

### Dependencies
- The tool should integrate with the user's existing email provider (Gmail, Outlook, etc.)
- Integration with 3rd party API services (Apify, ScraperAPI, Bright Data, etc.) for automated job posting collection
- Users must have valid API credentials and sufficient quota/credits with their chosen API service provider
- No direct LinkedIn API or scraping implementation (delegated to 3rd party services)

## Success Metrics

The success of the LinkedIn Job Matcher will be measured by:

1. **Time Savings:** Users report 80%+ reduction in time spent manually searching and filtering job postings.

2. **Match Accuracy:** 70%+ of jobs flagged as "high match" (score > 75) are considered relevant by the user upon review.

3. **User Adoption:** Users configure and run scheduled searches, indicating trust in the automation.

4. **Application Conversion:** Users apply to a higher percentage of discovered jobs compared to manual searching (baseline to be established).

5. **Tool Reliability:** 95%+ uptime for scheduled searches; no missed scheduled job searches.

6. **Email Engagement:** 60%+ email open rate and 40%+ click-through rate on job links in notification emails.

7. **Application Tracking Usage:** 70%+ of discovered jobs have their status updated by the user, indicating active use of the tracking feature.

## Design Decisions

The following key design decisions have been made for this version:

1. **Email Provider Configuration:** Gmail with OAuth 2.0 authentication for secure, passwordless email sending. Users will complete a one-time browser-based authentication flow.

2. **Matching Algorithm Weights:** Default 50/50 split between skills matching and experience level matching. Weights are fully configurable via the configuration file (YAML/JSON) to allow users to adjust based on their preferences.

3. **Job Posting Freshness:** Strict 24-hour filter applied to all job imports. Any job posting older than 24 hours from its posting date will be rejected, regardless of import source (manual or automated).

4. **Duplicate Detection:** Job postings are identified as duplicates based on normalized job title + company name combination (case-insensitive, trimmed whitespace).

5. **Skill Synonyms:** NLP-based semantic similarity for skill matching, enhanced with a predefined Product Management skills dictionary. The dictionary boosts and prioritizes PM-specific terms (e.g., "roadmapping," "stakeholder management," "OKRs") in the matching algorithm.

6. **Notification Batching:** Emails are sent immediately when new matched jobs are found. No batching or digest mode.

7. **Multi-Resume Support:** Not included in this version. Deferred as a future enhancement (see Non-Goals section).

8. **Google Sheets Export:** High-scoring job matches (70%+ threshold by default) are automatically exported to Google Sheets using OAuth 2.0 authentication. Spreadsheet formatting uses a clean, professional design with blue header row (white text) and plain black text on white background for data rows. No conditional formatting applied to data cells to maintain readability.

9. **Telegram Bot Security:** Bot access is restricted to a single authorized user via allowed_user_id configuration. Bot token authentication via @BotFather. Supports deployment to free cloud platforms (Railway, Render, Fly.io) with environment variable configuration for secure credential management.

10. **Remote Access Architecture:** Telegram bot chosen over web dashboard for mobile-first remote access, enabling job search control from anywhere without requiring a dedicated web server or complex infrastructure.

11. **Mock Data Mode for Testing:** The system supports a mock data mode (configurable via `apify.use_mock_data: true` in config.yaml) that loads job postings from a local JSON file (`dataset.json`) instead of calling the Apify API. This enables cost-free testing and development by:
    - Skipping all external API calls and avoiding API usage costs
    - Bypassing 24-hour freshness validation to allow testing with older data
    - Disabling duplicate detection to allow importing the same test jobs multiple times
    - Supporting full end-to-end testing of matching, export, and notification workflows without external dependencies

12. **Complete Job Logging:** ALL job postings retrieved during a search (not just high-scoring matches) are automatically logged to a separate "Logs" sheet in Google Sheets. This provides a complete audit trail for analyzing matching algorithm performance, identifying edge cases, and quality control. The Logs sheet includes 17 detailed columns including match scores, skills analysis, job metadata, and matching engine version.

13. **Matching Engine Versioning:** The matching algorithm is versioned using semantic versioning (v{major}.{minor}.{patch}) to track changes over time. Each match result records which engine version was used, enabling:
    - Historical tracking of algorithm performance across versions
    - A/B testing of different matching approaches
    - Ability to compare results from different algorithm configurations
    - Clear documentation of when and why matching logic changed

    Version numbers follow this scheme:
    - **Major version** (e.g., v1.x.x → v2.x.x): Breaking changes to core scoring algorithm or formula
    - **Minor version** (e.g., v1.0.x → v1.1.x): New features, component additions, or significant weight adjustments
    - **Patch version** (e.g., v1.0.0 → v1.0.1): Bug fixes, minor tweaks, or threshold adjustments

    The current baseline implementation is v1.0.0 (50/50 skills-experience weighting, step-based experience scoring).
