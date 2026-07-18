# ─── BODH AI — Dockerfile ────────────────────────────────────────────────────
# Built by GitHub Actions and pushed to ghcr.io.
# Uses CPU-only torch to stay within Render Free tier memory limits.

FROM python:3.11.9-slim

# ── System dependencies ───────────────────────────────────────────────────────
# curl: required for Docker health check
# libgomp1: required by sentence-transformers / torch CPU
# build-essential: needed for chromadb native extensions
RUN apt-get update && apt-get install -y \
    curl \
    libgomp1 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Install Python dependencies ───────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Copy application code ─────────────────────────────────────────────────────
COPY . .

# ── Create directories for persistent data ────────────────────────────────────
RUN mkdir -p /app/chroma_db /app/data

# ── Environment defaults ──────────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    DB_PATH=/app/data/teaching_assistant.db \
    CHROMA_DB_PATH=/app/chroma_db \
    ANONYMIZED_TELEMETRY=False \
    PORT=5000

# ── Expose port ───────────────────────────────────────────────────────────────
EXPOSE 5000

# ── Start command ─────────────────────────────────────────────────────────────
CMD gunicorn app:app --workers 1 --threads 2 --bind 0.0.0.0:$PORT