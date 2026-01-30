# AI Assistant Context - LinkedIn Job Matcher

This file provides context for AI assistants (Claude, GPT, Copilot, etc.) working on this codebase.

## Project Overview

LinkedIn Job Matcher is a Python application that automates job discovery by:
1. Fetching job postings from LinkedIn via Apify API
2. Matching jobs against a user's resume using NLP
3. **Advanced AI Features**: Rewriting resume bullets for specific jobs, saving liked rewrites, and persisting AI analysis.
4. Sending notifications via Telegram and exporting to Google Sheets

## Architecture Quick Reference

```
src/
├── bot/telegram_bot.py      # Telegram bot commands and handlers
├── scheduler/job_scheduler.py # Job scheduling logic (uses Telegram JobQueue)
├── matching/
│   ├── engine.py            # Main matching orchestrator
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
├── importers/api_importer.py # Fetches jobs from Apify LinkedIn scraper
├── integrations/
│   ├── sheets_connector.py  # Google Sheets export
│   └── gemini_client.py     # Gemini AI client (google-generativeai)
└── config.py                # YAML config loader

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

4. **Match Score Formula**: `Overall = (Skills × 0.45) + (Experience × 0.35) + (Domains × 0.20)`. Handles missing data with neutral scores (0.5).

5. **Location-Aware Matching**: Regular searches filter jobs by configured location (e.g., Canada). Remote searches skip location filtering since remote jobs can be listed from anywhere.

6. **Job Freshness Filter**: Only matches jobs posted within `max_job_age_days` (default: 7 days) to focus on recent listings and avoid stale month-old postings.

7. **Persistent AI Suggestions**: AI-generated bullet point rewrites are saved to the database (`MatchResult.bullet_suggestions`) automatically. This prevents re-running expensive LLM calls when revisiting a job match.

8. **Role-Aligned Suggestions**: Saved AI suggestions are mapped to resume roles using a composite key (`Company_Title`), ensuring they attach to the correct experience even if resume order changes.

9. **Global Search State (Zustand)**: The "Get Jobs" search state is managed via Zustand (`frontend/src/stores/searchStore.ts`) so searches persist across page navigation. A floating `SearchStatusIndicator` shows progress on all pages when a search is running.

10. **Performance Logging**: All critical operations (Search, AI Analysis) are wrapped with `PerformanceLogger` contexts. Metrics are persisted to SQLite for the `/analytics/performance` dashboard.

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

- Skills matching: `src/matching/skills_matcher.py`
- Experience matching: `src/matching/engine.py` → `_calculate_experience_score()`
- Skill extraction dictionary: `src/matching/skill_extractor.py` → `SKILL_DICTIONARY`
- **Skill relationships**: `data/skill_relationships.json` (edit without code changes)

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
| New config option | `config.yaml.example`, `config.py`, relevant docs |
| Matching algorithm | `engine.py`, `skills_matcher.py`, `ARCHITECTURE.md` |
| Database schema | `models.py`, `crud.py`, may need migration |

## Known Limitations

1. Resume parsing only supports plain text (.txt) and markdown (.md)
2. SQLite doesn't persist across cloud deployments (use PostgreSQL for production)
3. Apify API has rate limits and costs per call
4. Telegram bot can only run one instance at a time (polling conflict)

## Dependencies

Key packages and why they're used:
- `python-telegram-bot`: Telegram bot framework with JobQueue scheduling
- `sentence-transformers`: NLP embeddings for semantic skill matching
- `google-generativeai`: Google Gemini AI SDK
- `SQLAlchemy`: Database ORM
- `apify-client`: LinkedIn job data via Apify actors
- `google-api-python-client`: Google Sheets integration

**Frontend:**
- `zustand`: Lightweight global state management (search persistence)
- `@tanstack/react-query`: Server state caching and API calls
- `framer-motion`: Animations (SearchStatusIndicator, page transitions)
- `recharts`: Data visualization for Analytics/Performance charts
