# Bright Data Integration: Alternative LinkedIn Job Scraper

**Created:** 2026-02-04
**Status:** Planned
**Priority:** High (Apify experiencing maintenance downtime)

---

## Overview

Add Bright Data as an alternative to Apify for fetching LinkedIn job postings. Users can configure which provider to use via `config.yaml`.

**Why?** Apify has been unreliable (maintenance downtime). Bright Data offers similar functionality with:
- Official Python SDK
- Well-documented LinkedIn Jobs API
- Legal compliance (GDPR/CCPA)
- Similar data structure to Apify

---

## Bright Data API Reference

**Authentication:** Bearer token in `Authorization` header

**Trigger Job Search:**
```
POST https://api.brightdata.com/datasets/v3/trigger
  ?dataset_id=gd_lpfll7v5hcqtkxl6l
  &include_errors=true
  &type=discover_new
  &discover_by=keyword
  &limit_per_input={max_results}
```

**Request Body:**
```json
[{
  "location": "United States",
  "keyword": "Product Manager",
  "country": "US",
  "time_range": "Past 24 hours",
  "job_type": "Full-time",
  "experience_level": "Mid-Senior level",
  "remote": "Remote"
}]
```

**Response:** `{ "snapshot_id": "abc123" }`

**Poll for Results:**
```
GET https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}?format=json
```
- `200` = Ready (returns job array)
- `202` = Processing (retry after delay)

**Job Data Fields:**
- `job_posting_id`, `url`, `job_title`, `job_summary`, `company_name`
- `job_location`, `job_seniority_level`, `job_function`, `job_industries`
- `job_employment_type`, `job_base_pay_range`, `job_posted_date`

---

## Architecture: Provider Abstraction

Create a `JobProvider` abstraction to support multiple providers:

```
src/importers/
├── base_provider.py       # NEW: Abstract base class
├── apify_provider.py      # Renamed from api_importer.py
├── brightdata_provider.py # NEW: Bright Data implementation
└── provider_factory.py    # NEW: Factory to get configured provider
```

---

## Implementation Steps

### Phase 1: Base Provider Interface

**File:** `src/importers/base_provider.py`

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Optional

class JobProvider(ABC):
    """Abstract base class for job data providers."""

    @abstractmethod
    async def search_jobs_async(
        self,
        keywords: Optional[str] = None,
        location: str = "United States",
        job_type: Optional[str] = None,
        max_results: int = 50,
        posted_when: str = "Past 24 hours",
        experience_level: Optional[str] = None,
        work_arrangement: Optional[str] = None,
        progress_callback: Optional[callable] = None,
    ) -> List[Dict]:
        """Search for jobs and return raw provider data."""
        pass

    @abstractmethod
    def normalize_job(self, job_data: Dict) -> Dict:
        """Normalize provider-specific data to standard format."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider identifier (e.g., 'apify', 'brightdata')."""
        pass
```

---

### Phase 2: Bright Data Provider

**File:** `src/importers/brightdata_provider.py`

```python
import asyncio
import aiohttp
from typing import List, Dict, Optional

class BrightDataJobProvider(JobProvider):
    """Bright Data API client for LinkedIn jobs."""

    BASE_URL = "https://api.brightdata.com/datasets/v3"
    DATASET_ID = "gd_lpfll7v5hcqtkxl6l"  # LinkedIn job listings

    def __init__(self, api_key: Optional[str] = None):
        from src.config import get_config
        self.config = get_config()

        if api_key:
            self.api_key = api_key
        else:
            self.api_key = self.config.get("brightdata.api_key")

        if not self.api_key or self.api_key == "YOUR_BRIGHTDATA_API_KEY_HERE":
            raise ValueError("Bright Data API key not configured")

    async def search_jobs_async(self, keywords, location, ...):
        # 1. Trigger search
        snapshot_id = await self._trigger_search(keywords, location, ...)

        # 2. Poll until ready
        return await self._poll_results(snapshot_id, progress_callback)

    async def _trigger_search(self, ...) -> str:
        """Trigger job search, return snapshot_id."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.BASE_URL}/trigger",
                params={
                    "dataset_id": self.DATASET_ID,
                    "include_errors": "true",
                    "type": "discover_new",
                    "discover_by": "keyword",
                    "limit_per_input": max_results,
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=[{
                    "location": location,
                    "keyword": keywords,
                    "time_range": posted_when,
                    # ... map other params
                }]
            ) as resp:
                data = await resp.json()
                return data["snapshot_id"]

    async def _poll_results(self, snapshot_id: str, callback) -> List[Dict]:
        """Poll for results until ready."""
        async with aiohttp.ClientSession() as session:
            for attempt in range(60):  # Max 5 minutes
                async with session.get(
                    f"{self.BASE_URL}/snapshot/{snapshot_id}",
                    params={"format": "json"},
                    headers={"Authorization": f"Bearer {self.api_key}"}
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    elif resp.status == 202:
                        if callback:
                            await callback(f"Processing... ({attempt+1})", 0.5)
                        await asyncio.sleep(5)
                    else:
                        raise Exception(f"Bright Data error: {resp.status}")
            raise TimeoutError("Bright Data polling timeout")

    def normalize_job(self, job_data: Dict) -> Dict:
        """Map Bright Data fields to standard format."""
        return {
            'title': job_data.get('job_title', ''),
            'company': job_data.get('company_name', ''),
            'location': job_data.get('job_location', ''),
            'description': job_data.get('job_summary', ''),
            'url': job_data.get('url', ''),
            'posting_date': self._parse_date(job_data.get('job_posted_date')),
            'source': 'brightdata',
            # ... same normalization as Apify
        }
```

---

### Phase 3: Refactor Apify Provider

**File:** `src/importers/apify_provider.py`

Rename `ApifyJobImporter` to `ApifyJobProvider` and make it extend `JobProvider`:

```python
from src.importers.base_provider import JobProvider

class ApifyJobProvider(JobProvider):
    """Apify API client for LinkedIn jobs."""

    @property
    def provider_name(self) -> str:
        return "apify"

    # Existing methods remain the same, just ensure they match
    # the abstract interface from JobProvider
```

---

### Phase 4: Provider Factory

**File:** `src/importers/provider_factory.py`

```python
from src.importers.base_provider import JobProvider

def get_job_provider(provider: str = None) -> JobProvider:
    """Factory function to get configured job provider.

    Args:
        provider: Override config setting. Options: 'apify', 'brightdata', 'auto'

    Returns:
        Configured JobProvider instance
    """
    from src.config import get_config
    config = get_config()

    if provider is None:
        provider = config.get("job_provider.provider", "apify")

    if provider == "auto":
        # Try Bright Data first, fall back to Apify
        try:
            from src.importers.brightdata_provider import BrightDataJobProvider
            return BrightDataJobProvider()
        except ValueError:
            pass
        try:
            from src.importers.apify_provider import ApifyJobProvider
            return ApifyJobProvider()
        except ValueError:
            raise ValueError("No job provider configured")

    elif provider == "brightdata":
        from src.importers.brightdata_provider import BrightDataJobProvider
        return BrightDataJobProvider()

    elif provider == "apify":
        from src.importers.apify_provider import ApifyJobProvider
        return ApifyJobProvider()

    else:
        raise ValueError(f"Unknown job provider: {provider}")
```

---

### Phase 5: Configuration

**File:** `config.yaml.example`

Add new section:

```yaml
# Job Data Provider Configuration
job_provider:
  # Provider to use for fetching LinkedIn jobs
  # Options:
  #   "apify" - Use Apify LinkedIn scraper (original)
  #   "brightdata" - Use Bright Data LinkedIn Jobs API
  #   "auto" - Try Bright Data first, fall back to Apify
  provider: "apify"

# Bright Data API Configuration
brightdata:
  api_key: "YOUR_BRIGHTDATA_API_KEY_HERE"  # Get from https://brightdata.com/cp/api_keys

  # Request settings
  poll_interval_seconds: 5   # How often to check for results
  poll_timeout_seconds: 300  # Max wait time (5 minutes)

  # Dataset ID (don't change unless using different dataset)
  dataset_id: "gd_lpfll7v5hcqtkxl6l"
```

**File:** `src/config.py`

Add helper method:

```python
def get_brightdata_api_key(self) -> str:
    """Get Bright Data API key from config."""
    api_key = self.get("brightdata.api_key")
    if not api_key or api_key == "YOUR_BRIGHTDATA_API_KEY_HERE":
        raise ValueError("Bright Data API key not configured")
    return api_key

def get_job_provider(self) -> str:
    """Get configured job provider."""
    return self.get("job_provider.provider", "apify")
```

---

### Phase 6: Update Consumers

Update all files that use `ApifyJobImporter` to use the factory:

**Files to update:**
- `backend/routers/search.py` - Job search endpoint
- `backend/services/webapp_scheduler.py` - Scheduled searches
- `src/scheduler/job_scheduler.py` - Telegram bot scheduler

**Change pattern:**
```python
# Before
from src.importers.api_importer import ApifyJobImporter
importer = ApifyJobImporter()
jobs = await importer.search_jobs_async(...)

# After
from src.importers.provider_factory import get_job_provider
provider = get_job_provider()
jobs = await provider.search_jobs_async(...)
```

---

### Phase 7: Frontend Provider Selection (Optional Enhancement)

Add UI option to select provider per-search:

**File:** `frontend/src/pages/GetJobs.tsx`

Add dropdown to form:
```typescript
<Select
  label="Data Provider"
  value={provider}
  options={[
    { value: 'auto', label: 'Auto (try both)' },
    { value: 'brightdata', label: 'Bright Data' },
    { value: 'apify', label: 'Apify' },
  ]}
/>
```

**File:** `backend/schemas/search.py`

Add field to request:
```python
class SearchJobCreate(BaseModel):
    # ... existing fields ...
    provider: Optional[str] = Field(default=None, description="Job provider override")
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/importers/base_provider.py` | NEW - Abstract base class |
| `src/importers/brightdata_provider.py` | NEW - Bright Data implementation |
| `src/importers/api_importer.py` | Rename to `apify_provider.py`, extend base |
| `src/importers/provider_factory.py` | NEW - Factory function |
| `config.yaml.example` | Add `job_provider` and `brightdata` sections |
| `src/config.py` | Add `get_brightdata_api_key()` and `get_job_provider()` |
| `backend/routers/search.py` | Use `get_job_provider()` factory |
| `backend/services/webapp_scheduler.py` | Use `get_job_provider()` factory |
| `src/scheduler/job_scheduler.py` | Use `get_job_provider()` factory |

---

## Performance Improvements

1. **Parallel polling:** Poll both providers simultaneously in `auto` mode
2. **Caching:** Cache API responses for identical searches within 5 minutes
3. **Retry logic:** Exponential backoff for transient errors
4. **Rate limiting:** Track API calls to avoid hitting rate limits

---

## Testing Strategy

1. **Unit tests:** Mock API responses for both providers
2. **Integration test:** Real API call with small `max_results=5`
3. **Fallback test:** Simulate Bright Data failure, verify Apify fallback

---

## Detailed Task List

### Core Implementation (Required)

1. **Create base provider interface**
   - [ ] Create `src/importers/base_provider.py`
   - [ ] Define `JobProvider` ABC with `search_jobs_async()`, `normalize_job()`, `provider_name`
   - [ ] Document expected behavior and return types

2. **Implement Bright Data provider**
   - [ ] Create `src/importers/brightdata_provider.py`
   - [ ] Implement `_trigger_search()` - POST to trigger endpoint
   - [ ] Implement `_poll_results()` - GET with retry loop
   - [ ] Implement `normalize_job()` - map Bright Data fields to standard format
   - [ ] Handle authentication (Bearer token)
   - [ ] Add progress callback support
   - [ ] Add error handling for API errors and timeouts

3. **Refactor Apify provider**
   - [ ] Rename `src/importers/api_importer.py` to `src/importers/apify_provider.py`
   - [ ] Rename class `ApifyJobImporter` to `ApifyJobProvider`
   - [ ] Extend `JobProvider` base class
   - [ ] Implement `provider_name` property
   - [ ] Keep backward compatibility alias (`ApifyJobImporter = ApifyJobProvider`)

4. **Create provider factory**
   - [ ] Create `src/importers/provider_factory.py`
   - [ ] Implement `get_job_provider(provider=None)` function
   - [ ] Support 'apify', 'brightdata', 'auto' options
   - [ ] Read default from config if no override provided

5. **Update configuration**
   - [ ] Add `job_provider.provider` option to `config.yaml.example`
   - [ ] Add `brightdata` section with API key, poll settings, dataset ID
   - [ ] Add `get_brightdata_api_key()` to `src/config.py`
   - [ ] Add `get_job_provider()` to `src/config.py`

6. **Update consumers to use factory**
   - [ ] Update `backend/routers/search.py`
   - [ ] Update `backend/services/webapp_scheduler.py`
   - [ ] Update `src/scheduler/job_scheduler.py`
   - [ ] Update any test files that import `ApifyJobImporter`

7. **Testing**
   - [ ] Test Bright Data API with real credentials (small max_results)
   - [ ] Verify Apify still works after refactor
   - [ ] Test fallback from Bright Data to Apify in 'auto' mode
   - [ ] Test config switching between providers

### Optional Enhancements

8. **Frontend provider selection**
   - [ ] Add provider dropdown to GetJobs.tsx
   - [ ] Add `provider` field to `SearchJobCreate` schema
   - [ ] Pass provider to backend in search request

9. **Performance optimizations**
   - [ ] Add response caching (5 min TTL for identical searches)
   - [ ] Implement exponential backoff for retries
   - [ ] Add rate limit tracking per provider

10. **Monitoring**
    - [ ] Log provider used for each search
    - [ ] Track success/failure rates per provider
    - [ ] Add provider info to search performance metrics

---

## Resources

- **Bright Data SDK:** https://github.com/brightdata/sdk-python
- **Bright Data Docs:** https://docs.brightdata.com/api-reference/web-scraper-api/social-media-apis/linkedin
- **Example Implementation:** https://github.com/brightdata/linkedin-job-hunting-assistant
- **API Key Management:** https://brightdata.com/cp/api_keys
