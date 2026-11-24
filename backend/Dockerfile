# Kotha backend. Build context is the REPO ROOT (the app reads demo_assets/ at <root>/demo_assets).
#   docker build -f backend/Dockerfile -t kotha-backend .
FROM python:3.12-slim AS base

# ffmpeg is a hard runtime dependency: every uploaded recording is transcoded to 16 kHz mono WAV.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ /app/backend/
COPY demo_assets/ /app/demo_assets/
# Glossary CSV only (a lexical resource). The audio corpus (data/audio) is NEVER copied into an image.
COPY data/glossary/ /app/data/glossary/
COPY scripts/ /app/scripts/

# Run as a non-root user. Nothing is written to disk by the app (in-memory sessions only).
RUN useradd --create-home --uid 10001 kotha && chown -R kotha /app
USER kotha

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
