# syntax=docker/dockerfile:1.7

# ── builder: install deps + pre-fetch the fastembed ONNX model ──────────────
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FASTEMBED_CACHE_DIR=/opt/fastembed-cache

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY requirements.txt ./
RUN uv pip install --system --no-cache -r requirements.txt

# Pre-download the default embedding model so the container's first request
# doesn't stall on a ~100 MB download.
RUN mkdir -p "$FASTEMBED_CACHE_DIR" \
 && python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5', cache_dir='$FASTEMBED_CACHE_DIR')"


# ── runtime: slim image, non-root user, auto-migrate on start ───────────────
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_DIR=/opt/fastembed-cache \
    PORT=5057

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates tini \
 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /opt/fastembed-cache /opt/fastembed-cache

WORKDIR /app
COPY . .

RUN useradd -r -u 1000 -m bricksmith \
 && chown -R bricksmith:bricksmith /app /opt/fastembed-cache
USER bricksmith

EXPOSE 5057

# Healthcheck hits the landing page — cheap, no LLM involvement.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS "http://localhost:${PORT}/" > /dev/null || exit 1

ENTRYPOINT ["/usr/bin/tini", "--", "/app/docker-entrypoint.sh"]
CMD ["python", "main.py"]
