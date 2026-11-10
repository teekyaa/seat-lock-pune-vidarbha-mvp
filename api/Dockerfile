# Seat Lock API image: gunicorn web, scheduler, outbox relay and event consumers all run from it.
# Multi-arch: builds on the Oracle Ampere (arm64) VM as well as x86.
FROM python:3.12-slim AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.7.2 /uv /usr/local/bin/uv

WORKDIR /app
# Dependencies first so code changes reuse the cached layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .
# Static files are served by WhiteNoise. DEBUG=1 here only skips the production config checks.
RUN DJANGO_DEBUG=1 DJANGO_SECRET_KEY=build-only-not-secret python manage.py collectstatic --noinput \
    && useradd --system --uid 10001 --home /app seatlock \
    && chown -R seatlock /app

USER seatlock
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)" || exit 1
CMD ["gunicorn", "seatlock.wsgi", "--bind", "0.0.0.0:8000", "--workers", "3", "--threads", "2", \
     "--timeout", "30", "--access-logfile", "-", "--forwarded-allow-ips", "*"]
