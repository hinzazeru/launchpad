# Analytics Page Implementation Plan

## Goal
Create a visual "Analytics" dashboard to help users understand their job search performance, identify market trends, and spot skill gaps.

## User Review Required
> [!NOTE]
> This page relies on data stored in `MatchResult` and `JobPosting`. The richness of the "Skills" charts depends on how well the backend extracts and stores `required_skills` and `missing_domains`.

## Proposed Features

### 1. Key Metrics Cards (Top Row)
- **Total Jobs Scanned**: Volume of market coverage.
- **High Matches (>70%)**: Number of quality opportunities found.
- **AI Analysed**: Number of jobs re-ranked by Gemini.
- **Saved/Liked**: Count of saved bullets or jobs (if tracking exists).

### 2. Visualizations
- **Match Quality Distribution** (Bar Chart): Breakdown of scores (0-50, 50-70, 70-85, 85+).
- **Top In-Demand Skills** (Horizontal Bar): Aggregation of skills from high-match jobs.
- **Skill Gaps** (Horizontal Bar): Most frequent missing domains/skills in otherwise good matches.
- **Activity Timeline** (Line Chart): Jobs fetched/matched per day over the last 30 days.

## Technical Architecture

### Backend
- **New Router**: `backend/routers/analytics.py`
- **Endpoints**:
  - `GET /analytics/summary`: Aggregate counts.
  - `GET /analytics/skills`: Top present vs. missing skills/domains.
  - `GET /analytics/timeline`: Daily activity stats.

### Frontend
- **Library**: `recharts` for visualization (standard React charting library).
- **Page**: `frontend/src/pages/Analytics.tsx`.
- **Components**:
  - `MetricCard`: Reusable stats card.
  - `SkillsChart`: Bar chart for skills.
  - `ScoreDistributionChart`: Histogram for match scores.

## Proposed Changes

### Backend
#### [NEW] [backend/routers/analytics.py](file:///absolute/path/to/backend/routers/analytics.py)
- Implement SQL queries to aggregate data efficiently.

#### [MODIFY] [backend/main.py](file:///Users/hinza/Library/CloudStorage/OneDrive-Personal/[20] Project/ClaudeProjects/LinkedInJobSearch/backend/main.py)
- Register the new analytics router.

### Frontend
#### [NEW] [frontend/src/pages/Analytics.tsx](file:///absolute/path/to/frontend/src/pages/Analytics.tsx)
- Main dashboard layout.

#### [MODIFY] [frontend/src/App.tsx](file:///Users/hinza/Library/CloudStorage/OneDrive-Personal/[20] Project/ClaudeProjects/LinkedInJobSearch/frontend/src/App.tsx)
- Add route for `/analytics`.

#### [MODIFY] [frontend/src/components/Layout.tsx](file:///Users/hinza/Library/CloudStorage/OneDrive-Personal/[20] Project/ClaudeProjects/LinkedInJobSearch/frontend/src/components/Layout.tsx)
- Add "Analytics" link to the navigation sidebar/header.
