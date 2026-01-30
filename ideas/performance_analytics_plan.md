# Performance Analytics Implementation Plan

## Goal
Track and visualize system performance with detailed sub-component timing to identify bottlenecks and monitor AI/external API latency.

## User Requirements
- **Data Retention**: Long-term (30+ days) with archival strategy
- **UI Location**: New "Performance" tab on existing Analytics page
- **Granularity**: Include sub-components (skills extraction, NLP embedding, Gemini API, DB queries)

---

## Database Schema

### Table 1: SearchPerformance (one row per search)

```python
class SearchPerformance(Base):
    __tablename__ = "search_performance"

    id = Column(Integer, primary_key=True)
    search_id = Column(String(36), unique=True, index=True)  # UUID
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    status = Column(String(20))  # success, error, cancelled

    # High-level stage timings (ms)
    total_duration_ms = Column(Integer)
    initialize_ms = Column(Integer)
    fetch_ms = Column(Integer)
    import_ms = Column(Integer)
    match_ms = Column(Integer)
    export_ms = Column(Integer)

    # Sub-component timings (ms) - nullable
    apify_api_ms = Column(Integer, nullable=True)
    db_import_ms = Column(Integer, nullable=True)
    skills_extraction_ms = Column(Integer, nullable=True)
    nlp_embedding_ms = Column(Integer, nullable=True)
    gemini_rerank_ms = Column(Integer, nullable=True)
    sheets_export_ms = Column(Integer, nullable=True)

    # Counts
    jobs_fetched = Column(Integer)
    jobs_imported = Column(Integer)
    jobs_matched = Column(Integer)
    high_matches = Column(Integer)
    gemini_calls = Column(Integer, nullable=True)

    # Error tracking
    error_stage = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
```

### Table 2: APICallMetric (individual API calls)

```python
class APICallMetric(Base):
    __tablename__ = "api_call_metrics"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    call_type = Column(String(50), index=True)  # gemini_rerank, gemini_suggestions, apify_search, sheets_export
    duration_ms = Column(Integer)
    status = Column(String(20))  # success, error, timeout

    # Optional context
    search_id = Column(String(36), nullable=True, index=True)
    tokens_used = Column(Integer, nullable=True)  # For Gemini calls
    error_message = Column(Text, nullable=True)
```

---

## Performance Logger Service

```python
# src/services/performance_logger.py

class PerformanceTimer:
    """Context manager for timing code blocks."""

    def __init__(self, name: str, logger: 'PerformanceLogger'):
        self.name = name
        self.logger = logger
        self.start_time = None
        self.duration_ms = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.duration_ms = int((time.perf_counter() - self.start_time) * 1000)
        self.logger.record_timing(self.name, self.duration_ms)


class PerformanceLogger:
    """Collects timings during a search/analysis operation."""

    def __init__(self, search_id: str = None):
        self.search_id = search_id or str(uuid.uuid4())
        self.timings: Dict[str, int] = {}
        self.counts: Dict[str, int] = {}
        self.api_calls: List[Dict] = []

    def time(self, name: str) -> PerformanceTimer:
        """Usage: with logger.time('fetch'): ..."""
        return PerformanceTimer(name, self)

    def record_timing(self, name: str, duration_ms: int):
        self.timings[name] = duration_ms

    def record_api_call(self, call_type: str, duration_ms: int, status: str, **kwargs):
        self.api_calls.append({
            'call_type': call_type,
            'duration_ms': duration_ms,
            'status': status,
            **kwargs
        })

    def save(self, session: Session, status: str = 'success', error_stage: str = None, error_message: str = None):
        """Persist all collected metrics to database."""
        perf = SearchPerformance(
            search_id=self.search_id,
            status=status,
            total_duration_ms=self.timings.get('total'),
            # ... map all timings
        )
        session.add(perf)

        for call in self.api_calls:
            metric = APICallMetric(search_id=self.search_id, **call)
            session.add(metric)

        session.commit()
```

---

## API Endpoints

### GET /api/analytics/performance/summary
```json
{
    "avg_search_duration_ms": 15234,
    "avg_gemini_latency_ms": 1850,
    "search_success_rate": 0.94,
    "total_searches_30d": 127,
    "total_api_calls_30d": 2543
}
```

### GET /api/analytics/performance/timeline?days=30&metric=search_duration
```json
{
    "points": [
        {"date": "2026-01-25", "avg_ms": 14500, "count": 5},
        {"date": "2026-01-26", "avg_ms": 16200, "count": 8}
    ]
}
```

### GET /api/analytics/performance/breakdown?days=7
```json
{
    "stages": {
        "initialize": {"avg_ms": 150, "pct": 1},
        "fetch": {"avg_ms": 8500, "pct": 56},
        "import": {"avg_ms": 800, "pct": 5},
        "match": {"avg_ms": 5200, "pct": 34},
        "export": {"avg_ms": 600, "pct": 4}
    }
}
```

### GET /api/analytics/performance/api-latency?days=7
```json
{
    "gemini_rerank": {"p50": 1200, "p90": 2800, "p99": 5200, "count": 450},
    "apify_search": {"p50": 8000, "p90": 15000, "p99": 25000, "count": 127},
    "sheets_export": {"p50": 1500, "p90": 2500, "p99": 4000, "count": 89}
}
```

---

## UI Design (Performance Tab)

```
┌─────────────────────────────────────────────────────────────────────┐
│ Analytics                                                            │
│ [Self-Improvement] [Market Research] [Performance]  ← NEW TAB       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │
│ │ Avg Search   │ │ Avg Gemini   │ │ Success Rate │ │ Searches     │ │
│ │ 15.2s        │ │ 1.85s        │ │ 94%          │ │ 127 (30d)    │ │
│ └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘ │
│                                                                      │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ Search Duration Trend (30 days)                    [Line Chart] │ │
│ │ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~        │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│ ┌───────────────────────────┐ ┌───────────────────────────────────┐ │
│ │ Stage Breakdown           │ │ API Latency (p50/p90)             │ │
│ │ [Stacked Bar]             │ │ [Horizontal Bar]                  │ │
│ │ ▓▓▓░░░░░░░░░░ Fetch 56%   │ │ Gemini  ████████░░ 1.2s/2.8s     │ │
│ │ ▓▓▓▓▓░░░░░░░░ Match 34%   │ │ Apify   █████████████░ 8s/15s    │ │
│ │ ░░░░░░░░░░░░░ Other 10%   │ │ Sheets  ████░░░░░░ 1.5s/2.5s     │ │
│ └───────────────────────────┘ └───────────────────────────────────┘ │
│                                                                      │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ Recent Searches                                      [Table]    │ │
│ │ Time       | Duration | Jobs | Matches | Status               │ │
│ │ 10:32 AM   | 12.4s    | 45   | 8       | ✓ Success            │ │
│ │ 09:15 AM   | 18.2s    | 62   | 12      | ✓ Success            │ │
│ │ Yesterday  | --       | 0    | 0       | ✗ Apify Error        │ │
│ └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Files to Create/Modify

### Backend
| File | Action |
|------|--------|
| `src/database/models.py` | **MODIFY** - Add SearchPerformance, APICallMetric models |
| `src/services/performance_logger.py` | **CREATE** - PerformanceLogger service |
| `backend/routers/search.py` | **MODIFY** - Instrument with PerformanceLogger |
| `backend/routers/analysis.py` | **MODIFY** - Instrument Gemini calls |
| `backend/routers/analytics.py` | **MODIFY** - Add performance endpoints |
| `config.yaml.example` | **MODIFY** - Add performance config section |

### Frontend
| File | Action |
|------|--------|
| `frontend/src/pages/Analytics.tsx` | **MODIFY** - Add tab navigation |
| `frontend/src/components/analytics/PerformanceTab.tsx` | **CREATE** - Performance dashboard |
| `frontend/src/components/analytics/LatencyChart.tsx` | **CREATE** - API latency visualization |
| `frontend/src/components/analytics/StageBreakdown.tsx` | **CREATE** - Stacked bar chart |
| `frontend/src/services/api.ts` | **MODIFY** - Add performance API hooks |

---

## Data Cleanup Strategy

Add to `config.yaml`:
```yaml
performance:
  retention_days: 90
  cleanup_batch_size: 1000
```

---

## Implementation Tasks

### Phase 1: Database & Service
- [ ] Add SearchPerformance model to `src/database/models.py`
- [ ] Add APICallMetric model to `src/database/models.py`
- [ ] Create `src/services/performance_logger.py`
- [ ] Add performance config section to `config.yaml.example`

### Phase 2: Backend Instrumentation
- [ ] Instrument `backend/routers/search.py` with PerformanceLogger
- [ ] Instrument `backend/routers/analysis.py` for Gemini timing
- [ ] Add `/performance/summary` endpoint to analytics.py
- [ ] Add `/performance/timeline` endpoint to analytics.py
- [ ] Add `/performance/breakdown` endpoint to analytics.py
- [ ] Add `/performance/api-latency` endpoint to analytics.py

### Phase 3: Frontend
- [ ] Add performance API types to `api.ts`
- [ ] Add performance React Query hooks to `api.ts`
- [ ] Create `PerformanceTab.tsx` component
- [ ] Create `LatencyChart.tsx` component
- [ ] Create `StageBreakdown.tsx` component
- [ ] Add tab navigation to Analytics page

### Phase 4: Polish
- [ ] Add data cleanup command/function
- [ ] Add loading states and error handling
- [ ] Test with real search data
- [ ] Document performance config options
