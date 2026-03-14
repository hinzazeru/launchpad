"""Shared Gemini enrichment for job postings.

Runs domain extraction, summarization, and requirements extraction
concurrently across jobs using a thread pool. The existing GeminiRateLimiter
(threading.Lock-based) naturally throttles concurrent calls.

IMPORTANT: Worker threads must NOT modify SQLAlchemy ORM objects directly.
SQLAlchemy's session dirty-tracking is not thread-safe, so attribute changes
from worker threads get silently lost on commit. Instead, threads return
plain dicts and the main thread applies results to ORM objects.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _extract_for_job(
    description: str,
    title: str,
    company: str,
    gemini_extractor,
    requirements_extractor,
) -> Dict:
    """Run all Gemini extractions for a single job (thread-safe, no ORM access).

    Returns a dict of extracted fields to apply to the ORM object.
    """
    result = {}

    if gemini_extractor:
        # Extract domains
        try:
            domain_result = gemini_extractor.extract_domains(
                description=description,
                company=company,
                title=title
            )
            domains = domain_result.get('domains', [])
            if domains or domain_result.get('reasoning'):
                result['required_domains'] = domains if domains else None
                result['domain_extraction_method'] = 'llm'
        except Exception as e:
            logger.warning(f"Gemini domain extraction failed for {title}: {e}")

        # Generate summary
        try:
            summary = gemini_extractor.summarize_job(
                description=description,
                company=company,
                title=title
            )
            if summary:
                result['summary'] = summary
        except Exception as e:
            logger.warning(f"Gemini summarization failed for {title}: {e}")

    if requirements_extractor:
        try:
            requirements = requirements_extractor.extract_requirements(
                description=description,
                title=title,
                company=company
            )
            if requirements:
                result['structured_requirements'] = requirements
                result['requirements_extracted_at'] = datetime.now(timezone.utc)
                result['requirements_extraction_model'] = requirements_extractor.model_name
        except Exception as e:
            logger.warning(f"Requirements extraction failed for {title}: {e}")

    return result


def enrich_jobs_parallel(
    job_postings: List,
    gemini_extractor,
    requirements_extractor,
    session,
    max_workers: int = 2,
) -> int:
    """Enrich jobs with Gemini extraction using thread pool.

    Runs domain extraction, summarization, and requirements extraction
    concurrently across jobs. Results are applied to ORM objects in the
    main thread to avoid SQLAlchemy thread-safety issues.
    Returns count of successfully enriched jobs.
    """
    if not job_postings:
        return 0

    enriched_count = 0

    # Submit extraction tasks — threads only do Gemini API calls, return dicts
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_job = {
            executor.submit(
                _extract_for_job,
                description=job.description or '',
                title=job.title,
                company=job.company,
                gemini_extractor=gemini_extractor,
                requirements_extractor=requirements_extractor,
            ): job
            for job in job_postings
        }

        # Collect results and apply to ORM objects in main thread
        for future in as_completed(future_to_job):
            job = future_to_job[future]
            try:
                extracted = future.result()
                if extracted:
                    for attr, value in extracted.items():
                        setattr(job, attr, value)
                    enriched_count += 1
            except Exception as e:
                logger.error(f"Unexpected error enriching {job.title}: {e}")

    session.commit()
    return enriched_count
