"""SQLAlchemy database models."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, JSON, ForeignKey, Index, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from src.database.db import Base


class Resume(Base):
    """Resume model for storing user resume data."""

    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    skills = Column(JSON, nullable=False)  # List of skills
    experience_years = Column(Float, nullable=True)
    job_titles = Column(JSON, nullable=True)  # List of previous job titles
    education = Column(Text, nullable=True)
    domains = Column(JSON, nullable=True)  # List of domain expertise (e.g., ["fintech", "b2b_saas"])
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    match_results = relationship("MatchResult", back_populates="resume")

    def __repr__(self):
        return f"<Resume(id={self.id}, skills_count={len(self.skills) if self.skills else 0})>"


class JobPosting(Base):
    """Job posting model for storing job data."""

    __tablename__ = "job_postings"
    __table_args__ = (
        UniqueConstraint('title', 'company', name='uq_job_postings_title_company'),
        Index('ix_job_postings_title_company', 'title', 'company'),
    )

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    company = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    required_skills = Column(JSON, nullable=True)  # List of required skills
    experience_required = Column(Float, nullable=True)  # Years of experience
    posting_date = Column(DateTime, nullable=False, index=True)
    import_date = Column(DateTime, default=datetime.utcnow)
    source = Column(String(100), nullable=True)  # e.g., "api", "csv", "pdf"
    url = Column(String(500), nullable=True)
    location = Column(String(255), nullable=True)
    salary = Column(String(100), nullable=True)  # Extracted salary info (e.g., "$120K-$150K")
    required_domains = Column(JSON, nullable=True)  # List of required domain expertise (e.g., ["ecommerce", "headless_cms"])
    domain_extraction_method = Column(String(20), nullable=True)  # "keyword" or "llm" - tracks how domains were extracted
    summary = Column(Text, nullable=True)  # LLM-generated summary of the job description

    # Structured requirements for LLM matching
    structured_requirements = Column(JSON, nullable=True)  # StructuredRequirements dict
    requirements_extracted_at = Column(DateTime, nullable=True)
    requirements_extraction_model = Column(String(50), nullable=True)  # e.g., "gemini-2.0-flash"

    # Relationships
    match_results = relationship("MatchResult", back_populates="job_posting")
    application_tracking = relationship(
        "ApplicationTracking", back_populates="job_posting", uselist=False
    )

    def __repr__(self):
        return f"<JobPosting(id={self.id}, title='{self.title}', company='{self.company}')>"


class MatchResult(Base):
    """Match result model for storing job-resume matching scores."""

    __tablename__ = "match_results"
    __table_args__ = (
        Index('ix_match_score_date', 'match_score', 'generated_date'),
    )

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("job_postings.id"), nullable=False, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False, index=True)
    match_score = Column(Float, nullable=False, index=True)  # 0-100 score
    matching_skills = Column(JSON, nullable=True)  # List of matched skills
    experience_alignment = Column(Text, nullable=True)  # Experience match description
    missing_domains = Column(JSON, nullable=True)  # List of required domains candidate lacks
    generated_date = Column(DateTime, default=datetime.utcnow, index=True)
    engine_version = Column(String(20), nullable=True)  # Matching engine version (e.g., "1.0.0")
    notified_at = Column(DateTime, nullable=True, index=True)  # When user was notified via Telegram
    gemini_score = Column(Float, nullable=True)  # Gemini re-ranking score (0-100)
    gemini_reasoning = Column(Text, nullable=True)  # Gemini's explanation for the match quality
    gemini_strengths = Column(JSON, nullable=True)  # AI-identified candidate strengths
    gemini_gaps = Column(JSON, nullable=True)  # AI-identified candidate gaps
    bullet_suggestions = Column(JSON, nullable=True)  # Saved AI bullet suggestions

    # LLM-based matching scores (new AI matching system)
    ai_match_score = Column(Float, nullable=True)  # Primary AI score (0-100)
    skills_score = Column(Float, nullable=True)  # Skills component score (0-100)
    experience_score = Column(Float, nullable=True)  # Experience fit score (0-100)
    seniority_fit = Column(Float, nullable=True)  # Seniority alignment score (0-100)
    domain_score = Column(Float, nullable=True)  # Domain relevance score (0-100)

    # Rich AI insights
    ai_strengths = Column(JSON, nullable=True)  # ["Strong PM background", ...]
    ai_concerns = Column(JSON, nullable=True)  # ["Missing cloud certifications", ...]
    ai_recommendations = Column(JSON, nullable=True)  # ["Highlight scaling experience", ...]

    # Detailed skill analysis
    skill_matches = Column(JSON, nullable=True)  # [{job_skill, resume_skill, confidence}]
    skill_gaps_detailed = Column(JSON, nullable=True)  # [{skill, importance, transferable_from}]

    # Matching metadata
    match_engine = Column(String(20), default="nlp")  # "nlp" or "gemini"
    match_confidence = Column(Float, nullable=True)  # Model confidence (0-1)

    # Relationships
    job_posting = relationship("JobPosting", back_populates="match_results")
    resume = relationship("Resume", back_populates="match_results")

    def __repr__(self):
        return f"<MatchResult(id={self.id}, job_id={self.job_id}, score={self.match_score})>"


class ApplicationTracking(Base):
    """Application tracking model for tracking job application status."""

    __tablename__ = "application_tracking"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(
        Integer, ForeignKey("job_postings.id"), nullable=False, unique=True, index=True
    )
    status = Column(
        String(50), nullable=False, default="Saved", index=True
    )  # Saved, Applied, Interviewing, Rejected, Offer
    status_date = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)

    # Relationships
    job_posting = relationship("JobPosting", back_populates="application_tracking")

    def __repr__(self):
        return f"<ApplicationTracking(id={self.id}, job_id={self.job_id}, status='{self.status}')>"


class LikedBullet(Base):
    """Model for storing liked/saved bullet points from AI suggestions."""

    __tablename__ = "liked_bullets"

    id = Column(Integer, primary_key=True, index=True)
    original_text = Column(Text, nullable=False)
    rewritten_text = Column(Text, nullable=False)
    # Context
    role_title = Column(String(255), nullable=True, index=True)  # Indexed for filtering
    company = Column(String(255), nullable=True)
    job_id = Column(Integer, ForeignKey("job_postings.id"), nullable=True, index=True)  # Indexed for lookups

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    job_posting = relationship("JobPosting")

    def __repr__(self):
        return f"<LikedBullet(id={self.id}, company='{self.company}')>"


class ScheduledSearch(Base):
    """Model for storing scheduled job search configurations."""

    __tablename__ = "scheduled_searches"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)  # e.g., "Morning PM Search"
    keyword = Column(String(200), nullable=False)
    location = Column(String(200), default="Canada")
    job_type = Column(String(50), nullable=True)
    experience_level = Column(String(50), nullable=True)
    work_arrangement = Column(String(50), nullable=True)
    max_results = Column(Integer, default=25)
    resume_filename = Column(String(255), nullable=False)
    export_to_sheets = Column(Boolean, default=True)

    # Schedule config (fixed times approach)
    enabled = Column(Boolean, default=True, index=True)
    run_times = Column(JSON, default=["08:00", "12:00", "16:00", "20:00"])  # Daily times
    timezone = Column(String(50), default="America/Toronto")

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    last_run_status = Column(String(20), nullable=True)  # 'success' | 'error'
    max_retries = Column(Integer, default=2)
    retry_delay_minutes = Column(Integer, default=10)

    # Relationships
    search_runs = relationship("SearchPerformance", back_populates="scheduled_search")

    def __repr__(self):
        return f"<ScheduledSearch(id={self.id}, name='{self.name}', keyword='{self.keyword}', enabled={self.enabled})>"


class SearchPerformance(Base):
    """Model for tracking high-level job search performance metrics."""
    __tablename__ = "search_performance"

    id = Column(Integer, primary_key=True, index=True)
    search_id = Column(String(36), unique=True, index=True)  # UUID
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    status = Column(String(20))  # success, error, cancelled

    # Trigger tracking
    trigger_source = Column(String(20), default='manual', index=True)  # 'manual' | 'scheduled'
    schedule_id = Column(Integer, ForeignKey("scheduled_searches.id"), nullable=True, index=True)

    # High-level stage timings (ms)
    total_duration_ms = Column(Integer, nullable=True)
    initialize_ms = Column(Integer, nullable=True)
    fetch_ms = Column(Integer, nullable=True)
    import_ms = Column(Integer, nullable=True)
    match_ms = Column(Integer, nullable=True)
    export_ms = Column(Integer, nullable=True)

    # Sub-component timings (ms) - nullable
    apify_api_ms = Column(Integer, nullable=True)
    db_import_ms = Column(Integer, nullable=True)
    skills_extraction_ms = Column(Integer, nullable=True)
    nlp_embedding_ms = Column(Integer, nullable=True)
    gemini_rerank_ms = Column(Integer, nullable=True)
    sheets_export_ms = Column(Integer, nullable=True)

    # Counts
    jobs_fetched = Column(Integer, default=0)
    jobs_imported = Column(Integer, default=0)
    jobs_matched = Column(Integer, default=0)
    high_matches = Column(Integer, default=0)
    gemini_calls = Column(Integer, default=0)

    # Error tracking
    error_stage = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    scheduled_search = relationship("ScheduledSearch", back_populates="search_runs")

    def __repr__(self):
        return f"<SearchPerformance(id={self.id}, status='{self.status}', duration={self.total_duration_ms}ms)>"


class APICallMetric(Base):
    """Model for tracking individual API call performance."""
    __tablename__ = "api_call_metrics"
    __table_args__ = (
        Index('ix_call_type_created', 'call_type', 'created_at'),
    )

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    call_type = Column(String(50), index=True)  # gemini_rerank, gemini_suggestions, apify_search, sheets_export
    duration_ms = Column(Integer)
    status = Column(String(20))  # success, error, timeout

    # Optional context
    search_id = Column(String(36), nullable=True, index=True)
    tokens_used = Column(Integer, nullable=True)  # For Gemini calls
    error_message = Column(Text, nullable=True)

    def __repr__(self):
        return f"<APICallMetric(id={self.id}, type='{self.call_type}', duration={self.duration_ms}ms)>"


class SearchJob(Base):
    """Model for tracking background job search execution.

    This model enables the background job queue architecture where:
    - POST /search/jobs returns immediately with a search_id
    - Backend runs search in background, persists progress here
    - Frontend polls GET /search/jobs/{search_id} for updates
    - Results are always retrievable, even after browser disconnection
    """
    __tablename__ = "search_jobs"
    __table_args__ = (
        Index('ix_search_jobs_status_created', 'status', 'created_at'),
    )

    id = Column(Integer, primary_key=True, index=True)
    search_id = Column(String(36), unique=True, nullable=False, index=True)  # UUID
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Status tracking
    status = Column(String(20), default='pending', index=True)  # pending, running, completed, failed
    stage = Column(String(20), default='initializing')  # initializing, fetching, importing, matching, exporting, completed, error
    progress = Column(Integer, default=0)  # 0-100
    message = Column(String(500), nullable=True)

    # Request parameters (stored for reference)
    keyword = Column(String(200), nullable=False)
    location = Column(String(200), nullable=True)
    job_type = Column(String(50), nullable=True)
    experience_level = Column(String(50), nullable=True)
    work_arrangement = Column(String(50), nullable=True)
    max_results = Column(Integer, default=25)
    resume_filename = Column(String(255), nullable=False)
    export_to_sheets = Column(Boolean, default=True)

    # Progress counters
    jobs_found = Column(Integer, nullable=True)
    jobs_imported = Column(Integer, nullable=True)
    matches_found = Column(Integer, nullable=True)
    high_matches = Column(Integer, nullable=True)
    exported_count = Column(Integer, nullable=True)

    # Final results (JSON blob when completed)
    result = Column(JSON, nullable=True)  # Full SearchResult dict

    # Error tracking
    error = Column(Text, nullable=True)

    # Trigger tracking
    trigger_source = Column(String(20), default='manual')  # 'manual' or 'scheduled'
    schedule_id = Column(Integer, ForeignKey("scheduled_searches.id"), nullable=True)

    # Cancellation
    cancellation_requested = Column(Boolean, default=False)

    # Cleanup tracking
    expires_at = Column(DateTime, nullable=True)  # For auto-cleanup after 24 hours

    def __repr__(self):
        return f"<SearchJob(id={self.id}, search_id='{self.search_id}', status='{self.status}', progress={self.progress}%)>"
