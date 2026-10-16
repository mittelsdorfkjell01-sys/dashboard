# Backend API image: FastAPI + SQLAlchemy/PostGIS client + ERA5/live deps.
# Runs Alembic migrations on start, then serves uvicorn (see scripts/entrypoint.sh).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first for layer caching. All runtime deps ship manylinux wheels
# (psycopg[binary], shapely, numpy, pyarrow, pillow), so no compiler is needed.
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Application code + migration tooling.
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY scripts ./scripts
COPY config/europe-wind-measurement.json ./config/europe-wind-measurement.json

RUN chmod +x scripts/entrypoint.sh && mkdir -p data/media

EXPOSE 8000

# Container-level healthcheck: hits /health (DB round-trip). A dead DB → 503 →
# urlopen raises → unhealthy. Redis-down returns 200 (degraded) → stays healthy.
HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=4).status==200 else 1)" || exit 1

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
