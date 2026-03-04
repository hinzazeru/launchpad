"""FastAPI backend for Resume Bullet Point Targeter.

This API provides endpoints for job management, resume handling,
and AI-powered resume analysis and suggestions.
"""

import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from backend.limiter import limiter

# Configure root logger so all app loggers output to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.routers import jobs, resumes, analysis, search, bullets, analytics, domains, scheduler, admin
from src.database.db import init_db
from backend.services.webapp_scheduler import init_scheduler, shutdown_scheduler

# Initialize database
init_db()

# Check if we're in production mode (serving React build)
PRODUCTION = os.getenv("PRODUCTION", "false").lower() == "true"
frontend_build = project_root / "frontend" / "dist"

app = FastAPI(
    title="LaunchPad 💸 API",
    description="API for analyzing resumes against job descriptions and generating AI-powered suggestions",
    version="1.0.0"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS middleware for React frontend (only needed in dev mode)
if not PRODUCTION:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # Vite dev server
            "http://localhost:3000",  # Alternative dev server
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include routers
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(resumes.router, prefix="/api/resumes", tags=["resumes"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(bullets.router, prefix="/api/bullets", tags=["bullets"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(domains.router, prefix="/api/domains", tags=["domains"])
app.include_router(scheduler.router, prefix="/api/scheduler", tags=["scheduler"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])


# ============================================================================
# Lifecycle Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup."""
    logger = logging.getLogger(__name__)

    # Run pending database migrations before any ORM queries
    try:
        from sqlalchemy import text
        from src.database.db import engine

        migrations = [
            # add_rematch_tracking (may already exist from earlier deploy)
            ("scheduled_searches", "resume_content_hash", "VARCHAR(64)"),
            ("scheduled_searches", "last_engine_version", "VARCHAR(20)"),
            # add_search_analytics_columns
            ("search_performance", "gemini_attempted", "INTEGER"),
            ("search_performance", "gemini_succeeded", "INTEGER"),
            ("search_performance", "gemini_failed", "INTEGER"),
            ("search_performance", "gemini_failure_reasons", "TEXT"),
            ("search_performance", "rematch_type", "VARCHAR(30)"),
            ("search_performance", "jobs_skipped", "INTEGER"),
            ("search_performance", "gemini_timing_summary", "TEXT"),
            # weekdays_only toggle for scheduled searches
            ("scheduled_searches", "weekdays_only", "BOOLEAN DEFAULT FALSE"),
            # user curation (heart/ignore) on match results
            ("match_results", "user_status", "VARCHAR(20)"),
            # repost detection
            ("job_postings", "is_repost", "BOOLEAN DEFAULT FALSE"),
            ("job_postings", "repost_count", "INTEGER DEFAULT 0"),
        ]

        with engine.connect() as conn:
            for table, col, col_type in migrations:
                try:
                    # Check if column exists (PostgreSQL)
                    result = conn.execute(text(
                        f"SELECT column_name FROM information_schema.columns "
                        f"WHERE table_name = '{table}' AND column_name = '{col}'"
                    ))
                    if result.fetchone() is None:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                        logger.info(f"Migration: added {table}.{col}")
                except Exception as col_err:
                    logger.debug(f"Migration skip {table}.{col}: {col_err}")
            conn.commit()
    except Exception as e:
        logger.warning(f"Auto-migration check failed (non-fatal): {e}")

    # Clean up stale search jobs left running from a previous crash/restart
    try:
        from src.database.db import SessionLocal
        from src.database.models import SearchJob, ScheduledSearch
        db = SessionLocal()

        # Mark stale web searches as failed
        stale = db.query(SearchJob).filter(SearchJob.status.in_(['running', 'pending'])).all()
        for job in stale:
            job.status = 'failed'
            job.error = 'Server restarted while search was in progress'
            logger.warning(f"Marked stale search {job.search_id} as failed")
        if stale:
            db.commit()

        # Check for scheduled searches that were interrupted (last_run_status still not set)
        # and send failure notification via Telegram
        stale_schedules = db.query(ScheduledSearch).filter(
            ScheduledSearch.last_run_status == 'running'
        ).all()
        for sched in stale_schedules:
            sched.last_run_status = 'error'
            logger.warning(f"Marked stale schedule '{sched.name}' as error (worker was killed)")
        if stale_schedules:
            db.commit()
            # Send Telegram notification for crashed scheduled searches
            try:
                from src.config import get_config
                import aiohttp
                config = get_config()
                bot_token = config.get("telegram.bot_token")
                chat_id = config.get("telegram.chat_id")
                if bot_token and chat_id:
                    for sched in stale_schedules:
                        message = (
                            f"❌ Scheduled Search Crashed: \"{sched.name}\"\n\n"
                            f"The worker was killed (timeout) during execution.\n"
                            f"The search has been marked as failed."
                        )
                        async with aiohttp.ClientSession() as session:
                            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                            await session.post(url, json={
                                'chat_id': chat_id,
                                'text': message,
                            })
                        logger.info(f"Sent crash notification for schedule '{sched.name}'")
            except Exception as notify_err:
                logger.error(f"Failed to send crash notification: {notify_err}")

        db.close()
    except Exception as e:
        logger.error(f"Failed to clean up stale searches: {e}")

    try:
        init_scheduler()
        logger.info("Scheduler service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize scheduler: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup services on application shutdown."""
    import logging
    logger = logging.getLogger(__name__)
    try:
        shutdown_scheduler()
        logger.info("Scheduler service stopped")
    except Exception as e:
        logger.error(f"Error during scheduler shutdown: {e}")


@app.get("/api/health")
async def health_check():
    """Detailed health check with service status."""
    from src.targeting.bullet_rewriter import BulletRewriter

    rewriter = BulletRewriter()

    return {
        "status": "ok",
        "production": PRODUCTION,
        "services": {
            "database": "connected",
            "gemini": "available" if rewriter.is_available() else "not configured"
        }
    }


# Production mode: Serve React build
if PRODUCTION and frontend_build.exists():
    # Mount static assets
    app.mount("/assets", StaticFiles(directory=str(frontend_build / "assets")), name="assets")

    # Serve index.html for all non-API routes (SPA routing)
    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """Serve React SPA for all non-API routes."""
        # Check if it's a static file
        file_path = frontend_build / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        # Otherwise serve index.html for client-side routing
        return FileResponse(frontend_build / "index.html")
else:
    @app.get("/")
    async def root():
        """Health check endpoint (dev mode only)."""
        return {"status": "ok", "message": "LaunchPad 💸 API", "mode": "development"}


if __name__ == "__main__":
    import uvicorn
    # When running with reload, we must pass the app as a string
    # and ensure the module can be imported
    if os.getcwd() not in sys.path:
        sys.path.append(os.getcwd())
    
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=not PRODUCTION)
