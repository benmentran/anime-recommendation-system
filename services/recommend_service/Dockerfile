FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# NOTE: build context is the repo root (see docker-compose.yml), so that the
# shared pipelines/rag_prompt.py can be baked in without duplicating code.
COPY services/recommend_service/requirements.txt .
RUN pip install -r requirements.txt

COPY services/recommend_service ./services/recommend_service
COPY services/__init__.py ./services/__init__.py
COPY pipelines/rag_prompt.py ./pipelines/rag_prompt.py
COPY pipelines/__init__.py ./pipelines/__init__.py

EXPOSE 8001

CMD ["uvicorn", "services.recommend_service.app:app", "--host", "0.0.0.0", "--port", "8001"]
