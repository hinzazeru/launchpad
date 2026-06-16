# Matching Module

Calculates job-resume compatibility scores using Gemini AI.

## Overview

This module is the core intelligence of the job matcher. It takes job postings and a resume, then produces a match score (0-100%) plus rich AI insights (strengths, concerns, recommendations, detailed skill analysis) indicating how well the job fits the candidate.

Matching is **Gemini-only**. There is no NLP fallback: if Gemini is unavailable or a
match fails, the engine raises `GeminiUnavailableError` and the caller fails the search
so it can be retried later, rather than persisting a degraded result.

## Files

| File | Purpose |
|------|---------|
| `engine.py` | Orchestrator — runs Gemini matching, handles caching, concurrency, and failure (`GeminiUnavailableError`) |
| `gemini_matcher.py` | Gemini AI matcher (`MATCHING_PROMPT`, `GeminiMatchResult`) |
| `requirements.py` | `StructuredRequirements` & `GeminiMatchResult` dataclasses |
| `skill_extractor.py` | Extracts skills from job descriptions (used by importers/enrichment, not matching) |

## Score Calculation

Scores come directly from the Gemini matcher, which returns component scores
(skills, experience, seniority, domain) and an overall 0-100 match score, along with
matched skills, skill gaps, and narrative insights. See `gemini_matcher.py` →
`MATCHING_PROMPT` and `requirements.py` → `GeminiMatchResult`.

## Failure Handling

- `JobMatcher()` raises `GeminiUnavailableError` at construction if Gemini isn't configured.
- `match_job()` / `match_jobs()` raise `GeminiUnavailableError` on a failed/empty Gemini call.
- Web searches mark the `SearchJob` as `failed`; scheduled runs record the error and
  reschedule per `max_retries` / `retry_delay_minutes`.

## Caching

`match_jobs()` reuses previously-saved Gemini matches for the same `(resume, job)` pair
(`crud.get_cached_gemini_matches`) to avoid re-paying API cost on repeat searches.

## Usage Example

```python
from src.matching.engine import JobMatcher, GeminiUnavailableError
from src.database.models import Resume, JobPosting

try:
    matcher = JobMatcher()  # raises GeminiUnavailableError if not configured
    result = matcher.match_job(resume, job_posting)
except GeminiUnavailableError:
    ...  # fail the search; retry later

print(f"Overall: {result['overall_score'] * 100}%")
print(f"Strengths: {result.get('ai_strengths', [])}")
print(f"Skill gaps: {result.get('skill_gaps', [])}")
```

## Configuration

In `config.yaml`:

```yaml
matching:
  engine: "gemini"      # Gemini-only
  min_match_score: 0.5  # Minimum score to consider a match
```
