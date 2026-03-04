"""Analytics router for Resume Targeter API.

Provides aggregated analytics data for the dashboard:
- Summary metrics (cards)
- Skills analysis (gaps, matches, in-demand)
- Market research (companies, locations)
- Activity timeline
- Performance metrics
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import Counter
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from statistics import quantiles
import threading
import logging
import time

from src.database.db import get_db
from src.database.models import JobPosting, MatchResult, SearchPerformance, APICallMetric, ScheduledSearch
from backend.limiter import limiter

router = APIRouter()
logger = logging.getLogger(__name__)

# Thread-safe in-memory cache with TTL (1 hour)
_cache: Dict[str, tuple] = {}
_cache_lock = threading.Lock()
CACHE_TTL_SECONDS = 3600


def _get_cached(key: str):
    """Get value from cache if not expired (thread-safe)."""
    with _cache_lock:
        if key in _cache:
            value, timestamp = _cache[key]
            if time.time() - timestamp < CACHE_TTL_SECONDS:
                return value
    return None


def _set_cached(key: str, value):
    """Set value in cache with current timestamp (thread-safe)."""
    with _cache_lock:
        _cache[key] = (value, time.time())


# --- Response Models ---

class SummaryMetrics(BaseModel):
    """Summary metrics for the top row cards."""
    total_jobs: int
    high_matches: int
    ai_analysed: int
    avg_score: float


class SkillCount(BaseModel):
    """A skill with its occurrence count."""
    name: str
    count: int


class SkillsAnalytics(BaseModel):
    """Skills-related analytics data."""
    skill_gaps: List[SkillCount]  # Missing domains from high matches
    matching_skills: List[SkillCount]  # Skills driving matches
    in_demand_skills: List[SkillCount]  # Required skills from all jobs


class CompanyCount(BaseModel):
    """A company with job count."""
    name: str
    count: int


class LocationCount(BaseModel):
    """A location with job count."""
    name: str
    count: int


class MarketAnalytics(BaseModel):
    """Market research analytics data."""
    top_companies: List[CompanyCount]
    locations: List[LocationCount]


class TimelinePoint(BaseModel):
    """A single point in the timeline."""
    date: str  # ISO date string (YYYY-MM-DD)
    jobs_fetched: int
    matches_generated: int


class TimelineAnalytics(BaseModel):
    """Activity timeline data."""
    points: List[TimelinePoint]


class LatencyMetric(BaseModel):
    """Latency distribution for an API or pipeline stage."""
    name: str
    avg_ms: float
    p50_ms: float
    p90_ms: float
    p99_ms: float
    count: int


class PerformanceSummary(BaseModel):
    """High-level system performance metrics."""
    avg_search_duration_ms: float
    avg_gemini_latency_ms: float
    search_success_rate: float
    total_searches_30d: int
    total_api_calls_30d: int
    latencies: List[LatencyMetric]


class PerformanceTimelinePoint(BaseModel):
    """A single point in the performance timeline."""
    date: str
    avg_ms: float
    count: int


class PerformanceTimeline(BaseModel):
    """Performance timeline data."""
    points: List[PerformanceTimelinePoint]


class StageMetric(BaseModel):
    """Timing metric for a pipeline stage."""
    avg_ms: float
    pct: float


class PerformanceBreakdown(BaseModel):
    """Stage-by-stage timing breakdown."""
    stages: Dict[str, StageMetric]


class MatchingDistributionPoint(BaseModel):
    """A single point in the matching distribution timeline."""
    date: str
    nlp_count: int
    gemini_count: int


class MatchingDistribution(BaseModel):
    """Matching distribution timeline data."""
    points: List[MatchingDistributionPoint]


class ApiLatencyDetail(BaseModel):
    """Detailed latency percentiles for an API type."""
    p50: float
    p90: float
    p99: float
    count: int


class RecentSearch(BaseModel):
    """A recent search result for the table."""
    search_id: str
    created_at: str
    total_duration_ms: Optional[int]
    jobs_fetched: int
    jobs_matched: int
    high_matches: int
    status: str
    error_message: Optional[str]
    trigger_source: str = "manual"  # 'manual' or 'scheduled'
    schedule_name: Optional[str] = None
    rematch_type: Optional[str] = None
    gemini_attempted: Optional[int] = None
    gemini_succeeded: Optional[int] = None
    gemini_failed: Optional[int] = None
    jobs_skipped: Optional[int] = None


class RecentSearchesResponse(BaseModel):
    """Response for recent searches endpoint."""
    searches: List[RecentSearch]


class GeminiUsageDay(BaseModel):
    """Daily Gemini API usage breakdown."""
    date: str  # YYYY-MM-DD
    matching: int
    rerank: int
    suggestions: int
    total: int


class GeminiUsageTotals(BaseModel):
    """Total Gemini usage counts."""
    matching: int
    rerank: int
    suggestions: int
    total: int


class GeminiUsageResponse(BaseModel):
    """Response for Gemini usage endpoint."""
    data: List[GeminiUsageDay]
    totals: GeminiUsageTotals



# --- Endpoints ---

@router.get("/summary", response_model=SummaryMetrics)
@limiter.limit("200/minute")
async def get_summary(request: Request, session: Session = Depends(get_db)):
    """Get summary metrics for the analytics cards.

    Returns:
    - total_jobs: Total number of jobs scanned
    - high_matches: Jobs with match score > 70%
    - ai_analysed: Jobs re-ranked by Gemini
    - avg_score: Average match score
    """
    cached = _get_cached("summary")
    if cached:
        return cached

    total_jobs = session.query(JobPosting).count()

    high_matches = (
        session.query(MatchResult)
        .filter(MatchResult.match_score > 70)
        .count()
    )

    ai_analysed = (
        session.query(MatchResult)
        .filter(MatchResult.gemini_score.isnot(None))
        .count()
    )

    avg_score_result = session.query(func.avg(MatchResult.match_score)).scalar()
    avg_score = round(float(avg_score_result), 1) if avg_score_result else 0.0

    result = SummaryMetrics(
        total_jobs=total_jobs,
        high_matches=high_matches,
        ai_analysed=ai_analysed,
        avg_score=avg_score
    )

    _set_cached("summary", result)
    return result


@router.get("/skills", response_model=SkillsAnalytics)
@limiter.limit("200/minute")
async def get_skills_analytics(
    request: Request,
    top_n: int = 10,
    session: Session = Depends(get_db)
):
    """Get skills-related analytics.

    Returns:
    - skill_gaps: Most common missing domains from high-match jobs (>60%)
    - matching_skills: Skills that are driving your matches
    - in_demand_skills: Most requested skills across all jobs
    """
    cache_key = f"skills_{top_n}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    # 1. Skill Gaps - aggregate missing_domains from high matches
    high_matches = (
        session.query(MatchResult.missing_domains)
        .filter(MatchResult.match_score > 60)
        .filter(MatchResult.missing_domains.isnot(None))
        .all()
    )

    gap_counter = Counter()
    for (domains,) in high_matches:
        if domains:
            for domain in domains:
                gap_counter[domain] += 1

    skill_gaps = [
        SkillCount(name=name, count=count)
        for name, count in gap_counter.most_common(top_n)
    ]

    # 2. Matching Skills - aggregate from MatchResult.matching_skills
    all_matches = (
        session.query(MatchResult.matching_skills)
        .filter(MatchResult.matching_skills.isnot(None))
        .all()
    )

    match_counter = Counter()
    for (skills,) in all_matches:
        if skills:
            for skill in skills:
                match_counter[skill] += 1

    matching_skills = [
        SkillCount(name=name, count=count)
        for name, count in match_counter.most_common(top_n)
    ]

    # 3. In-Demand Skills - aggregate from JobPosting.required_skills
    all_jobs = (
        session.query(JobPosting.required_skills)
        .filter(JobPosting.required_skills.isnot(None))
        .all()
    )

    demand_counter = Counter()
    for (skills,) in all_jobs:
        if skills:
            for skill in skills:
                demand_counter[skill] += 1

    in_demand_skills = [
        SkillCount(name=name, count=count)
        for name, count in demand_counter.most_common(top_n)
    ]

    result = SkillsAnalytics(
        skill_gaps=skill_gaps,
        matching_skills=matching_skills,
        in_demand_skills=in_demand_skills
    )

    _set_cached(cache_key, result)
    return result


@router.get("/market", response_model=MarketAnalytics)
@limiter.limit("200/minute")
async def get_market_analytics(
    request: Request,
    top_n: int = 10,
    min_score: float = 60,
    session: Session = Depends(get_db)
):
    """Get market research analytics.

    Args:
    - top_n: Number of top items to return
    - min_score: Minimum match score to filter jobs

    Returns:
    - top_companies: Companies with most high-match jobs
    - locations: Distribution of job locations
    """
    cache_key = f"market_{top_n}_{min_score}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    # Get high-match jobs
    high_match_jobs = (
        session.query(JobPosting)
        .join(MatchResult)
        .filter(MatchResult.match_score >= min_score)
        .all()
    )

    # 1. Top Companies
    company_counter = Counter()
    for job in high_match_jobs:
        company_counter[job.company] += 1

    top_companies = [
        CompanyCount(name=name, count=count)
        for name, count in company_counter.most_common(top_n)
    ]

    # 2. Locations
    location_counter = Counter()
    for job in high_match_jobs:
        loc = job.location or "Unknown"
        # Normalize location (take first part before comma for cleaner grouping)
        loc_normalized = loc.split(",")[0].strip() if loc else "Unknown"
        location_counter[loc_normalized] += 1

    locations = [
        LocationCount(name=name, count=count)
        for name, count in location_counter.most_common(top_n)
    ]

    result = MarketAnalytics(
        top_companies=top_companies,
        locations=locations
    )

    _set_cached(cache_key, result)
    return result


@router.get("/timeline", response_model=TimelineAnalytics)
@limiter.limit("200/minute")
async def get_timeline_analytics(
    request: Request,
    days: int = 30,
    session: Session = Depends(get_db)
):
    """Get activity timeline for the last N days.

    Returns daily counts of:
    - jobs_fetched: Jobs imported on that day
    - matches_generated: Match results created on that day
    """
    cache_key = f"timeline_{days}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    cutoff = datetime.now() - timedelta(days=days)

    # Group jobs by import_date
    jobs_by_day = (
        session.query(
            func.date(JobPosting.import_date).label('date'),
            func.count(JobPosting.id).label('count')
        )
        .filter(JobPosting.import_date >= cutoff)
        .group_by(func.date(JobPosting.import_date))
        .all()
    )
    jobs_dict = {str(row.date): row.count for row in jobs_by_day}

    # Group matches by generated_date
    matches_by_day = (
        session.query(
            func.date(MatchResult.generated_date).label('date'),
            func.count(MatchResult.id).label('count')
        )
        .filter(MatchResult.generated_date >= cutoff)
        .group_by(func.date(MatchResult.generated_date))
        .all()
    )
    matches_dict = {str(row.date): row.count for row in matches_by_day}

    # Build timeline points for each day
    points = []
    current = datetime.now().date()
    for i in range(days):
        date = current - timedelta(days=i)
        date_str = str(date)
        points.append(TimelinePoint(
            date=date_str,
            jobs_fetched=jobs_dict.get(date_str, 0),
            matches_generated=matches_dict.get(date_str, 0)
        ))

    # Reverse to have oldest first
    points.reverse()

    result = TimelineAnalytics(points=points)

    _set_cached(cache_key, result)
    return result


@router.get("/score-distribution")
@limiter.limit("200/minute")
async def get_score_distribution(request: Request, session: Session = Depends(get_db)):
    """Get match score distribution in buckets.

    Returns counts for buckets: 0-50%, 50-70%, 70-85%, 85%+
    """
    cached = _get_cached("score_distribution")
    if cached:
        return cached

    # Query all match scores
    scores = (
        session.query(MatchResult.match_score)
        .all()
    )

    buckets = {
        "0-50": 0,
        "50-70": 0,
        "70-85": 0,
        "85+": 0
    }

    for (score,) in scores:
        if score < 50:
            buckets["0-50"] += 1
        elif score < 70:
            buckets["50-70"] += 1
        elif score < 85:
            buckets["70-85"] += 1
        else:
            buckets["85+"] += 1

    result = [
        {"range": k, "count": v}
        for k, v in buckets.items()
    ]

    _set_cached("score_distribution", result)
    return result


@router.get("/matching-distribution", response_model=MatchingDistribution)
@limiter.limit("200/minute")
async def get_matching_distribution(
    request: Request,
    days: int = 30,
    session: Session = Depends(get_db)
):
    """Get daily breakdown of matches by engine (NLP vs Gemini).
    
    Returns daily counts of:
    - nlp_count: Matches using only NLP
    - gemini_count: Matches using/enhanced by Gemini
    """
    cache_key = f"matching_distribution_{days}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        cutoff = datetime.now() - timedelta(days=days)

        # Query counts grouped by date and whether gemini_score matches
        # We'll fetch raw counts and aggregate in Python for simplicity
        matches = (
            session.query(
                func.date(MatchResult.generated_date).label('date'),
                MatchResult.gemini_score,
                func.count(MatchResult.id).label('count')
            )
            .filter(MatchResult.generated_date >= cutoff)
            .group_by(func.date(MatchResult.generated_date), MatchResult.gemini_score)
            .all()
        )

        # Organize by date
        daily_stats = {}
        
        # Initialize all days with 0
        current = datetime.now().date()
        for i in range(days):
            date_str = str(current - timedelta(days=i))
            daily_stats[date_str] = {"nlp": 0, "gemini": 0}

        for row in matches:
            date_str = str(row.date)
            count = row.count
            is_gemini = row.gemini_score is not None
            
            if date_str in daily_stats:
                if is_gemini:
                    daily_stats[date_str]["gemini"] += count
                else:
                    daily_stats[date_str]["nlp"] += count

        points = [
            MatchingDistributionPoint(
                date=date,
                nlp_count=stats["nlp"],
                gemini_count=stats["gemini"]
            )
            for date, stats in sorted(daily_stats.items())
        ]

        result = MatchingDistribution(points=points)
        _set_cached(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"Error fetching matching distribution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load matching distribution")


@router.get("/performance/summary", response_model=PerformanceSummary)
@limiter.limit("200/minute")
async def get_performance_summary(request: Request, session: Session = Depends(get_db)):
    """Get aggregated system performance metrics (30 days)."""
    cache_key = "perf_summary"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        cutoff_30d = datetime.now() - timedelta(days=30)

        # 1. Search Performance Stats
        search_stats = (
            session.query(
                func.avg(SearchPerformance.total_duration_ms),
                func.count(SearchPerformance.id),
                func.sum(
                    case(
                        (SearchPerformance.status == 'success', 1),
                        else_=0
                    )
                )
            )
            .filter(SearchPerformance.created_at >= cutoff_30d)
            .first()
        )

        avg_search_ms = float(search_stats[0] or 0)
        total_searches = search_stats[1] or 0
        success_searches = search_stats[2] or 0
        success_rate = (success_searches / total_searches) if total_searches > 0 else 0.0

        # 2. API Call Stats with real percentiles
        api_types = (
            session.query(APICallMetric.call_type)
            .filter(APICallMetric.created_at >= cutoff_30d)
            .distinct()
            .all()
        )

        total_api_calls = 0
        gemini_latency = 0.0
        gemini_count = 0
        latencies = []

        for (call_type,) in api_types:
            # Get all durations for this call type to calculate real percentiles
            durations = [
                d for (d,) in session.query(APICallMetric.duration_ms)
                .filter(APICallMetric.call_type == call_type)
                .filter(APICallMetric.created_at >= cutoff_30d)
                .filter(APICallMetric.duration_ms.isnot(None))
                .all()
            ]

            if not durations:
                continue

            count = len(durations)
            total_api_calls += count
            avg_ms = sum(durations) / count

            # Calculate real percentiles
            if len(durations) >= 4:
                sorted_d = sorted(durations)
                p50 = sorted_d[len(sorted_d) // 2]
                p90 = sorted_d[int(len(sorted_d) * 0.9)]
                p99 = sorted_d[int(len(sorted_d) * 0.99)] if len(sorted_d) >= 100 else sorted_d[-1]
            else:
                p50 = p90 = p99 = avg_ms

            latencies.append(LatencyMetric(
                name=call_type,
                avg_ms=round(avg_ms, 1),
                p50_ms=round(p50, 1),
                p90_ms=round(p90, 1),
                p99_ms=round(p99, 1),
                count=count
            ))

            if 'gemini' in call_type:
                gemini_latency += (avg_ms * count)
                gemini_count += count

        avg_gemini_latency = (gemini_latency / gemini_count) if gemini_count > 0 else 0.0

        result = PerformanceSummary(
            avg_search_duration_ms=round(avg_search_ms, 1),
            avg_gemini_latency_ms=round(avg_gemini_latency, 1),
            search_success_rate=round(success_rate, 2),
            total_searches_30d=total_searches,
            total_api_calls_30d=total_api_calls,
            latencies=latencies
        )

        _set_cached(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"Error fetching performance summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load performance metrics")


@router.get("/performance/timeline", response_model=PerformanceTimeline)
@limiter.limit("200/minute")
async def get_performance_timeline(
    request: Request,
    days: int = 30,
    session: Session = Depends(get_db)
):
    """Get daily search duration trends for line chart.

    Returns daily averages of search durations for the specified period.
    """
    cache_key = f"perf_timeline_{days}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        cutoff = datetime.now() - timedelta(days=days)

        daily_stats = (
            session.query(
                func.date(SearchPerformance.created_at).label('date'),
                func.avg(SearchPerformance.total_duration_ms).label('avg_ms'),
                func.count(SearchPerformance.id).label('count')
            )
            .filter(SearchPerformance.created_at >= cutoff)
            .group_by(func.date(SearchPerformance.created_at))
            .order_by(func.date(SearchPerformance.created_at))
            .all()
        )

        points = [
            PerformanceTimelinePoint(
                date=str(row.date),
                avg_ms=round(float(row.avg_ms or 0), 1),
                count=row.count
            )
            for row in daily_stats
        ]

        result = PerformanceTimeline(points=points)
        _set_cached(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"Error fetching performance timeline: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load performance timeline")


@router.get("/performance/breakdown", response_model=PerformanceBreakdown)
@limiter.limit("200/minute")
async def get_performance_breakdown(
    request: Request,
    days: int = 7,
    session: Session = Depends(get_db)
):
    """Get stage-by-stage timing breakdown for stacked bar chart.

    Returns average duration and percentage for each pipeline stage.
    """
    cache_key = f"perf_breakdown_{days}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        cutoff = datetime.now() - timedelta(days=days)

        stats = (
            session.query(
                func.avg(SearchPerformance.initialize_ms).label('initialize'),
                func.avg(SearchPerformance.fetch_ms).label('fetch'),
                func.avg(SearchPerformance.import_ms).label('import_stage'),
                func.avg(SearchPerformance.match_ms).label('match'),
                func.avg(SearchPerformance.export_ms).label('export'),
            )
            .filter(SearchPerformance.created_at >= cutoff)
            .first()
        )

        # Extract values with defaults
        init_ms = float(stats.initialize or 0)
        fetch_ms = float(stats.fetch or 0)
        import_ms = float(stats.import_stage or 0)
        match_ms = float(stats.match or 0)
        export_ms = float(stats.export or 0)

        total_ms = init_ms + fetch_ms + import_ms + match_ms + export_ms

        def calc_pct(val):
            return round((val / total_ms * 100) if total_ms > 0 else 0, 1)

        stages = {
            "initialize": StageMetric(avg_ms=round(init_ms, 1), pct=calc_pct(init_ms)),
            "fetch": StageMetric(avg_ms=round(fetch_ms, 1), pct=calc_pct(fetch_ms)),
            "import": StageMetric(avg_ms=round(import_ms, 1), pct=calc_pct(import_ms)),
            "match": StageMetric(avg_ms=round(match_ms, 1), pct=calc_pct(match_ms)),
            "export": StageMetric(avg_ms=round(export_ms, 1), pct=calc_pct(export_ms)),
        }

        result = PerformanceBreakdown(stages=stages)
        _set_cached(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"Error fetching performance breakdown: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load performance breakdown")


@router.get("/performance/api-latency")
@limiter.limit("200/minute")
async def get_api_latency(
    request: Request,
    days: int = 7,
    session: Session = Depends(get_db)
) -> Dict[str, ApiLatencyDetail]:
    """Get API latency percentiles for each API type.

    Returns p50, p90, p99 for each API type (gemini, apify, sheets).
    """
    cache_key = f"perf_api_latency_{days}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        cutoff = datetime.now() - timedelta(days=days)

        # Get all unique call types
        api_types = (
            session.query(APICallMetric.call_type)
            .filter(APICallMetric.created_at >= cutoff)
            .distinct()
            .all()
        )

        result = {}

        for (call_type,) in api_types:
            durations = [
                d for (d,) in session.query(APICallMetric.duration_ms)
                .filter(APICallMetric.call_type == call_type)
                .filter(APICallMetric.created_at >= cutoff)
                .filter(APICallMetric.duration_ms.isnot(None))
                .all()
            ]

            if not durations:
                continue

            count = len(durations)
            sorted_d = sorted(durations)

            # Calculate percentiles
            if len(sorted_d) >= 4:
                p50 = sorted_d[len(sorted_d) // 2]
                p90 = sorted_d[int(len(sorted_d) * 0.9)]
                p99 = sorted_d[int(len(sorted_d) * 0.99)] if len(sorted_d) >= 100 else sorted_d[-1]
            else:
                avg = sum(sorted_d) / len(sorted_d)
                p50 = p90 = p99 = avg

            result[call_type] = ApiLatencyDetail(
                p50=round(p50, 1),
                p90=round(p90, 1),
                p99=round(p99, 1),
                count=count
            )

        _set_cached(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"Error fetching API latency: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load API latency metrics")


@router.get("/performance/recent-searches", response_model=RecentSearchesResponse)
@limiter.limit("200/minute")
async def get_recent_searches(
    request: Request,
    limit: int = 20,
    session: Session = Depends(get_db)
):
    """Get recent search history for the searches table.

    Returns the most recent searches with their status and metrics.
    """
    cache_key = f"perf_recent_{limit}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        rows = (
            session.query(SearchPerformance, ScheduledSearch.name)
            .outerjoin(ScheduledSearch, SearchPerformance.schedule_id == ScheduledSearch.id)
            .order_by(SearchPerformance.created_at.desc())
            .limit(limit)
            .all()
        )

        search_list = [
            RecentSearch(
                search_id=s.search_id,
                created_at=s.created_at.isoformat() if s.created_at else "",
                total_duration_ms=s.total_duration_ms,
                jobs_fetched=s.jobs_fetched or 0,
                jobs_matched=s.jobs_matched or 0,
                high_matches=s.high_matches or 0,
                status=s.status or "unknown",
                error_message=s.error_message,
                trigger_source=s.trigger_source or "manual",
                schedule_name=schedule_name,
                rematch_type=s.rematch_type,
                gemini_attempted=s.gemini_attempted,
                gemini_succeeded=s.gemini_succeeded,
                gemini_failed=s.gemini_failed,
                jobs_skipped=s.jobs_skipped,
            )
            for s, schedule_name in rows
        ]

        result = RecentSearchesResponse(searches=search_list)
        _set_cached(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"Error fetching recent searches: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load recent searches")


@router.get("/gemini-usage", response_model=GeminiUsageResponse)
@limiter.limit("200/minute")
async def get_gemini_usage(
    request: Request,
    days: int = 30,
    session: Session = Depends(get_db)
):
    """Get daily Gemini API usage breakdown by operation type.

    Returns daily counts of:
    - matching: Jobs matched using Gemini engine
    - rerank: Gemini re-ranking API calls
    - suggestions: Gemini bullet suggestion API calls
    """
    cache_key = f"gemini_usage_{days}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        cutoff = datetime.now() - timedelta(days=days)

        # Initialize daily stats for all days
        daily_stats = {}
        current = datetime.now().date()
        for i in range(days):
            date_str = str(current - timedelta(days=i))
            daily_stats[date_str] = {"matching": 0, "rerank": 0, "suggestions": 0}

        # Query 1: Matching engine usage from MatchResult
        matching_by_day = (
            session.query(
                func.date(MatchResult.generated_date).label('date'),
                func.count(MatchResult.id).label('count')
            )
            .filter(MatchResult.match_engine == 'gemini')
            .filter(MatchResult.generated_date >= cutoff)
            .group_by(func.date(MatchResult.generated_date))
            .all()
        )

        for row in matching_by_day:
            date_str = str(row.date)
            if date_str in daily_stats:
                daily_stats[date_str]["matching"] = row.count

        # Query 2: API Calls (rerank + suggestions) from APICallMetric
        api_calls_by_day = (
            session.query(
                func.date(APICallMetric.created_at).label('date'),
                APICallMetric.call_type,
                func.count(APICallMetric.id).label('count')
            )
            .filter(APICallMetric.call_type.in_(['gemini_rerank', 'gemini_suggestions']))
            .filter(APICallMetric.created_at >= cutoff)
            .group_by(func.date(APICallMetric.created_at), APICallMetric.call_type)
            .all()
        )

        for row in api_calls_by_day:
            date_str = str(row.date)
            if date_str in daily_stats:
                if row.call_type == 'gemini_rerank':
                    daily_stats[date_str]["rerank"] = row.count
                elif row.call_type == 'gemini_suggestions':
                    daily_stats[date_str]["suggestions"] = row.count

        # Build response data (oldest first)
        data = []
        totals = {"matching": 0, "rerank": 0, "suggestions": 0, "total": 0}

        for date_str in sorted(daily_stats.keys()):
            stats = daily_stats[date_str]
            day_total = stats["matching"] + stats["rerank"] + stats["suggestions"]
            data.append(GeminiUsageDay(
                date=date_str,
                matching=stats["matching"],
                rerank=stats["rerank"],
                suggestions=stats["suggestions"],
                total=day_total
            ))
            totals["matching"] += stats["matching"]
            totals["rerank"] += stats["rerank"]
            totals["suggestions"] += stats["suggestions"]
            totals["total"] += day_total

        result = GeminiUsageResponse(
            data=data,
            totals=GeminiUsageTotals(**totals)
        )

        _set_cached(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"Error fetching Gemini usage: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load Gemini usage data")


# --- Scheduled Search Summary ---

class SchedulePerformanceSummary(BaseModel):
    """Per-schedule performance summary."""
    schedule_id: int
    schedule_name: str
    total_runs: int
    successful_runs: int
    failed_runs: int
    avg_duration_ms: float
    avg_jobs_fetched: float
    avg_high_matches: float
    avg_gemini_success_rate: Optional[float] = None
    total_jobs_skipped: int
    last_run_at: Optional[str] = None
    last_status: Optional[str] = None


class ScheduledSearchesSummaryResponse(BaseModel):
    """Response for scheduled search summary endpoint."""
    schedules: List[SchedulePerformanceSummary]
    total_scheduled_runs_30d: int
    overall_success_rate: float


@router.get("/performance/scheduled-summary", response_model=ScheduledSearchesSummaryResponse)
@limiter.limit("200/minute")
async def get_scheduled_search_summary(
    request: Request,
    days: int = 30,
    session: Session = Depends(get_db)
):
    """Get per-schedule performance aggregates.

    Returns summary metrics for each scheduled search over the given period.
    """
    cache_key = f"scheduled_summary_{days}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        cutoff = datetime.now() - timedelta(days=days)

        # Aggregate SearchPerformance by schedule_id, joined with ScheduledSearch
        rows = (
            session.query(
                SearchPerformance.schedule_id,
                ScheduledSearch.name,
                func.count(SearchPerformance.id).label('total_runs'),
                func.sum(case((SearchPerformance.status == 'success', 1), else_=0)).label('successful_runs'),
                func.sum(case((SearchPerformance.status == 'error', 1), else_=0)).label('failed_runs'),
                func.avg(SearchPerformance.total_duration_ms).label('avg_duration_ms'),
                func.avg(SearchPerformance.jobs_fetched).label('avg_jobs_fetched'),
                func.avg(SearchPerformance.high_matches).label('avg_high_matches'),
                func.sum(func.coalesce(SearchPerformance.gemini_succeeded, 0)).label('total_gemini_succeeded'),
                func.sum(func.coalesce(SearchPerformance.gemini_attempted, 0)).label('total_gemini_attempted'),
                func.sum(func.coalesce(SearchPerformance.jobs_skipped, 0)).label('total_jobs_skipped'),
            )
            .join(ScheduledSearch, SearchPerformance.schedule_id == ScheduledSearch.id)
            .filter(SearchPerformance.created_at >= cutoff)
            .filter(SearchPerformance.schedule_id.isnot(None))
            .group_by(SearchPerformance.schedule_id, ScheduledSearch.name)
            .all()
        )

        schedules = []
        total_runs = 0
        total_success = 0

        for row in rows:
            total_runs += row.total_runs
            total_success += row.successful_runs

            # Get last run info
            last_run = (
                session.query(SearchPerformance.created_at, SearchPerformance.status)
                .filter(SearchPerformance.schedule_id == row.schedule_id)
                .order_by(SearchPerformance.created_at.desc())
                .first()
            )

            gemini_rate = None
            if row.total_gemini_attempted and row.total_gemini_attempted > 0:
                gemini_rate = round(row.total_gemini_succeeded / row.total_gemini_attempted, 2)

            schedules.append(SchedulePerformanceSummary(
                schedule_id=row.schedule_id,
                schedule_name=row.name,
                total_runs=row.total_runs,
                successful_runs=row.successful_runs,
                failed_runs=row.failed_runs,
                avg_duration_ms=round(float(row.avg_duration_ms or 0), 1),
                avg_jobs_fetched=round(float(row.avg_jobs_fetched or 0), 1),
                avg_high_matches=round(float(row.avg_high_matches or 0), 1),
                avg_gemini_success_rate=gemini_rate,
                total_jobs_skipped=int(row.total_jobs_skipped or 0),
                last_run_at=last_run.created_at.isoformat() if last_run else None,
                last_status=last_run.status if last_run else None,
            ))

        overall_rate = round(total_success / total_runs, 2) if total_runs > 0 else 0.0

        result = ScheduledSearchesSummaryResponse(
            schedules=schedules,
            total_scheduled_runs_30d=total_runs,
            overall_success_rate=overall_rate,
        )

        _set_cached(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"Error fetching scheduled search summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load scheduled search summary")
