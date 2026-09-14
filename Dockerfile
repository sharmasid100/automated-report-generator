FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MOCK_LLM=true \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-ci.txt requirements-dev.txt requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements-ci.txt -r requirements-dev.txt

COPY src ./src
COPY scripts ./scripts
COPY prompts ./prompts
COPY tests ./tests
COPY data ./data

RUN mkdir -p /app/output /app/processed_data /app/data \
    && useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app

USER appuser

ENTRYPOINT ["python", "src/main.py"]
