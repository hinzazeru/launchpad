# AI Assistant Context - LaunchPad 💸

This file provides context for AI assistants (Claude, GPT, Copilot, etc.) working on this codebase.

## Project Overview

LaunchPad 💸 is a Python application that automates job discovery by:
1. Fetching job postings from LinkedIn via Apify API
2. **Dual-Mode Matching**: Jobs matched against resume using NLP (fast, free) or Gemini AI (accurate, rich insights)
3. **Advanced AI Features**: AI-powered match analysis with strengths/concerns/recommendations, resume bullet rewrites, and persistent AI suggestions
4. Sending notifications via Telegram and exporting to Google Sheets

## Architecture Quick Reference

```
src/
├── bot/telegram_bot.py      # Telegram bot commands and handlers
├── scheduler/job_scheduler.py # Job scheduling logic (uses Telegram JobQueue)
├── matching/
│   ├── engine.py            # Main matching orchestrator (dual-mode: NLP/Gemini)
│   ├── gemini_matcher.py    # AI-powered matching with Gemini LLM
│   ├── requirements.py      # StructuredRequirements & GeminiMatchResult dataclasses
│   ├── skills_matcher.py    # NLP-based skill matching (sentence-transformers)
│   └── skill_extractor.py   # Extracts skills from job descriptions
├── database/
│   ├── models.py            # SQLAlchemy models (Resume, JobPosting, MatchResult, LikedBullet, PerfLogs)
│   ├── crud.py              # Database operations
│   └── db.py                # Database connection
├── services/
│   └── performance_logger.py # Metric tracking for backend operations
backend/
├── routers/
│   ├── bullets.py           # Saved AI bullets management
│   ├── analysis.py          # AI Analysis endpoints
│   ├── analytics.py         # Performance summaries
└── ...
├── importers/
│   ├── apify_provider.py    # Fetches jobs from Apify LinkedIn scraper
│   ├── brightdata_provider.py # Fetches jobs from Bright Data
│   └── enrichment.py        # Parallel Gemini extraction (domains, summaries, requirements)
├── integrations/
│   ├── sheets_connector.py  # Google Sheets export
│   └── gemini_client.py     # Gemini AI client (google-genai)
└── config.py                # YAML + env var config loader (ENV_OVERRIDES)

Dockerfile                   # Multi-stage build (Node frontend + Python backend, CPU-only PyTorch)
railway.json                 # Railway deployment config (Dockerfile builder, healthcheck)
.dockerignore                # Excludes dev files but keeps frontend source for in-Docker build

frontend/src/
├── stores/searchStore.ts    # Zustand global state for job search
├── components/
│   ├── SearchStatusIndicator.tsx # Floating search progress indicator
│   └── analytics/           # Charts and performance tabs
├── pages/GetJobs.tsx        # Job search page (uses searchStore)
└── services/api.ts          # API client with React Query hooks
```

## Key Design Decisions

1. **Telegram JobQueue for Scheduling**: We use python-telegram-bot's built-in JobQueue instead of standalone APScheduler to avoid event loop conflicts with `run_polling()`.

2. **Single Keyword Profiles**: Each profile has one keyword to minimize API costs (1 call per search instead of N calls for N keywords).

3. **Markdown Escaping**: Dynamic content in Telegram messages must be escaped using `escape_markdown()` in `telegram_bot.py` to prevent parse errors.

4. **Dual-Mode Matching Engine**: Supports three modes via `matching.engine` config:
   - `"nlp"` - Fast, free NLP matching using sentence-transformers
   - `"gemini"` - Full AI matching with rich insights (strengths, concerns, recommendations)
   - `"auto"` (default) - Uses Gemini if available/configured, falls back to NLP

5. **NLP Match Score Formula**: `Overall = (Skills × 0.45) + (Experience × 0.35) + (Domains × 0.20)`. Handles missing data with neutral scores (0.5).

6. **AI Match Insights**: When using Gemini matcher, each match includes:
   - Component scores (skills, experience, seniority, domain)
   - Skill matches with confidence levels
   - Skill gaps with transferability analysis
   - Strengths, concerns, and application recommendations

7. **Location-Aware Matching**: Regular searches filter jobs by configured location (e.g., Canada). Remote searches skip location filtering since remote jobs can be listed from anywhere.

8. **Job Freshness Filter**: Only matches jobs posted within `max_job_age_days` (default: 7 days) to focus on recent listings and avoid stale month-old postings.

9. **Persistent AI Suggestions**: AI-generated bullet point rewrites are saved to the database (`MatchResult.bullet_suggestions`) automatically. This prevents re-running expensive LLM calls when revisiting a job match.

10. **Role-Aligned Suggestions**: Saved AI suggestions are mapped to resume roles using a composite key (`Company_Title`), ensuring they attach to the correct experience even if resume order changes.

11. **Domain Keys vs Names**: Resume domains MUST use standardized keys from `data/domain_expertise.json` (e.g., `"financial_services"`, `"b2b_saas"`), NOT human-readable names (e.g., `"Financial Services"`). The matching engine compares domains by exact key match. Using names will cause skill gaps to be incorrectly reported in analytics.

12. **Global Search State (Zustand)**: The "Get Jobs" search state is managed via Zustand (`frontend/src/stores/searchStore.ts`) so searches persist across page navigation. A floating `SearchStatusIndicator` shows progress on all pages when a search is running.

13. **Performance Logging**: All critical operations (Search, AI Analysis) are wrapped with `PerformanceLogger` contexts. Metrics are persisted to the database for the `/analytics/performance` dashboard.

14. **Environment Variable Config Overrides**: `src/config.py` checks env vars before YAML values via the `ENV_OVERRIDES` mapping. This enables Railway/cloud deployments where secrets are injected as env vars. Config.yaml is optional — if missing, the app runs on env vars and defaults only. Boolean coercion handles `"true"/"false"` strings automatically.

15. **Parallel Gemini Enrichment**: During job import, Gemini extraction (domains, summaries, requirements) runs concurrently across jobs using `ThreadPoolExecutor(max_workers=5)` via `src/importers/enrichment.py`. The existing `GeminiRateLimiter` (thread-safe `threading.Lock`) throttles calls to stay within Gemini rate limits. Both Apify and BrightData providers share this helper.
    - **3 separate calls per job (intentional)**: Domain extraction, summarization, and requirements extraction are kept as 3 individual Gemini calls rather than 1 combined call. Combining them into a single prompt was tested and significantly reduced extraction accuracy — focused single-task prompts produce better results. Do not attempt to merge these into one call to save API quota.

16. **Railway Deployment**: The app is deployed on Railway at `https://YOUR_APP.up.railway.app`. Uses a multi-stage Dockerfile (Node frontend build + CPU-only PyTorch + Python deps). PostgreSQL replaces SQLite in production. Railway sets `PORT` dynamically; the Dockerfile CMD uses `${PORT:-8000}`.

## Common Tasks

### Adding a New Telegram Command

1. Add handler in `TelegramBot.__init__()`:
   ```python
   self.application.add_handler(CommandHandler("newcmd", self.newcmd_command))
   ```

2. Implement the command method:
   ```python
   async def newcmd_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
       if not self._check_authorization(update):
           await update.message.reply_text("❌ You are not authorized.")
           return
       # Command logic here
       await update.message.reply_text("Response", parse_mode='Markdown')
   ```

3. Update `/help` message in `help_command()`

4. Update docs: `docs/TELEGRAM_BOT.md`, `docs/ARCHITECTURE.md`

### Modifying Match Algorithm

**NLP Matching (traditional)**:
- Skills matching: `src/matching/skills_matcher.py`
- Experience matching: `src/matching/engine.py` → `_calculate_experience_score()`
- Skill extraction dictionary: `src/matching/skill_extractor.py` → `SKILL_DICTIONARY`
- **Skill relationships**: `data/skill_relationships.json` (edit without code changes)

**AI Matching (Gemini)**:
- Matching prompts: `src/matching/gemini_matcher.py` → `MATCHING_PROMPT`
- Data structures: `src/matching/requirements.py` → `GeminiMatchResult`, `StructuredRequirements`
- Engine mode selection: `src/matching/engine.py` → `_should_use_gemini()`
- Requirements extraction: `src/integrations/gemini_client.py` → `GeminiRequirementsExtractor`

### Skill Relationships

Related skills receive partial credit (default 0.7x) during matching. Edit `data/skill_relationships.json` to add/modify relationships:

```json
{
  "config": {
    "related_skill_weight": 0.7
  },
  "relationships": {
    "technical": {
      "python": ["data science", "machine learning", "automation"],
      "sql": ["data analysis", "database", "analytics"]
    }
  }
}
```

### Adding New Configuration Options

1. Add to `config.yaml.example` with comments
2. Access via `self.config.get("section.key", default_value)` using `src/config.py`
3. For cloud-deployable secrets, add an entry to `ENV_OVERRIDES` in `src/config.py`
4. Set the env var on Railway: `railway variable set KEY=value --service launchpad`

## Important Patterns

### Telegram Message Formatting

Always escape dynamic content when using Markdown:
```python
from src.bot.telegram_bot import escape_markdown

# Bad - will break if profile_name contains underscores
msg = f"Profile: {profile_name}"

# Good
msg = f"Profile: {escape_markdown(profile_name)}"
```

### Database Sessions

Always use context manager or try/finally:
```python
session = SessionLocal()
try:
    # database operations
finally:
    session.close()
```

### Error Handling in Bot Commands

Wrap command logic in try/except to prevent silent failures:
```python
try:
    # command logic
except Exception as e:
    logger.error(f"Error in command: {e}", exc_info=True)
    await update.message.reply_text(f"❌ Error: {str(e)}")
```

## Testing

- Unit tests: `tests/` directory
- Manual bot testing: `python run_telegram_bot.py`
- Demo scripts: `run_matching_demo.py`, `quick_match_demo.py`

## Files to Update Together

When modifying features, these files often need synchronized updates:

| Change | Files to Update |
|--------|-----------------|
| New Telegram command | `telegram_bot.py`, `TELEGRAM_BOT.md`, `ARCHITECTURE.md`, `SCHEDULER.md` |
| New config option | `config.yaml.example`, `config.py` (+ `ENV_OVERRIDES`), relevant docs |
| Deployment config | `Dockerfile`, `railway.json`, `.dockerignore`, `docs/RAILWAY_DEPLOYMENT.md` |
| NLP matching algorithm | `engine.py`, `skills_matcher.py`, `ARCHITECTURE.md` |
| AI matching algorithm | `gemini_matcher.py`, `requirements.py`, `engine.py`, `ARCHITECTURE.md` |
| AI match insights UI | `api.ts` (types), `JobMatches.tsx`, `Dashboard.tsx` |
| Database schema | `models.py`, `crud.py`, may need migration |
| Job enrichment pipeline | `enrichment.py`, `apify_provider.py`, `brightdata_provider.py` |

## Deployment

- **Local**: `uvicorn backend.main:app --reload` (SQLite, frontend via Vite dev server)
- **Railway** (production): `https://YOUR_APP.up.railway.app`
  - Project: `rail-linkedin-project`, Service: `launchpad`
  - Database: Railway PostgreSQL (auto-referenced via `DATABASE_URL`)
  - All secrets as env vars (see `ENV_OVERRIDES` in `src/config.py`)
  - Deploy: `railway up --service launchpad` or push to `main` branch
  - Logs: `railway logs --service launchpad`
  - Guides: `docs/RAILWAY_DEPLOYMENT.md`, `ideas/railway_deployment.md`

### Dockerfile Notes
- 3-stage build: Node frontend → Python deps (CPU-only PyTorch) → slim production image
- `.dockerignore` keeps frontend source for in-Docker build (unlike pre-built approach)
- Single Gunicorn worker to stay within Railway memory limits
- `PRODUCTION=true` env var enables serving React build from `/frontend/dist/`

## Known Limitations

1. Resume parsing only supports plain text (.txt) and markdown (.md)
2. Apify API has rate limits and costs per call
3. Telegram bot can only run one instance at a time (polling conflict)
4. Google Sheets/Gmail OAuth tokens require local browser flow — not available on Railway without volume mounts

## Dependencies

Key packages and why they're used:
- `python-telegram-bot`: Telegram bot framework with JobQueue scheduling
- `sentence-transformers`: NLP embeddings for semantic skill matching
- `google-genai`: Google Gemini AI SDK
- `SQLAlchemy`: Database ORM
- `apify-client`: LinkedIn job data via Apify actors
- `google-api-python-client`: Google Sheets integration

**Frontend:**
- `zustand`: Lightweight global state management (search persistence)
- `@tanstack/react-query`: Server state caching and API calls
- `framer-motion`: Animations (SearchStatusIndicator, page transitions)
- `recharts`: Data visualization for Analytics/Performance charts
