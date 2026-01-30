# Web App Migration - FastAPI + React Implementation Tasks

## Overview

Migration from Streamlit to a modern FastAPI + React stack for improved UI/UX control, mobile responsiveness, and advanced interactions.

**Estimated Timeline:** 3 weeks
- Week 1: FastAPI Backend API
- Week 2: React Frontend with Core Features
- Week 3: Polish, Animations, Mobile Testing

## Relevant Files

### Backend (FastAPI) - NEW
- `backend/main.py` - FastAPI application entry point with CORS, health checks
- `backend/routers/__init__.py` - Router module initialization
- `backend/routers/jobs.py` - Job listing and filtering endpoints
- `backend/routers/resumes.py` - Resume CRUD endpoints
- `backend/routers/analysis.py` - Analysis, AI suggestions, and export endpoints
- `run_api.py` - FastAPI server runner script

### Frontend (React) - CREATED
- `frontend/package.json` - Node.js dependencies and scripts
- `frontend/vite.config.ts` - Vite build configuration with Tailwind and path aliases
- `frontend/tsconfig.json` - TypeScript configuration
- `frontend/tsconfig.app.json` - TypeScript app config with path aliases
- `frontend/src/main.tsx` - React application entry point
- `frontend/src/App.tsx` - Main application component with routing
- `frontend/src/index.css` - Global styles with Tailwind CSS v4 imports
- `frontend/src/lib/utils.ts` - Utility functions (cn helper)
- `frontend/src/services/api.ts` - API client for backend communication
- `frontend/src/components/Layout.tsx` - Common layout with navigation
- `frontend/src/components/ui/button.tsx` - Button component (shadcn-style)
- `frontend/src/components/ui/card.tsx` - Card component
- `frontend/src/components/ui/select.tsx` - Select dropdown component
- `frontend/src/components/ui/input.tsx` - Input component
- `frontend/src/components/ui/badge.tsx` - Badge component
- `frontend/src/components/ui/progress.tsx` - Progress bar component
- `frontend/src/components/ui/tabs.tsx` - Tabs component
- `frontend/src/pages/Dashboard.tsx` - Main dashboard page (job selection, resume upload, analyze)
- `frontend/src/pages/Library.tsx` - Resume library management page with drag-drop upload

### Frontend (React) - RECENTLY CREATED
- `frontend/src/components/BulletEditor.tsx` - Radio selection + custom edit component for bullet modifications
- `frontend/src/components/ExportButton.tsx` - Preview changes modal + download tailored resume
- `frontend/src/components/AnimatedComponents.tsx` - Framer Motion animation wrappers
- `frontend/src/components/ErrorBoundary.tsx` - Error boundary and API error components
- `frontend/src/components/ui/skeleton.tsx` - Skeleton loader components
- `frontend/src/components/ui/toast.tsx` - Toast notification system with provider

### Frontend (React) - OPTIONAL ENHANCEMENTS
- `frontend/src/pages/Results.tsx` - Separate results page (currently integrated in Dashboard)
- `frontend/src/components/JobSelector.tsx` - Standalone job selector (optional extraction)
- `frontend/src/components/ResumeUploader.tsx` - Standalone uploader (already integrated in Library)

### Existing Backend Logic (REUSED - NO CHANGES)
- `src/targeting/role_analyzer.py` - NLP-based role alignment scoring
- `src/targeting/bullet_rewriter.py` - Gemini-powered bullet suggestions
- `src/resume/parser.py` - Resume parsing (text, markdown, JSON)
- `src/integrations/gemini_client.py` - Gemini API client
- `src/database/db.py` - Database connection
- `src/database/models.py` - SQLAlchemy models (JobPosting, MatchResult, etc.)
- `src/database/crud.py` - Database CRUD operations

### Configuration & Scripts
- `config.yaml` - Application configuration (already has Gemini settings)
- `requirements.txt` - Python dependencies (add FastAPI, uvicorn)
- `run_webapp.sh` - Combined startup script for web app (dev and production modes)
- `run_api.py` - FastAPI server runner with CLI arguments
- `restart_bot.sh` - Update to include API server startup

### Documentation
- `tasks/tasks-webapp-migration.md` - This task file
- `docs/WEBAPP_SETUP.md` - Web app setup and deployment guide
- `.claude/plans/logical-brewing-otter.md` - Original migration plan with framework comparison

## Instructions for Completing Tasks

**IMPORTANT:** As you complete each task, check it off by changing `- [ ]` to `- [x]`. This tracks progress and ensures no steps are skipped.

Example:
- `- [ ] 1.1 Create file` → `- [x] 1.1 Create file` (after completing)

Update the file after completing each sub-task, not just after completing an entire parent task.

## Tasks

### Phase 1: FastAPI Backend API

- [x] 1.0 Set up FastAPI backend structure
  - [x] 1.1 Create `backend/` directory structure
  - [x] 1.2 Create `backend/main.py` with FastAPI app:
    - [x] 1.2.1 Configure CORS middleware for React dev server (localhost:5173)
    - [x] 1.2.2 Add health check endpoints (`/` and `/api/health`)
    - [x] 1.2.3 Include routers with `/api` prefix
    - [x] 1.2.4 Add Gemini availability status to health check
    - [ ] 1.2.5 Add Basic Auth middleware (Optional - Wait for confirmation)
  - [x] 1.3 Create `backend/routers/__init__.py`
  - [x] 1.4 Install dependencies: `pip install fastapi uvicorn python-multipart`

- [x] 2.0 Implement Jobs Router
  - [x] 2.1 Create `backend/routers/jobs.py`:
    - [x] 2.1.1 Define Pydantic response models (`JobResponse`, `JobListResponse`)
    - [x] 2.1.2 Implement `GET /api/jobs` - list jobs with filters (min_score, recency_days, search, limit)
    - [x] 2.1.3 Implement `GET /api/jobs/{job_id}` - get single job details
    - [x] 2.1.4 Implement `GET /api/jobs/stats/summary` - job statistics
  - [x] 2.2 Test jobs endpoints with curl or API docs (`/docs`)
  - [x] 2.3 Implement `POST /api/jobs/fetch` - trigger Apify scraper (add to `backend/routers/jobs.py`)

- [x] 3.0 Implement Resumes Router
  - [x] 3.1 Create `backend/routers/resumes.py`:
    - [x] 3.1.1 Define Pydantic models (`ResumeMetadata`, `ResumePreview`, `ResumeUploadResponse`)
    - [x] 3.1.2 Implement `GET /api/resumes` - list saved resumes from library
    - [x] 3.1.3 Implement `GET /api/resumes/{filename}` - get resume content
    - [x] 3.1.4 Implement `GET /api/resumes/{filename}/preview` - get parsed preview
    - [x] 3.1.5 Implement `POST /api/resumes` - upload new resume (file + name)
    - [x] 3.1.6 Implement `DELETE /api/resumes/{filename}` - delete resume
    - [x] 3.1.7 Implement `POST /api/resumes/parse` - parse content without saving
  - [x] 3.2 Test resume endpoints with file uploads

- [x] 4.0 Implement Analysis Router
  - [x] 4.1 Create `backend/routers/analysis.py`:
    - [x] 4.1.1 Define request/response models (`AnalyzeRequest`, `AnalyzeResponse`, etc.)
    - [x] 4.1.2 Implement lazy loading for heavy models (RoleAnalyzer, BulletRewriter)
    - [x] 4.1.3 Implement `POST /api/analysis/analyze` - analyze resume against job
    - [x] 4.1.4 Implement `POST /api/analysis/suggestions` - generate AI suggestions for role
    - [x] 4.1.5 Implement `POST /api/analysis/export` - export tailored resume
    - [x] 4.1.6 Implement `GET /api/analysis/download/{filename}` - download exported file
    - [x] 4.1.7 Implement `GET /api/analysis/gemini-status` - check AI availability
  - [x] 4.2 Test analysis endpoints

- [x] 5.0 Backend Integration Testing (CRITICAL PATH - Complete before Phase 2)
  - [x] 5.1 Create `backend/tests/test_jobs.py` with pytest tests
  - [x] 5.2 Create `backend/tests/test_resumes.py` with pytest tests
  - [x] 5.3 Create `backend/tests/test_analysis.py` with pytest tests
  - [x] 5.4 Run all tests: `pytest backend/tests/`
  - [x] 5.5 Test full API flow manually via Swagger UI (`/docs`)

- [x] 6.0 Create API Runner Script
  - [x] 6.1 Create `run_api.py` with uvicorn configuration
  - [ ] 6.2 Update `restart_bot.sh` to optionally start API server
  - [ ] 6.3 Add API server to documentation

### Phase 2: React Frontend

- [x] 7.0 Scaffold React Project
  - [x] 7.1 Create React app with Vite: `npm create vite@latest frontend -- --template react-ts`
  - [x] 7.2 Install core dependencies:
    ```bash
    cd frontend
    npm install
    npm install -D tailwindcss @tailwindcss/vite
    npm install react-router-dom lucide-react clsx tailwind-merge class-variance-authority
    npm install @radix-ui/react-slot @radix-ui/react-dialog @radix-ui/react-select
    npm install @radix-ui/react-tabs @radix-ui/react-progress @radix-ui/react-tooltip
    ```
  - [x] 7.3 Configure Tailwind CSS v4 with `@tailwindcss/vite` plugin
  - [x] 7.4 Configure `vite.config.ts` with path aliases and API proxy
  - [x] 7.5 Add Tailwind v4 import to `src/index.css`
  - [x] 7.6 Verify dev server runs: `npm run dev` ✓
  - [x] 7.7 Verify production build: `npm run build` ✓ (364KB gzipped: 117KB)

- [x] 8.0 Set Up UI Components (shadcn-style with Radix primitives)
  - [x] 8.1 Create `src/lib/utils.ts` with `cn()` utility
  - [x] 8.2 Create UI components in `src/components/ui/`:
    - [x] 8.2.1 `button.tsx` - Button with variants (default, outline, ghost, etc.)
    - [x] 8.2.2 `card.tsx` - Card, CardHeader, CardTitle, CardContent, CardFooter
    - [x] 8.2.3 `select.tsx` - Select dropdown with Radix primitives
    - [x] 8.2.4 `input.tsx` - Input field
    - [x] 8.2.5 `badge.tsx` - Badge with variants (default, success, warning, etc.)
    - [x] 8.2.6 `progress.tsx` - Progress bar
    - [x] 8.2.7 `tabs.tsx` - Tabs, TabsList, TabsTrigger, TabsContent
  - [x] 8.3 Verify components render correctly ✓ (build passes, dev server runs)

- [x] 9.0 Set Up API Client and Types
  - [x] 9.1 Create `src/services/api.ts` with TypeScript interfaces:
    - [x] 9.1.1 `Job` interface matching `JobResponse`
    - [x] 9.1.2 `ResumeMetadata`, `ResumePreview`, `ResumeRole` interfaces
    - [x] 9.1.3 `RoleAnalysis`, `BulletScore`, `AnalyzeResponse` interfaces
    - [x] 9.1.4 Request/response types for all API calls
  - [x] 9.2 Create `ApiClient` class with fetch-based methods:
    - [x] 9.2.1 Configure base URL (`/api` with Vite proxy)
    - [x] 9.2.2 Implement `getJobs()`, `getJob()`, `getJobStats()`
    - [x] 9.2.3 Implement `getResumes()`, `getResumePreview()`, `uploadResume()`, `deleteResume()`
    - [x] 9.2.4 Implement `analyzeResume()`, `generateSuggestions()`, `exportResume()`
    - [x] 9.2.5 Implement `getGeminiStatus()`, `getDownloadUrl()`
  - [ ] 9.3 Optionally add React Query for caching (currently using useState)

- [x] 10.0 Create Layout and Navigation
  - [x] 10.1 Create `src/components/Layout.tsx`:
    - [x] 10.1.1 Header with app title and navigation links
    - [x] 10.1.2 Navigation tabs for Dashboard and Library
    - [x] 10.1.3 Main content area with max-width container
    - [x] 10.1.4 Footer
  - [x] 10.1.5 Theme Toggle (Dark/Light mode) support
  - [x] 10.2 Set up React Router in `App.tsx`:
    - [x] 10.2.1 Route `/` → Dashboard
    - [x] 10.2.2 Route `/library` → Library
    - [x] 10.2.3 Results integrated into Dashboard (not separate page)

- [x] 11.0 Build Dashboard Page
  - [x] 11.1 Create `src/pages/Dashboard.tsx`:
    - [x] 11.1.1 Job selection from database
    - [x] 11.1.2 Job filters section (score slider, search input)
    - [x] 11.1.3 Job selector dropdown with score badge
    - [x] 11.1.4 Selected job details card
    - [x] 11.1.5 Resume selector from library
    - [x] 11.1.6 Selected resume details card
    - [x] 11.1.7 Analyze button with loading state
    - [x] 11.1.8 Analysis results with overall metrics
    - [x] 11.1.9 Role cards with expandable bullet scores
    - [x] 11.1.10 AI suggestions generation per role
    - [x] 11.1.11 Gemini availability indicator
    - [x] 11.1.12 "Sync/Fetch Jobs" button in header (triggers 2.3)
  - [ ] 11.2 Extract `JobSelector` as standalone component (optional)
  - [ ] 11.3 Extract `JobDetails` as standalone component (optional)

- [x] 12.0 Build Resume Upload (Integrated in Library)
  - [x] 12.1 Drag-and-drop zone with visual feedback
  - [x] 12.2 File type validation (.txt, .md, .json)
  - [x] 12.3 Name input for uploaded resume
  - [x] 12.4 Upload button with loading state
  - [ ] 12.5 Upload progress indicator (optional enhancement)

- [x] 13.0 Build Library Page
  - [x] 13.1 Create `src/pages/Library.tsx`:
    - [x] 13.1.1 List of saved resumes with cards
    - [x] 13.1.2 Resume card showing name, format, date
    - [x] 13.1.3 Preview modal on eye icon click
    - [x] 13.1.4 Delete button with loading state
    - [x] 13.1.5 Upload section with drag-drop

- [x] 14.0 Build Bullet Editor and Export (Remaining)
  - [x] 14.1 Create `src/components/BulletEditor.tsx`:
    - [x] 14.1.1 Radio buttons: Keep Original, AI options
    - [x] 14.1.2 Expandable custom edit textarea
    - [x] 14.1.3 Show full suggestion text on selection
    - [x] 14.1.4 AI analysis explanation
  - [x] 14.2 Create `src/components/ExportButton.tsx`:
    - [x] 14.2.1 Preview changes modal
    - [x] 14.2.2 Export button with loading state
    - [x] 14.2.3 Download triggered on success
  - [x] 14.3 Integrate bullet selection into Dashboard role cards
  - [x] 14.4 Add export section to Dashboard

### Phase 3: Polish and Integration

- [x] 15.0 Add Loading States and Animations
  - [x] 15.1 Install Framer Motion: `npm install framer-motion`
  - [x] 15.2 Add skeleton loaders for:
    - [x] 15.2.1 Job list loading
    - [x] 15.2.2 Resume list loading
    - [x] 15.2.3 Analysis loading
  - [x] 15.3 Add transitions for:
    - [x] 15.3.1 Page transitions
    - [x] 15.3.2 Modal open/close
    - [x] 15.3.3 Card hover effects
    - [x] 15.3.4 Button click feedback
  - [ ] 15.4 Implement "Optimistic Updates" for mutations (delete/upload)

- [x] 16.0 Mobile Responsiveness
  - [x] 16.1 Test all pages on mobile viewport
  - [x] 16.2 Implement responsive layouts:
    - [x] 16.2.1 Stack columns on mobile
    - [x] 16.2.2 Collapsible sidebar/menu
    - [x] 16.2.3 Touch-friendly buttons and inputs
    - [ ] 16.2.4 Swipe gestures for cards (optional)
  - [ ] 16.3 Test on actual mobile device

- [x] 17.0 Error Handling and Edge Cases
  - [x] 17.1 Add error boundaries
  - [x] 17.2 Handle API errors with toast notifications
  - [x] 17.3 Handle empty states (no jobs, no resumes)
  - [x] 17.4 Handle Gemini unavailable state
  - [x] 17.5 Add retry buttons for failed requests

- [x] 18.0 Production Build and Deployment
  - [x] 18.1 Test production build: `npm run build`
  - [x] 18.2 Configure FastAPI to serve React build
  - [x] 18.3 Update `run_api.py` for production mode
  - [x] 18.4 Create combined startup script (`run_webapp.sh`)
  - [x] 18.5 Test full stack locally

- [x] 19.0 Documentation
  - [ ] 19.1 Update `README.md` with new web app instructions (optional)
  - [x] 19.2 Create `docs/WEBAPP_SETUP.md`:
    - [x] 19.2.1 Development setup (backend + frontend)
    - [x] 19.2.2 Production deployment
    - [x] 19.2.3 Environment variables
    - [x] 19.2.4 Troubleshooting
  - [ ] 19.3 Update `restart_bot.sh` with webapp options (optional)

### Phase 4: Optimization and Enhancements (Recommended)

- [x] 20.0 State Management & Caching (React Query)
  - [x] 20.1 Install dependencies: `npm install @tanstack/react-query`
  - [x] 20.2 Configure `QueryClientProvider` in `main.tsx`
  - [x] 20.3 Refactor `api.ts` to export Query hooks (`useJobs`, `useResumes`)
  - [x] 20.4 Replace `useEffect` fetching in Dashboard/Library with hooks
  - [x] 20.5 Implement cache invalidation for mutations (upload/delete resume)

- [x] 21.0 Advanced Filtering & Sorting
  - [x] 21.1 Update `ListingFilter` component (Implemented in Dashboard):
    - [x] 21.1.1 Add Date Range filter (Last 24h, 7d, 30d)
    - [x] 21.1.2 Add Sort options (Match Score, Date Posted)
  - [x] 21.2 Update `useJobs` hook to support new params

- [ ] 22.0 UX Improvements
  - [ ] 22.1 Persistent Bullet Selection (Local Storage or Store)
    - [ ] 22.1.1 Save draft selections when navigating away
  - [ ] 22.2 Detailed Upload Progress
    - [ ] 22.2.1 Add progress bar to Toast notification
  - [ ] 22.3 Error Handling Polish
    - [ ] 22.3.1 Friendly UI for 429 (Rate Limit) errors for AI features
  - [x] 22.4 Include a dark theme option

---

## Current Progress

**Phase 1: Backend API** - ✅ COMPLETE (Tasks 1-4, 6.1)
- All endpoints implemented and tested
- Jobs, Resumes, Analysis routers functional
- API runner script created
- Remaining: 6.2 (restart_bot.sh), 6.3 (docs)

**Phase 2: React Frontend** - ✅ COMPLETE (Tasks 7-14)
- ✅ React + Vite scaffolded with TypeScript
- ✅ Tailwind CSS v4 configured with @tailwindcss/vite plugin
- ✅ UI components created (Button, Card, Select, Input, Badge, Progress, Tabs)
- ✅ API client service with all endpoints
- ✅ Layout with navigation
- ✅ Dashboard page with job selection, resume selection, analysis, AI suggestions
- ✅ Library page with drag-drop upload and preview modal
- ✅ BulletEditor component with radio selection and custom edit
- ✅ ExportButton component with preview modal and download
- ✅ Integration complete - bullet selection and export in Dashboard
- ✅ Build verified: 375KB (119KB gzipped)

**Phase 3: Polish** - ✅ COMPLETE
- ✅ Framer Motion animations installed and implemented
- ✅ Skeleton loaders for loading states
- ✅ Page transitions, modal animations, card hover effects
- ✅ Mobile responsive layout with hamburger menu
- ✅ Toast notifications for errors and success messages
- ✅ Error boundary components
- ✅ FastAPI configured to serve React build in production
- ✅ Production/development mode support in run_api.py
- ✅ Combined startup script (`run_webapp.sh`)
- ✅ Documentation (`docs/WEBAPP_SETUP.md`)

**Migration Complete!** 🎉

---

## API Endpoints Reference

### Jobs (`/api/jobs`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/jobs` | List jobs with filters |
| GET | `/api/jobs/{id}` | Get job by ID |
| GET | `/api/jobs/stats/summary` | Get job statistics |

### Resumes (`/api/resumes`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/resumes` | List saved resumes |
| GET | `/api/resumes/{filename}` | Get resume content |
| GET | `/api/resumes/{filename}/preview` | Get parsed preview |
| POST | `/api/resumes` | Upload new resume |
| DELETE | `/api/resumes/{filename}` | Delete resume |
| POST | `/api/resumes/parse` | Parse without saving |

### Analysis (`/api/analysis`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/analysis/analyze` | Analyze resume vs job |
| POST | `/api/analysis/suggestions` | Generate AI suggestions |
| POST | `/api/analysis/export` | Export tailored resume |
| GET | `/api/analysis/download/{filename}` | Download exported file |
| GET | `/api/analysis/gemini-status` | Check Gemini availability |

---

## Tech Stack Summary

### Backend
- **Framework:** FastAPI
- **Database:** SQLite + SQLAlchemy (existing)
- **AI:** Google Gemini API (existing)
- **NLP:** sentence-transformers (existing)

### Frontend
- **Framework:** React 18 + TypeScript
- **Build:** Vite
- **Styling:** Tailwind CSS
- **Components:** shadcn/ui
- **State:** React Query + React Router
- **Animations:** Framer Motion
- **Upload:** react-dropzone
