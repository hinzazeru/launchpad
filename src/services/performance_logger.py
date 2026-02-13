
import time
import uuid
import logging
from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from src.database.models import SearchPerformance, APICallMetric

logger = logging.getLogger(__name__)


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

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            self.duration_ms = int((time.perf_counter() - self.start_time) * 1000)
            self.logger.record_timing(self.name, self.duration_ms)


class PerformanceLogger:
    """Collects timings during a search/analysis operation."""

    def __init__(self, search_id: str = None):
        self.search_id = search_id or str(uuid.uuid4())
        self.timings: Dict[str, int] = {}
        self.counts: Dict[str, int] = {}
        self.extra: Dict[str, any] = {}
        self.api_calls: List[Dict] = []
        self.start_time = time.perf_counter()

    def time(self, name: str) -> PerformanceTimer:
        """Usage: with logger.time('fetch'): ..."""
        return PerformanceTimer(name, self)

    def record_timing(self, name: str, duration_ms: int):
        self.timings[name] = duration_ms

    def record_count(self, name: str, count: int):
        self.counts[name] = count

    def record_extra(self, key: str, value):
        """Record an extra metadata field (JSON-serializable)."""
        self.extra[key] = value

    def record_api_call(self, call_type: str, duration_ms: int, status: str, **kwargs):
        self.api_calls.append({
            'call_type': call_type,
            'duration_ms': duration_ms,
            'status': status,
            **kwargs
        })

    def save(
        self,
        session: Session,
        status: str = 'success',
        error_stage: str = None,
        error_message: str = None,
        trigger_source: str = 'manual',
        schedule_id: int = None
    ):
        """Persist all collected metrics to database."""
        try:
            total_duration = int((time.perf_counter() - self.start_time) * 1000)
            
            # Map known timings to model fields
            perf = SearchPerformance(
                search_id=self.search_id,
                status=status,
                created_at=datetime.utcnow(),
                total_duration_ms=total_duration,
                
                # Trigger tracking
                trigger_source=trigger_source,
                schedule_id=schedule_id,
                
                # High-level stages
                initialize_ms=self.timings.get('initialize'),
                fetch_ms=self.timings.get('fetch'),
                import_ms=self.timings.get('import'),
                match_ms=self.timings.get('match'),
                export_ms=self.timings.get('export'),
                
                # Sub-components
                apify_api_ms=self.timings.get('apify_api'),
                db_import_ms=self.timings.get('db_import'),
                skills_extraction_ms=self.timings.get('skills_extraction'),
                nlp_embedding_ms=self.timings.get('nlp_embedding'),
                gemini_rerank_ms=self.timings.get('gemini_rerank'),
                sheets_export_ms=self.timings.get('sheets_export'),
                
                # Counts
                jobs_fetched=self.counts.get('jobs_fetched', 0),
                jobs_imported=self.counts.get('jobs_imported', 0),
                jobs_matched=self.counts.get('jobs_matched', 0),
                high_matches=self.counts.get('high_matches', 0),
                gemini_calls=self.counts.get('gemini_calls', 0),

                # Gemini matching stats
                gemini_attempted=self.counts.get('gemini_attempted'),
                gemini_succeeded=self.counts.get('gemini_succeeded'),
                gemini_failed=self.counts.get('gemini_failed'),
                gemini_failure_reasons=self.extra.get('gemini_failure_reasons'),

                # Smart rematch tracking
                rematch_type=self.extra.get('rematch_type'),
                jobs_skipped=self.counts.get('jobs_skipped'),

                # Gemini timing summary
                gemini_timing_summary=self.extra.get('gemini_timing_summary'),

                # Error context
                error_stage=error_stage,
                error_message=str(error_message)[:2000] if error_message else None  # Truncate error message
            )
            session.add(perf)

            # Save API calls
            for call in self.api_calls:
                metric = APICallMetric(
                    search_id=self.search_id,
                    created_at=datetime.utcnow(),
                    call_type=call['call_type'],
                    duration_ms=call['duration_ms'],
                    status=call['status'],
                    tokens_used=call.get('tokens_used'),
                    error_message=str(call.get('error_message'))[:2000] if call.get('error_message') else None
                )
                session.add(metric)

            session.commit()
            logger.info(f"Performance metrics saved for search {self.search_id}")
            
        except Exception as e:
            logger.error(f"Failed to save performance metrics: {str(e)}")
            session.rollback()
