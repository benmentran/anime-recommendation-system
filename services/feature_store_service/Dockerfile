# ---------- builder: compile wheels ----------
FROM python:3.10-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /wheels

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .


# Build wheels for all dependencies
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip wheel --no-cache-dir --wheel-dir=/wheels/ -r requirements.txt


# ---------- final: production image ----------
FROM python:3.10-slim AS final

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /wheels /wheels
COPY requirements.txt .

RUN python -m pip install --upgrade pip && \
    pip install --no-index --no-cache-dir --find-links=/wheels -r requirements.txt && \
    rm -rf /wheels /root/.cache/pip /usr/local/lib/python3.10/site-packages/tests

COPY . .

# Expose port for FastAPI
EXPOSE 8002

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8002"]
