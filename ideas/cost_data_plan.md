# Plan: Add "Costs" Tab to Analytics Page

## Context
The user currently has to visit each provider's billing page separately (Gemini, Apify, Bright Data, Railway) to understand LaunchPad's running costs. The goal is to add a "Costs" tab under the existing Analytics page that aggregates cost data from all providers in one place.

### Provider API Feasibility (from research)
- **Gemini**: No billing API. But we already track `tokens_used` in `APICallMetric` for every Gemini call. We can **estimate costs** using known pricing ($0.10/1M input, $0.40/1M output for Flash).
- **Apify**: Has a full monthly usage API via Python SDK (`client.user().monthly_usage()`). Returns per-actor costs, datasets, etc.
- **Bright Data**: Only has a balance endpoint, no per-request cost breakdown. We can show current balance.
- **Railway**: Has a GraphQL API (`estimatedUsage` query) that returns cost estimates for the current billing period. Requires a Railway API token.

### Approach
Use a **hybrid model**: internal token tracking for Gemini cost estimates + external API calls for Apify/Railway/Bright Data. Each provider's data is fetched by a new backend endpoint, displayed in a unified Costs tab.

## Changes

### 1. New backend endpoint: `GET /api/analytics/costs`
**File:** `backend/routers/analytics.py`

Add a single endpoint that returns cost data for all providers:

```python
@router.get("/costs")
async def get_cost_summary(days: int = 30, session: Session = Depends(get_db)):
```

Response structure:
```json
{
  "period_days": 30,
  "gemini": {
    "total_tokens": 125000,
    "estimated_cost_usd": 0.05,
    "calls_count": 42,
    "by_type": {"gemini_rerank": {"tokens": 80000, "count": 30}, ...}
  },
  "apify": {
    "monthly_usage_usd": 4.50,
    "plan": "Free",
    "usage_cycle": {"start": "2026-02-01", "end": "2026-02-28"}
  },
  "brightdata": {
    "balance_usd": 12.50,
    "available": true
  },
  "railway": {
    "estimated_cost_usd": 3.20,
    "billing_period": {"start": "...", "end": "..."},
    "available": true
  }
}
```

**Implementation details:**
- **Gemini**: Query `APICallMetric` for `call_type LIKE 'gemini%'` within the period, sum `tokens_used`. Estimate cost at Gemini Flash pricing. No external API needed.
- **Apify**: Call `ApifyClient(token).user().monthly_usage()` — wrap in try/except, return `{"available": false}` if no API key configured.
- **Bright Data**: Call GET `https://api.brightdata.com/customer/balance` with Bearer token — wrap similarly.
- **Railway**: Call Railway GraphQL API `estimatedUsage` query with `RAILWAY_API_TOKEN` env var. Return `{"available": false}` if no token.
- Use the existing `_get_cached`/`_set_cached` pattern with 1-hour TTL.
- Each external provider wrapped in its own try/except so one failure doesn't break the whole response.

### 2. New config entries for Railway API token
**File:** `src/config.py`

Add to `ENV_OVERRIDES`:
```python
"railway.api_token": "RAILWAY_API_TOKEN",
"railway.project_id": "RAILWAY_PROJECT_ID",
```

### 3. New frontend component: `CostsTab`
**File:** `frontend/src/components/analytics/CostsTab.tsx` (new)

Following the `PerformanceTab.tsx` pattern:
- Summary cards at top showing total estimated cost, per-provider breakdown
- Provider-specific sections with detail cards:
  - **Gemini**: Token usage breakdown by type (rerank, suggestions, matching), estimated cost
  - **Apify**: Monthly usage, plan info
  - **Bright Data**: Current balance
  - **Railway**: Current billing period estimate
- Loading/error states matching existing analytics patterns
- Uses lucide icons: `DollarSign`, `Cpu`, `Globe`, `Server`

### 4. Update Analytics page to add Costs tab
**File:** `frontend/src/pages/Analytics.tsx`

- Add "Costs" to the TabsList (change `grid-cols-2` → `grid-cols-3`)
- Add `TabsContent` for "costs" rendering `<CostsTab />`
- Import `DollarSign` icon from lucide-react
- Update tab width from `w-[300px]` → `w-[450px]`

### 5. Add API client hook
**File:** `frontend/src/services/api.ts`

- Add `getCostSummary(days)` method to the api object
- Add `useCostSummary(days)` React Query hook following existing pattern
- Add TypeScript types for the cost response

## Files to Modify
1. `backend/routers/analytics.py` — new `/costs` endpoint
2. `src/config.py` — add `railway.api_token` and `railway.project_id` to ENV_OVERRIDES
3. `frontend/src/components/analytics/CostsTab.tsx` — **new file**
4. `frontend/src/pages/Analytics.tsx` — add third tab
5. `frontend/src/services/api.ts` — add API client method + hook + types

## Verification
1. Run backend tests: `./venv/bin/python -m pytest backend/tests/`
2. Test endpoint locally: `curl http://localhost:8000/api/analytics/costs?days=30`
3. Verify Gemini cost calculation uses actual `tokens_used` from DB
4. Verify graceful degradation when provider API keys are missing (each section shows "Not configured" instead of error)
5. Check frontend renders all provider cards, loading states work
6. Build frontend: `cd frontend && npm run build`
