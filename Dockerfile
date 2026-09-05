FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.docker.txt .

RUN pip install --upgrade pip \
    && pip install -r requirements.docker.txt

COPY pyproject.toml .
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

RUN pip install --no-deps .

EXPOSE 8000

CMD ["uvicorn", "busirag.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
