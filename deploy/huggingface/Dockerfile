# Hugging Face Space (Docker SDK): busiRAG API + frontend in one container.
#
# The Space repository only needs this Dockerfile and README.md; the
# code is cloned from GitHub at build time. Use "Factory rebuild" in
# the Space settings to pick up new commits on GIT_REF.
#
# Space *variables* are passed as build args (VITE_DEMO_EMAIL,
# VITE_DEMO_PASSWORD, GIT_REF); Space *secrets* are available at runtime.

ARG GIT_REPO=https://github.com/iamzimozic/busiRAG.git
ARG GIT_REF=main

# ---------------------------------------------------------------------
# 1. Source + frontend build
# ---------------------------------------------------------------------
FROM node:22-slim AS frontend

ARG GIT_REPO
ARG GIT_REF
# The demo login is intentionally public: it is embedded in the page
# and the API runs with DEMO_MODE=true (read-only).
ARG VITE_DEMO_EMAIL=""
ARG VITE_DEMO_PASSWORD=""
ARG VITE_MAX_QUERY_LENGTH=500

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch "${GIT_REF}" "${GIT_REPO}" /src

WORKDIR /src/frontend

# Empty API base URL = same origin (the API serves the frontend).
ENV VITE_API_BASE_URL="" \
    VITE_DEMO_MODE=true

RUN npm ci && npm run build

# ---------------------------------------------------------------------
# 2. API image (mirrors the repository Dockerfile)
# ---------------------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=7860 \
    HOME=/home/user \
    HF_HOME=/home/user/.cache/huggingface \
    FRONTEND_DIST=/app/frontend/dist \
    DEMO_MODE=true \
    RETRIEVAL_MODE=hybrid

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=frontend /src/requirements.docker.txt .

RUN pip install --upgrade pip \
    && pip install --index-url https://download.pytorch.org/whl/cpu torch==2.14.0 \
    && pip install -r requirements.docker.txt

COPY --from=frontend /src/pyproject.toml .
COPY --from=frontend /src/src/ src/
COPY --from=frontend /src/alembic/ alembic/
COPY --from=frontend /src/alembic.ini .
COPY --from=frontend /src/scripts/ scripts/
COPY --from=frontend /src/frontend/dist/ frontend/dist/

RUN pip install --no-deps .

# Spaces run the container as uid 1000.
RUN useradd -m -u 1000 user && chown -R user /app

USER user

# Bake the embedding model into the image (no download on cold start).
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"

EXPOSE 7860

CMD ["sh", "-c", "alembic upgrade head && uvicorn busirag.api.main:app --host 0.0.0.0 --port ${PORT}"]
