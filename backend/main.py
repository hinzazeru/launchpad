"""FastAPI backend for Resume Bullet Point Targeter.

This API provides endpoints for job management, resume handling,
and AI-powered resume analysis and suggestions.
"""

import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.routers import jobs, resumes, analysis, search, bullets, analytics, domains, scheduler
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


# ============================================================================
# Lifecycle Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup."""
    import logging
    logger = logging.getLogger(__name__)
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
