# Stage 1: Frontend build
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python dependency build
FROM python:3.10-slim AS builder

WORKDIR /app

# Install system dependencies for psycopg2 and spacy
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first (avoids pulling ~2GB of CUDA libraries)
RUN pip install --no-cache-dir --user torch --index-url https://download.pytorch.org/whl/cpu

# Copy requirements and install remaining deps (torch already satisfied)
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 3: Production
FROM python:3.10-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY backend/ ./backend/
COPY src/ ./src/
COPY data/ ./data/

# Copy frontend build output from frontend stage
COPY --from=frontend /app/frontend/dist ./frontend/dist/

# Set Python path for imports
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port (Railway sets PORT dynamically)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/api/health')" || exit 1

# Start with Gunicorn — use shell form so $PORT is expanded at runtime
# Timeout disabled: single worker runs long background tasks (Gemini AI matching)
# Docker HEALTHCHECK and Railway handle container-level health monitoring
CMD gunicorn backend.main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind "[::]:${PORT:-8000}" --timeout 0
