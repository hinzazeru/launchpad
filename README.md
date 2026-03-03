# LaunchPad

**AI-powered LinkedIn job matching for product managers and knowledge workers.**

LaunchPad fetches job postings from LinkedIn, matches them against your resume using NLP or Gemini AI, and helps you rewrite resume bullets to target specific roles — all from a clean web interface.

---

## Features

- **Job Fetching** — Pull fresh LinkedIn jobs via Apify or Bright Data (configurable)
- **Dual-Mode Matching** — NLP matching (free, fast) or Gemini AI matching (richer insights: strengths, concerns, skill gaps)
- **AI Bullet Rewrites** — Gemini rewrites your resume bullets to align with job requirements; suggestions are saved to avoid re-running expensive LLM calls
- **Scheduled Searches** — Run job searches on a schedule via the web UI or Telegram bot
- **Analytics Dashboard** — Track match performance, Gemini usage, and search history
- **Resume Management** — Upload and switch between multiple resume profiles

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10, FastAPI, SQLAlchemy |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Database | SQLite (local) / PostgreSQL (production) |
| AI | Google Gemini (2.0 Flash / 2.5 Flash) |
| Job Data | Apify LinkedIn Scraper, Bright Data LinkedIn Jobs API |
| Notifications | Telegram Bot API |
| Deployment | Docker, Railway |

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node 20+
- An [Apify](https://console.apify.com) or [Bright Data](https://brightdata.com) API key
- A [Google Gemini](https://aistudio.google.com/app/apikey) API key (optional, for AI features)

### 1. Clone and configure

```bash
git clone https://github.com/your-username/launchpad.git
cd launchpad

cp config.yaml.example config.yaml
# Edit config.yaml and fill in your API keys
```

### 2. Install backend dependencies

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 4. Run locally

```bash
# Terminal 1 — backend
uvicorn backend.main:app --reload

# Terminal 2 — frontend
cd frontend && npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

### 5. (Optional) Docker

```bash
docker build -t launchpad .
docker run -p 8000:8000 --env-file .env launchpad
```

---

## Configuration

All configuration lives in `config.yaml`. Copy `config.yaml.example` to get started:

```bash
cp config.yaml.example config.yaml
```

Key sections:

| Section | Description |
|---------|-------------|
| `database` | SQLite path or PostgreSQL URL |
| `apify` / `brightdata` | Job data provider credentials |
| `job_provider` | Which provider to use (`apify`, `brightdata`, or `auto`) |
| `matching` | Engine mode (`nlp`, `gemini`, or `auto`), weights, thresholds |
| `gemini` | Gemini API key, model selection, rate limits |
| `scheduling` | Automated search intervals and keyword profiles |
| `telegram` | Bot token and authorized user ID |
| `email` / `sheets` | Optional Gmail and Google Sheets integration |

See `config.yaml.example` for full documentation of every option.

---

## Resume Format

Resumes are stored as JSON in `data/resumes/`. See `data/resumes/basic_resume.json` for a complete example demonstrating the schema.

Key fields:
- `contact` — name, location, email
- `skills` — technical, product, tools, analytics, domains
- `experience` — company, title, bullets with keywords and metrics
- `education` — institution, degree, field

Domain values in `skills.domains` must use keys from `data/domain_expertise.json` (e.g., `"financial_services"`, `"b2b_saas"`) for correct matching.

---

## Deployment

LaunchPad is designed for one-click deployment on [Railway](https://railway.app).

See [`docs/RAILWAY_DEPLOYMENT.md`](docs/RAILWAY_DEPLOYMENT.md) for the full guide, including:
- Environment variable reference
- PostgreSQL setup
- Common operations (deploy, logs, variables)
- Troubleshooting

---

## Project Structure

```
backend/          FastAPI app (routers, schemas, pipeline)
src/              Core library (matching, importers, database, bot)
frontend/         React/TypeScript web app
data/             Resume files, skill dictionaries, domain expertise
docs/             Architecture and deployment guides
scripts/          One-off analysis and backfill scripts
config.yaml.example  Configuration template
Dockerfile        Multi-stage production build
railway.json      Railway deployment config
```

---

## License

MIT — see [LICENSE](LICENSE) for details.
