# ---------- build stage ----------
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------- runtime stage ----------
FROM python:3.12-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Replicate the edge.src package path so that "from edge.src.X" imports resolve.
# The repo uses edge.src.* imports everywhere; pyproject.toml adds ".." to
# sys.path in dev, and this COPY mirrors the same layout in the container.
COPY src/ edge/src/
RUN touch edge/__init__.py

# Provision health-file directory (AC6 / STORY-015)
RUN mkdir -p /data

# Run as non-root user
RUN useradd --create-home --no-log-init appuser && chown -R appuser /data
USER appuser

STOPSIGNAL SIGTERM

HEALTHCHECK --interval=60s --timeout=5s --start-period=30s --retries=3 \
    CMD test -f /data/health.json || exit 1

CMD ["python", "-m", "edge.src.main"]
