"""Shared Gemini enrichment for job postings.

Runs domain extraction, summarization, and requirements extraction
concurrently across jobs using a thread pool. The existing GeminiRateLimiter
(threading.Lock-based) naturally throttles concurrent calls.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


def _enrich_single_job(job, gemini_extractor, requirements_extractor) -> bool:
    """Run all Gemini extractions for a single job posting.

    Returns True if at least one extraction succeeded.
    """
    enriched = False

    if gemini_extractor:
        # Extract domains
        try:
            result = gemini_extractor.extract_domains(
                description=job.description or '',
                company=job.company,
                title=job.title
            )
            domains = result.get('domains', [])
            if domains or result.get('reasoning'):
                job.required_domains = domains if domains else None
                job.domain_extraction_method = 'llm'
                enriched = True
        except Exception as e:
            logger.warning(f"Gemini domain extraction failed for {job.title}: {e}")

        # Generate summary
        try:
            summary = gemini_extractor.summarize_job(
                description=job.description or '',
                company=job.company,
                title=job.title
            )
            if summary:
                job.summary = summary
                enriched = True
        except Exception as e:
            logger.warning(f"Gemini summarization failed for {job.title}: {e}")

    if requirements_extractor:
        try:
            requirements = requirements_extractor.extract_requirements(
                description=job.description or '',
                title=job.title,
                company=job.company
            )
            if requirements:
                job.structured_requirements = requirements
                job.requirements_extracted_at = datetime.utcnow()
                job.requirements_extraction_model = requirements_extractor.model_name
                enriched = True
        except Exception as e:
            logger.warning(f"Requirements extraction failed for {job.title}: {e}")

    return enriched


def enrich_jobs_parallel(
    job_postings: List,
    gemini_extractor,
    requirements_extractor,
    session,
    max_workers: int = 5,
) -> int:
    """Enrich jobs with Gemini extraction using thread pool.

    Runs domain extraction, summarization, and requirements extraction
    concurrently across jobs. Returns count of successfully enriched jobs.
    """
    if not job_postings:
        return 0

    enriched_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_job = {
            executor.submit(
                _enrich_single_job, job, gemini_extractor, requirements_extractor
            ): job
            for job in job_postings
        }

        for future in as_completed(future_to_job):
            job = future_to_job[future]
            try:
                if future.result():
                    enriched_count += 1
            except Exception as e:
                logger.error(f"Unexpected error enriching {job.title}: {e}")

    session.commit()
    return enriched_count
