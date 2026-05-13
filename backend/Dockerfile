FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .

RUN pip install --no-cache-dir -e ".[dev]"

COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

CMD ["uvicorn", "rag_qa.main:app", "--host", "0.0.0.0", "--port", "8000"]
