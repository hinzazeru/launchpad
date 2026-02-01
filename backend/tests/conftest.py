import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# MOCKING MUST HAPPEN BEFORE IMPORTING APP
# Mock sentence-transformers dependent modules to avoid environment issues and slow loading
mock_role_analyzer = MagicMock()
mock_role_analyzer.RoleAnalyzer.return_value.analyze_role.return_value = {
    "alignment_score": 0.85,
    "matching_keywords": ["Python", "API"],
    "missing_keywords": ["Java"],
    "bullets_analysis": []
}
sys.modules["src.targeting.role_analyzer"] = mock_role_analyzer
sys.modules["src.targeting.role_analyzer.RoleAnalyzer"] = mock_role_analyzer.RoleAnalyzer

mock_bullet_rewriter = MagicMock()
mock_bullet_rewriter.BulletRewriter.return_value.is_available.return_value = True
mock_bullet_rewriter.BulletRewriter.return_value.rewrite_bullet.return_value = ["Option 1", "Option 2"]
sys.modules["src.targeting.bullet_rewriter"] = mock_bullet_rewriter

# Also mock engine if it uses sentence_transformers
mock_engine = MagicMock()
sys.modules["src.matching.engine"] = mock_engine

# Now imports can proceed safely
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from src.database.db import get_db, Base
from src.database.models import JobPosting, Resume, MatchResult

# Use in-memory SQLite database for tests with shared cache
# This ensures all connections see the same data
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:?cache=shared"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def test_resume_dir(tmp_path):
    """Create a temporary directory with test resume files."""
    resume_dir = tmp_path / "resumes"
    resume_dir.mkdir()

    # Create test resume files that tests expect
    test_files = [
        "test_resume.txt",
        "test.txt",
        "resume.txt",
        "test_resume.md",
    ]
    for filename in test_files:
        (resume_dir / filename).write_text("# Test Resume\n\n## Skills\n- Python\n- FastAPI")

    return resume_dir


@pytest.fixture(scope="function")
def client(db_session, test_resume_dir):
    """Create test client - uses function scope for proper isolation."""
    # Patch the RESUME_LIBRARY_DIR in the scheduler router
    with patch("backend.routers.scheduler.RESUME_LIBRARY_DIR", test_resume_dir):
        with TestClient(app) as c:
            yield c


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    # Create tables fresh for each test
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop all tables after test
        Base.metadata.drop_all(bind=engine)
