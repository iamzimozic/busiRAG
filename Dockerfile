FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

# CPU-only PyTorch by default: the CUDA wheels add several GB and most
# low-cost hosts have no GPU. Build with
#   --build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cu130
# for a GPU image.
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu

COPY requirements.docker.txt .

RUN pip install --upgrade pip \
    && pip install --index-url ${TORCH_INDEX_URL} torch==2.14.0 \
    && pip install -r requirements.docker.txt

COPY pyproject.toml .
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .
COPY scripts/ scripts/

RUN pip install --no-deps .

# Bake the embedding model into the image so cold starts do not
# download it. Set to "" to skip.
ARG PRELOAD_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5

RUN if [ -n "${PRELOAD_EMBEDDING_MODEL}" ]; then \
        python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${PRELOAD_EMBEDDING_MODEL}')"; \
    fi

EXPOSE 8000

# Hosts such as Railway and Render provide $PORT.
CMD ["sh", "-c", "uvicorn busirag.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
