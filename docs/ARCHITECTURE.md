# LinkedIn Job Matcher - Architecture & Process Flow

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              LINKEDIN JOB MATCHER                                │
└─────────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   INPUTS     │────▶│  PROCESSING  │────▶│   STORAGE    │────▶│   OUTPUTS    │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

## Detailed Process Flow

```
                                    ┌─────────────────┐
                                    │   USER (You)    │
                                    └────────┬────────┘
                                             │
                         ┌───────────────────┼───────────────────┐
                         │                   │                   │
                         ▼                   ▼                   ▼
                  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
                  │   Web App   │     │  Telegram   │     │   Config    │
                  │ (React UI)  │     │  Commands   │     │   (YAML)    │
                  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
                         │                   │                   │
                         ▼                   ▼                   │
┌────────────────────────┼───────────────────┼───────────────────┼────────────────┐
│  FASTAPI BACKEND       │                   │                   │                │
│  ┌─────────────────────┼───────────────────┼───────────────────┼─────────────┐  │
│  │                     │           TELEGRAM BOT                │             │  │
│  │  /api/search        │           /start  /search             │             │  │
│  │  /api/jobs          │           /status /matches            │             │  │
│  │  /api/resumes       │           /mute   /schedule           │             │  │
│  │                     │                                       │             │  │
│  └─────────────────────┴───────────────────┬───────────────────┼─────────────┘  │
│                                            │                   │                │
└────────────────────────────────────────────┼───────────────────┼────────────────┘
                                             │                   │
                                             ▼                   ▼
          ┌──────────────────────────────────────────────────────────────┐
          │                      JOB SCHEDULER                           │
          │  ┌────────────────────────────────────────────────────────┐  │
          │  │  Telegram JobQueue (python-telegram-bot)               │  │
          │  │  Schedule: 08:00, 12:00, 16:00, 20:00                  │  │
          │  └────────────────────────────────────────────────────────┘  │
          └───────────────────────────┬──────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
                    ▼                 ▼                 ▼
          ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
          │  Manual Search  │ │ Scheduled Run   │ │  Web Search     │
          │   (/search)     │ │  (Automatic)    │ │  (/api/search)  │
          └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
                   │                   │                   │
                   └─────────┬─────────┴───────────────────┘
                             │
                             ▼
          ┌──────────────────────────────────────────────────────────────┐
          │                      APIFY API                               │
          │              LinkedIn Jobs Scraper                           │
          └───────────────────────────┬──────────────────────────────────┘
                                      │
                                      ▼
          ┌──────────────────────────────────────────────────────────────┐
          │                      JOB IMPORT & MATCHING                   │
          │  • Import: Deduplicate, Check Freshness, Store in DB         │
          │  • Match: NLP Skills + Experience + Gemini Domain Extraction │
          └───────────────────────────┬──────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │                                   │
                    ▼                                   ▼
          ┌─────────────────┐                 ┌─────────────────┐
          │  SQLite Database│                 │  Match Results  │
          │  (Jobs/Resumes) │                 │  (Table)        │
          └────────┬────────┘                 └─────────────────┘
                   │
                   ▼
          ┌──────────────────────────────────────────────────────────────┐
          │                      OUTPUT & NOTIFICATION                   │
          │  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐      │
          │  │  Web UI      │   │ Telegram     │   │ Google Sheets│      │
          │  │  (Dashboard) │   │ (Push Notif) │   │ (Export)     │      │
          │  └──────────────┘   └──────────────┘   └──────────────┘      │
          └──────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. FRONTEND (Web App)

| Component | Technology | Description |
|-----------|------------|-------------|
| **Core** | React + Vite | Modern SPA architecture |
| **UI Framework** | Tailwind CSS + Shadcn | Responsive, accessible UI components |
| **Server State** | TanStack React Query | API caching and synchronization |
| **Global State** | Zustand | Search state persistence across navigation |
| **Pages** | `Dashboard`, `Library`, `GetJobs`, `Analytics` | Main application views |
| **API Client** | `api.ts` | Typed interface to Backend |

#### Key Frontend Files

| File | Purpose |
|------|---------|
| `stores/searchStore.ts` | Zustand store for job search state (persists across page navigation) |
| `components/SearchStatusIndicator.tsx` | Floating progress indicator shown on all pages during active search |
| `components/analytics/PerformanceTab.tsx` | Latency and success charts for system performance |
| `pages/GetJobs.tsx` | Job search page consuming global search state |
| `pages/JobMatches.tsx` | Match results with AI insights panel, score tooltips, aggregated insights |
| `pages/Dashboard.tsx` | Resume analysis with AI match context when selecting jobs |
| `services/api.ts` | API client with React Query hooks and AI match types |

### 2. BACKEND (FastAPI)

| Component | File | Purpose |
|-----------|------|---------|
| **Main App** | `backend/main.py` | FastAPI application entry point, CORS, static files |
| **Search Router** | `backend/routers/search.py` | Handles distinct search pipelines (Instrumented) |
| **Analytics Router** | `backend/routers/analytics.py` | Aggregates system metrics and performance data |
| **Performance Logger** | `src/services/performance_logger.py` | Tracks API latency and success rates |
| **Bullet Router** | `backend/routers/bullets.py` | Manages saved/liked bullet rewrites |
| **Telegram Bot** | `src/bot/telegram_bot.py` | Command handling, user interaction |
| **Job Scheduler** | `src/scheduler/job_scheduler.py` | Automated background scheduling |
| **API Importer** | `src/importers/apify_provider.py` | Fetch jobs from Apify |
| **Job Matcher** | `src/matching/engine.py` | Orchestrate matching (dual-mode) |
| **AI Matcher** | `src/matching/gemini_matcher.py` | Gemini-based AI matching |
| **Match Types** | `src/matching/requirements.py` | Data structures for AI results |
| **Resume Parser** | `src/resume/parser.py` | Parse text/PDF/JSON resumes |

### 3. STORAGE

| Component | Type | Data Stored |
|-----------|------|-------------|
| **SQLite Database** | `linkedin_job_matcher.db` | Jobs, Resumes, Match Results, Liked Bullets, Perf Logs |
| **Google Sheets** | External | Job Matches (≥70%), All Jobs (Logs) |
| **Config File** | `config.yaml` | Settings, profiles, schedule |

## Data Flow Sequences

### A. Web App Search Flow (Real-time)

```
1. USER ACTION
   └── User configures parameters (keyword, location, filters) on "Get Jobs" page

2. INITIALIZATION (SSE Stream)
   ├── Validate inputs and resume file
   ├── Store search state in Zustand (persists across navigation)
   └── Establish Server-Sent Events connection

3. FETCHING
   ├── Call Apify LinkedIn Jobs Scraper API
   ├── Stream progress: "Fetching jobs..."
   └── Global SearchStatusIndicator shows progress on all pages

4. IMPORTING
   ├── Normalize and validate job data
   ├── Import to SQLite (skip duplicates)
   └── Return "Fetched Jobs" list (unmatched raw jobs) for transparency

5. MATCHING
   ├── Load parsed resume skills/experience
   ├── Filter jobs (Location, Freshness)
   ├── Calculate Match Scores:
   │   ├── Skills (NLP Semantic Similarity)
   │   └── Experience (Years alignment)
   ├── Re-rank using Gemini AI (if enabled)
   └── Store high-quality matches

6. EXPORTING & COMPLETION
   ├── Export to Google Sheets (if selected)
   ├── Return final `SearchResult` object
   ├── Frontend displays: Stats, Top Matches, and Fetched Jobs
   └── Toast notification confirms success

NOTE: Search continues running even if user navigates away from GetJobs page.
      Returning to the page restores the search state (progress or results).
```

### B. Scheduled/Telegram Flow (Background)

```
1. TRIGGER
   ├── Manual: /search command
   └── Automatic: Schedule (08:00, 12:00, 16:00, 20:00)

2. EXECUTION
   ├── Fetch active profile configuration
   ├── Call Apify API
   ├── Import and Match (same core logic as Web App)
   ├── Export to Sheets
   └── Notify via Telegram (Push Top 5 matches)
```

## Match Score Calculation

The system supports **dual-mode matching** configurable via `matching.engine`:

### Mode 1: NLP Matching (`engine: "nlp"`)

Fast, free matching using traditional NLP techniques:

```
Overall Score = (Skills × 0.45) + (Experience × 0.35) + (Domains × 0.20)

1. Skills Score (NLP):
   - Semantic similarity using `sentence-transformers` (all-MiniLM-L6-v2)
   - Compares job description skills vs resume skills

2. Experience Score:
   - Years of experience comparison (Resume vs Required)
   - Seniority level matching
   - Generates alignment text (e.g., "Resume: 5 years, Required: 3 years")

3. Domain Score:
   - Gemini LLM extracts industry domains (Fintech, SaaS, etc.)
   - Simple set intersection matching
```

### Mode 2: AI Matching (`engine: "gemini"`)

Full AI-powered matching with rich insights using Google Gemini:

```
┌─────────────────────────────────────────────────────────────────┐
│                    GEMINI AI MATCHER                            │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐   │
│  │ Resume Data   │───▶│ Gemini LLM    │───▶│ Match Result  │   │
│  │ + Job Posting │    │ (Structured   │    │ + Insights    │   │
│  │               │    │  Prompting)   │    │               │   │
│  └───────────────┘    └───────────────┘    └───────────────┘   │
└─────────────────────────────────────────────────────────────────┘

Output includes:
├── Component Scores (0-100)
│   ├── skills_score      # How well skills match
│   ├── experience_score  # Experience level fit
│   ├── seniority_fit     # Career stage alignment
│   └── domain_score      # Industry relevance
│
├── Skill Analysis
│   ├── skill_matches[]   # Matched skills with confidence
│   └── skill_gaps[]      # Missing skills with transferability
│
└── Insights
    ├── strengths[]       # Candidate advantages
    ├── concerns[]        # Potential issues
    └── recommendations[] # Application tips
```

### Mode 3: Auto (`engine: "auto"`) - Default

Uses Gemini if available and configured, otherwise falls back to NLP.

### Key Files

| File | Purpose |
|------|---------|
| `src/matching/engine.py` | Orchestrates matching, selects mode |
| `src/matching/gemini_matcher.py` | AI matching prompts and logic |
| `src/matching/requirements.py` | Data structures for AI matching |
| `src/matching/skills_matcher.py` | NLP semantic similarity |

## Configuration

Key settings in `config.yaml`:

```yaml
search:
  default_location: "United States"
  default_max_results: 20
  default_job_type: "Full-time"

matching:
  # Matching engine mode: "nlp" | "gemini" | "auto" (default)
  engine: "auto"

  # NLP weights (used when engine is "nlp" or as fallback)
  weights:
    skills: 0.45
    experience: 0.35
    domains: 0.20
  min_match_score: 0.6

gemini:
  enabled: true
  api_key: "YOUR_API_KEY"

  # AI Matcher settings
  matcher:
    enabled: true
    model: "gemini-3-flash-preview"  # Best accuracy
    batch_model: "gemini-2.0-flash"  # Faster for bulk ops
    concurrency: 5
    fallback_to_nlp: true            # Fall back if Gemini fails

sheets:
  enabled: true
  auto_export: true
```

## Domain Extraction

Jobs are tagged with industry domains (fintech, healthcare, b2b_saas, etc.) using Google's Gemini LLM for high accuracy.

### Supported Domains
- **Industries**: fintech, banking, healthcare, ecommerce, b2b_saas, etc.
- **Platforms**: salesforce, shopify, stripe, snowflake, etc.
- **Technologies**: ai_ml, blockchain, devops, mobile, etc.

## AI Match Insights (Frontend)

When using Gemini AI matching, the frontend displays rich insights:

### Job Matches Page (`JobMatches.tsx`)

| Feature | Description |
|---------|-------------|
| **AI/NLP Badge** | Shows matching engine used (violet "AI" or blue "NLP" badge) |
| **Score Tooltip** | Hover over radial score to see component breakdown |
| **Stats Bar** | Shows AI vs NLP match counts (e.g., "15/35 AI/NLP Matches") |
| **Aggregated Insights** | Panel showing common skill gaps, strengths, and recommendations across all AI-matched jobs |
| **Expanded Card** | Full AI analysis with strengths, concerns, recommendations, and skill gaps with transferability |

### Resume Analysis Page (`Dashboard.tsx`)

When selecting an AI-matched job for resume analysis:
- Shows AI match context (strengths, concerns, focus areas)
- Displays key skill gaps to address during bullet rewriting
- NLP-matched jobs show prompt to enable Gemini for richer insights

### Data Flow

```
Backend (search.py)
    │
    ├── AI Match Result
    │   ├── ai_match_score, skills_score, experience_score, etc.
    │   ├── ai_strengths[], ai_concerns[], ai_recommendations[]
    │   └── skill_matches[], skill_gaps_detailed[]
    │
    ▼
Frontend (api.ts types)
    │
    ├── Job interface with AI fields
    │
    ▼
UI Components
    ├── JobMatches.tsx (full display)
    └── Dashboard.tsx (context for analysis)
```

## AI Bullet Optimization & Persistence

The system uses Gemini to rewrite specific resume bullet points to better align with a job description.

### Suggestion Generation
1. **User Request**: User clicks "Generate suggestions" for a role on the Dashboard.
2. **Analysis**: System identifies low-scoring bullets (<70% match).
3. **Generation**: Gemini generates 3 rewritten options for each low-scoring bullet.
4. **Persistence**:
   - Suggestions are saved to `MatchResult.bullet_suggestions` column in the database.
   - Keyed by `Company_Title` to ensure correct alignment if resume structure changes.
   - **Cost Saving**: Subsequent loads of the same match retrieve saved suggestions instantly without calling the LLM.

### "Liked" Bullets Library
- Users can "like" (save) specific rewrites they prefer.
- **Storage**: Saved to `liked_bullets` table with context (Original, Rewrite, Company, Role, Date).
- **Library View**: A dedicated "Saved Bullets" tab in the Resume Library allows reviewing/copying these snippets for future use.

## Telegram Commands

| Command | Action |
|---------|--------|
| `/start`, `/help` | Basic bot interaction |
| `/search [kw]` | Trigger manual search |
| `/matches` | View recent top matches |
| `/status`, `/config` | View system status/config |
| `/mute`, `/schedule` | Manage notifications |
