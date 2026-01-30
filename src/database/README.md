# Database Module

SQLAlchemy-based data persistence layer for jobs, resumes, and match results.

## Overview

This module handles all database operations using SQLAlchemy ORM. Default storage is SQLite, but PostgreSQL is supported for production deployments.

## Files

| File | Purpose |
|------|---------|
| `models.py` | SQLAlchemy model definitions (Resume, JobPosting, MatchResult) |
| `crud.py` | Create, Read, Update, Delete operations |
| `db.py` | Database connection and session management |

## Models

### Resume

Stores user's professional profile for matching.

```python
class Resume:
    id: int
    name: str                    # Resume identifier
    skills: List[str]            # Technical/soft skills
    experience_years: int        # Years of experience
    job_titles: List[str]        # Previous job titles
    education: List[str]         # Educational background
    raw_text: str                # Original resume text
    created_at: datetime
    updated_at: datetime
```

### JobPosting

Stores job listings fetched from LinkedIn.

```python
class JobPosting:
    id: int
    title: str                   # Job title
    company: str                 # Company name
    location: str                # Job location
    description: str             # Full job description
    url: str                     # LinkedIn job URL
    posted_date: datetime        # When job was posted
    source: str                  # Data source (e.g., "apify")
    created_at: datetime
```

### MatchResult

Stores matching results between jobs and resumes.

```python
class MatchResult:
    id: int
    job_id: int                  # FK to JobPosting
    resume_id: int               # FK to Resume
    match_score: float           # Overall score (0-100)
    skills_score: float          # Skills component score
    experience_score: float      # Experience component score
    matching_skills: List[str]   # Skills that matched
    skill_gaps: List[str]        # Skills job requires but resume lacks
    engine_version: str          # Matching algorithm version
    notified_at: datetime        # When user was notified (for dedup)
    generated_date: datetime     # When match was calculated
```

## Usage Examples

### Creating a Session

```python
from src.database.db import SessionLocal

session = SessionLocal()
try:
    # database operations
    session.commit()
finally:
    session.close()
```

### CRUD Operations

```python
from src.database import crud
from src.database.db import SessionLocal

session = SessionLocal()

# Create
resume = crud.create_resume(session, name="My Resume", skills=["Python", "SQL"])

# Read
job = crud.get_job_posting(session, job_id=123)
jobs = crud.get_recent_jobs(session, days=7)

# Query matches
matches = crud.get_matches_by_score(session, min_score=70)

# Update
crud.update_match_notified(session, match_id=456)

# Delete
crud.delete_old_matches(session, days=30)

session.close()
```

### Deduplication

Jobs are deduplicated by title + company:

```python
existing = crud.get_job_by_title_company(session, title, company)
if existing:
    # Skip or update
else:
    # Create new
```

## Configuration

In `config.yaml`:

```yaml
database:
  url: "sqlite:///linkedin_job_matcher.db"
  # For PostgreSQL:
  # url: "postgresql://user:password@localhost/dbname"
```

## Migration Notes

When changing models:

1. Update model in `models.py`
2. For SQLite (dev): Delete `.db` file and restart
3. For PostgreSQL (prod): Use Alembic migrations

## Relationships

```
Resume ──┬── MatchResult ──┬── JobPosting
         │                 │
         └─ (1:many) ──────┘
```

- One Resume can have many MatchResults
- One JobPosting can have many MatchResults
- MatchResult links Resume to JobPosting with scores

## Cloud Deployment

**Important**: SQLite doesn't persist on most cloud platforms (ephemeral filesystem).

For production, use PostgreSQL:

```yaml
database:
  url: "postgresql://user:pass@host:5432/dbname"
```

Cloud providers like Railway, Render, and Fly.io offer managed PostgreSQL.
