# LaunchPad 💸 Web App Setup Guide

This guide covers setting up and running the LaunchPad 💸 web application, which consists of a FastAPI backend and React frontend.

## Table of Contents

- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
- [Development Setup](#development-setup)
- [Production Deployment](#production-deployment)
- [Configuration](#configuration)
- [Architecture Overview](#architecture-overview)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)

## Quick Start

```bash
# Development mode (recommended for local development)
./run_webapp.sh

# Production mode (serves built React app)
./run_webapp.sh --production

# Build frontend and run production
./run_webapp.sh --build
```

## Prerequisites

### Backend
- Python 3.9+
- pip (Python package manager)
- Virtual environment (recommended)

### Frontend
- Node.js 18+ (for development)
- npm 9+

### Optional
- Google Gemini API key (for AI suggestions)

## Development Setup

### 1. Clone and Setup Python Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Setup Frontend

```bash
cd frontend
npm install
cd ..
```

### 3. Configure Environment

Copy the example config and add your API keys:

```bash
cp config.yaml.example config.yaml
```

Edit `config.yaml` to add your Gemini API key (optional, for AI suggestions):

```yaml
gemini:
  api_key: "your-api-key-here"
```

### 4. Run Development Servers

**Option A: Using the startup script (recommended)**

```bash
./run_webapp.sh
```

This starts:
- Backend API at http://localhost:8000
- Frontend dev server at http://localhost:5173

**Option B: Manual startup**

Terminal 1 (Backend):
```bash
source venv/bin/activate
python run_api.py
```

Terminal 2 (Frontend):
```bash
cd frontend
npm run dev
```

### 5. Access the App

- **Web App:** http://localhost:5173
- **API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/api/health

## Production Deployment

### 1. Build the Frontend

```bash
cd frontend
npm run build
cd ..
```

This creates an optimized build in `frontend/dist/`.

### 2. Run in Production Mode

```bash
python run_api.py --production --port 8000
```

Or using the startup script:

```bash
./run_webapp.sh --production
```

In production mode:
- FastAPI serves the React build from `frontend/dist/`
- All routes are handled by the SPA
- No CORS needed (same origin)
- Hot-reload is disabled

### 3. Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PRODUCTION` | Enable production mode | `false` |
| `PORT` | Server port | `8000` |

### 4. Deployment Options

#### Local/VPS Deployment

```bash
# Using systemd service
sudo cp resume-targeter.service /etc/systemd/system/
sudo systemctl enable resume-targeter
sudo systemctl start resume-targeter
```

Example systemd service file:

```ini
[Unit]
Description=LaunchPad 💸 Web App
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/LinkedInJobSearch
Environment=PRODUCTION=true
ExecStart=/path/to/venv/bin/python run_api.py --production
Restart=always

[Install]
WantedBy=multi-user.target
```

#### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Build frontend
RUN apt-get update && apt-get install -y nodejs npm
RUN cd frontend && npm install && npm run build

ENV PRODUCTION=true
EXPOSE 8000

CMD ["python", "run_api.py", "--production"]
```

## Configuration

### config.yaml

```yaml
# Gemini AI Configuration (optional)
gemini:
  api_key: "your-gemini-api-key"  # Required for AI suggestions
  model: "gemini-pro"

# Database
database:
  url: "sqlite:///./data/jobs.db"

# Resume Library
resume_library:
  path: "./resume_library"
```

### Frontend Environment

The frontend uses Vite's proxy for API calls in development. No `.env` file is needed.

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    Web Browser                       │
│  ┌─────────────────────────────────────────────┐    │
│  │           React Frontend (SPA)               │    │
│  │  - Dashboard (job selection, analysis)       │    │
│  │  - Library (resume management)               │    │
│  │  - Components (BulletEditor, ExportButton)   │    │
│  └─────────────────────────────────────────────┘    │
└────────────────────────┬────────────────────────────┘
                         │ HTTP/REST
                         ▼
┌─────────────────────────────────────────────────────┐
│                  FastAPI Backend                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ /api/jobs│  │/api/resume│ │  /api/analysis   │   │
│  └────┬─────┘  └─────┬────┘  └────────┬─────────┘   │
│       │              │                │             │
│       ▼              ▼                ▼             │
│  ┌──────────────────────────────────────────────┐   │
│  │              Business Logic                   │   │
│  │  - RoleAnalyzer (NLP scoring)                │   │
│  │  - BulletRewriter (Gemini AI suggestions)    │   │
│  │  - ResumeParser (text/JSON parsing)          │   │
│  └──────────────────────────────────────────────┘   │
│       │              │                │             │
│       ▼              ▼                ▼             │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ SQLite DB│  │File System│ │   Gemini API     │   │
│  └──────────┘  └──────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, TypeScript, Tailwind CSS, Framer Motion |
| Build | Vite |
| Backend | FastAPI, Pydantic |
| Database | SQLite + SQLAlchemy |
| AI | Google Gemini API |
| NLP | sentence-transformers |

## API Reference

### Jobs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/jobs` | GET | List jobs with filters |
| `/api/jobs/{id}` | GET | Get job by ID |
| `/api/jobs/stats/summary` | GET | Job statistics |

### Resumes

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/resumes` | GET | List saved resumes |
| `/api/resumes` | POST | Upload new resume |
| `/api/resumes/{filename}` | GET | Get resume content |
| `/api/resumes/{filename}` | DELETE | Delete resume |
| `/api/resumes/{filename}/preview` | GET | Get parsed preview |

### Analysis

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analysis/analyze` | POST | Analyze resume vs job |
| `/api/analysis/suggestions` | POST | Generate AI suggestions |
| `/api/analysis/export` | POST | Export tailored resume |
| `/api/analysis/download/{filename}` | GET | Download exported file |
| `/api/analysis/gemini-status` | GET | Check AI availability |

Full API documentation available at `/docs` when the server is running.

## Troubleshooting

### Common Issues

#### "ECONNREFUSED" errors in frontend

The backend API is not running. Start it with:
```bash
python run_api.py
```

#### "Gemini not available" warning

Add your Gemini API key to `config.yaml`:
```yaml
gemini:
  api_key: "your-api-key"
```

#### Frontend build fails

Clear node_modules and reinstall:
```bash
cd frontend
rm -rf node_modules
npm install
npm run build
```

#### Port already in use

Kill the process using the port:
```bash
lsof -ti:8000 | xargs kill -9  # Kill process on port 8000
```

Or use a different port:
```bash
python run_api.py --port 8080
```

#### Database errors

Reset the database:
```bash
rm data/jobs.db
python -c "from src.database.db import init_db; init_db()"
```

### Getting Help

- Check the API health: `curl http://localhost:8000/api/health`
- View API docs: http://localhost:8000/docs
- Check browser console for frontend errors
- Check terminal for backend errors

## Development Tips

### Hot Reload

- **Backend:** Automatically reloads on Python file changes (dev mode)
- **Frontend:** Vite provides instant HMR (Hot Module Replacement)

### Adding New API Endpoints

1. Create route in `backend/routers/`
2. Add Pydantic models for request/response
3. Include router in `backend/main.py`
4. Add TypeScript types in `frontend/src/services/api.ts`

### Adding New UI Components

1. Create component in `frontend/src/components/`
2. For shadcn-style components, add to `frontend/src/components/ui/`
3. Use existing patterns from `button.tsx`, `card.tsx`, etc.

### Running Tests

```bash
# Backend tests
pytest backend/tests/

# Frontend type check
cd frontend && npm run build
```
