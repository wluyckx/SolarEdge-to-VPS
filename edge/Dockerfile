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

COPY src/ src/

STOPSIGNAL SIGTERM

HEALTHCHECK --interval=60s --timeout=5s --start-period=30s --retries=3 \
    CMD test -f /data/health.json || exit 1

CMD ["python", "-m", "edge.src.main"]
