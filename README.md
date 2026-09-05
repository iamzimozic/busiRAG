# busiRAG

**Financial & Business Intelligence RAG System**

busiRAG is a production-oriented Retrieval-Augmented Generation (RAG) system for asking grounded questions about company financial documents. It combines document-aware ingestion, hybrid dense+sparse retrieval, neural reranking, citation-grounded generation, Redis caching, PostgreSQL/pgvector, observability, Docker, and automated CI.

busiRAG focuses on the engineering around RAG—not just the LLM call: versioned ingestion, hybrid retrieval, reranking, grounded generation, caching, observability, migrations, containers, and CI.

The project is designed around an engineering question: **how do you turn RAG from a demo into a reproducible, testable service?**

## What it does

busiRAG ingests company reports in PDF and DOCX formats, preserves document structure and table context, creates versioned chunks and embeddings, and indexes them in PostgreSQL.

At query time it:

1. Validates the request.
2. Checks Redis for a deterministic cached response.
3. Retrieves candidates using both vector similarity and PostgreSQL full-text search.
4. Fuses the retrieval results with Reciprocal Rank Fusion (RRF).
5. Reranks the candidates with `BAAI/bge-reranker-v2-m3`.
6. Builds a context for the generation model.
7. Generates a structured answer with Gemini.
8. Returns the answer together with supporting sources.
9. Records latency, cache, source-count, and error metrics.

## Architecture

```text
                         ┌──────────────────────┐
                         │       FastAPI        │
                         │       /query         │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │      RAG Service     │
                         └──────────┬───────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
             ┌─────────────┐                 ┌─────────────┐
             │    Redis    │                 │  Retrieval  │
             │    Cache    │                 │   Pipeline  │
             └─────────────┘                 └──────┬──────┘
                                                    │
                              ┌─────────────────────┴─────────────────────┐
                              │                                           │
                              ▼                                           ▼
                     ┌─────────────────┐                         ┌─────────────────┐
                     │ Dense Retrieval │                         │ Sparse Retrieval│
                     │   pgvector      │                         │ PostgreSQL FTS  │
                     └────────┬────────┘                         └────────┬────────┘
                              └──────────────────┬────────────────────────┘
                                                 ▼
                                      ┌────────────────────┐
                                      │      RRF Fusion    │
                                      └──────────┬─────────┘
                                                 ▼
                                      ┌────────────────────┐
                                      │  BGE Reranker      │
                                      │ bge-reranker-v2-m3 │
                                      └──────────┬─────────┘
                                                 ▼
                                      ┌────────────────────┐
                                      │  Context Builder   │
                                      └──────────┬─────────┘
                                                 ▼
                                      ┌────────────────────┐
                                      │ Gemini Generation  │
                                      └──────────┬─────────┘
                                                 ▼
                                      ┌────────────────────┐
                                      │ Answer + Citations │
                                      └────────────────────┘

Documents
   │
   ▼
┌──────────────────────┐
│ PDF / DOCX Extraction│
│ Layout + Tables      │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Normalization        │
│ + Table Context      │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Versioned Chunking   │
│ + Metadata + Hashing │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ BGE-small Embeddings │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ PostgreSQL + pgvector│
│ + PostgreSQL FTS     │
└──────────────────────┘
```

## Key engineering decisions

### Structure-aware document ingestion

The ingestion pipeline handles both PDF and DOCX documents. PDF extraction uses PyMuPDF and explicit table-region processing so table content can retain surrounding document context rather than being treated as arbitrary text.

The ingestion pipeline is versioned. Current pipeline identity includes:

- Chunking version: `v3-table-context`
- Embedding model: `BAAI/bge-small-en-v1.5`
- Embedding version: `v1`

Document identity uses content and pipeline metadata, allowing the system to distinguish different indexed representations of the same source document.

### Hybrid retrieval

Dense retrieval and lexical retrieval solve different failure modes.

- **Dense retrieval** uses normalized BGE embeddings and pgvector cosine similarity.
- **Sparse retrieval** uses PostgreSQL full-text search with a GIN index.
- **RRF** combines the ranked candidate lists without requiring the scores from the two retrieval systems to be directly comparable.
- **Reranking** then applies `BAAI/bge-reranker-v2-m3` to the retrieved candidates before generation.

The current retrieval configuration uses 50 candidates before reranking and returns 10 final sources.

### Citation-grounded generation

Generation is separated from retrieval behind a generation service/provider abstraction. Gemini is currently used as the generation provider, while a mock provider supports deterministic tests.

The generation prompt requires the model to:

- answer only from retrieved sources,
- avoid inventing financial figures,
- preserve units and reporting periods,
- cite factual claims using the supplied sources,
- return a structured response containing an answer and citations.

### Deterministic caching

Redis caches complete RAG responses using a deterministic cache key derived from the normalized query and retrieval/pipeline configuration.

The key includes version-sensitive parameters such as:

- chunking version,
- embedding model,
- candidate count,
- final top-k.

This prevents a response generated under one retrieval configuration from silently being reused after the indexed pipeline changes.

Default cache TTL: **3600 seconds**.

### Observability

The API exposes Prometheus metrics at `/metrics` and records structured JSON query logs.

Tracked metrics include:

- total queries,
- cache hits/misses,
- query errors,
- retrieval latency,
- generation latency,
- total query latency.

Each request receives an `X-Request-ID` response header, allowing a query to be correlated across logs and request-level diagnostics without logging the user's query text.

### Error boundaries

Application-specific exceptions separate invalid input, retrieval failures, generation failures, and configuration failures. FastAPI maps these errors to appropriate HTTP responses rather than leaking implementation details through generic failures.

## Tech stack

| Area | Technology |
|---|---|
| API | FastAPI |
| Language | Python 3.12+ |
| Database | PostgreSQL 16 |
| Vector search | pgvector |
| Sparse search | PostgreSQL Full-Text Search |
| Embeddings | `BAAI/bge-small-en-v1.5` |
| Reranking | `BAAI/bge-reranker-v2-m3` |
| Generation | Gemini |
| Cache | Redis 7 |
| ORM | SQLAlchemy |
| Migrations | Alembic |
| Validation | Pydantic |
| Testing | pytest |
| Metrics | Prometheus client |
| Containers | Docker / Docker Compose |
| CI | GitHub Actions |

## Project structure

```text
busiRAG/
├── src/busirag/
│   ├── api/             # FastAPI application and API schemas
│   ├── cache/           # Cache abstraction, Redis implementation, keys, serialization
│   ├── config/          # Settings and configuration validation
│   ├── db/              # SQLAlchemy models, database session, base metadata
│   ├── embeddings/      # Embedding provider abstraction and local provider
│   ├── errors/          # Application-specific exceptions
│   ├── extraction/      # PDF/DOCX extraction, normalization, and table handling
│   ├── generation/      # Generation providers, prompts, context, parsing, responses
│   ├── observability/   # Structured logging and Prometheus metrics
│   ├── rag/             # End-to-end RAG orchestration
│   ├── reranking/       # Reranker abstraction and local implementation
│   ├── retrieval/       # Dense, sparse, hybrid, and reranked retrieval
│   ├── chunking.py      # Chunk construction
│   ├── evaluation.py    # Retrieval evaluation utilities
│   ├── ingestion.py     # Document ingestion orchestration
│   ├── parser.py        # Document parser routing
│   ├── hashing.py       # Content hashing
│   └── versioning.py    # Pipeline identity/version definitions
│
├── alembic/             # Database migrations
├── data/
│   └── evaluation/      # Reproducible retrieval benchmark
├── docker/
│   └── postgres/        # PostgreSQL initialization
├── scripts/             # Corpus ingestion and utility scripts
├── tests/               # Unit/API/integration tests
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── requirements.docker.txt
└── pyproject.toml
```

## Running locally

### Prerequisites

- Python 3.12+
- Docker Desktop with WSL2 integration (or Docker Engine)
- A Gemini API key for live generation

### 1. Clone the repository

```bash
git clone https://github.com/iamzimozic/busiRAG.git
cd busiRAG
```

### 2. Create the environment

Create and activate a Python environment, then install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install --no-deps .
```

### 3. Configure environment variables

Create `.env` in the project root:

```env
DATABASE_URL=postgresql+psycopg://busirag:busirag@localhost:5432/busirag
REDIS_URL=redis://localhost:6379/0
CACHE_TTL=3600
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
CANDIDATE_K=50
TOP_K=10
```

**Never commit `.env` or API keys.**

### 4. Start infrastructure

```bash
docker compose up -d postgres redis
```

Run database migrations:

```bash
docker compose run --rm migrate
```

### 5. Ingest documents

Place supported documents under:

```text
data/raw/<company>/<year>/<document>
```

Then run the ingestion container:

```bash
docker compose run --rm ingestion python /app/scripts/ingest_corpus.py
```

The ingestion script discovers PDF and DOCX files, derives company/year metadata from the directory structure, extracts and chunks documents, creates embeddings, and inserts new versioned chunks.

### 6. Start the API

```bash
docker compose up -d api
```

Check health:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## API

### Query

`POST /query`

Example:

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query":"What was the company revenue in the latest annual report?"}'
```

The response contains the generated answer and the retrieved supporting sources.

### Health

```text
GET /health
```

Used for service health checks.

### Metrics

```text
GET /metrics
```

Returns Prometheus-compatible metrics for query volume, cache behavior, errors, and latency.

## Testing

Run the normal test suite without external API calls:

```bash
pytest -m "not integration"
```

Integration tests are explicitly marked:

```bash
pytest -m integration
```

The CI pipeline runs the non-integration suite against PostgreSQL/pgvector and Redis services and also builds the Docker image.

## Evaluation

The repository contains an explicit retrieval benchmark at:

```text
data/evaluation/retrieval.json
```

Retrieval evaluation is kept separate from the implementation so that retrieval changes can be measured against a fixed set of expected results instead of being judged only by individual examples.

## CI/CD

GitHub Actions currently performs two jobs:

1. **Tests**
   - Python 3.12
   - PostgreSQL + pgvector service
   - Redis service
   - project installation
   - Alembic migrations
   - non-integration pytest suite

2. **Docker build**
   - builds the application image after the tests pass

This provides a basic quality gate before changes reach the main branch.

## Current scope

The current implementation focuses on the core production-oriented RAG path:

- document ingestion,
- structure-aware extraction,
- versioned chunking and embeddings,
- hybrid retrieval,
- reranking,
- grounded generation,
- citations,
- Redis response caching,
- API error handling,
- structured logging,
- Prometheus metrics,
- Dockerized deployment,
- database migrations,
- automated CI.

## Roadmap

Planned engineering extensions include:

- asynchronous ingestion workers with Celery,
- incremental document update/deletion workflows,
- richer query expansion and metadata filtering,
- expanded retrieval and end-to-end evaluation,
- OpenTelemetry tracing,
- user-facing query/retrieval diagnostics,
- production cloud deployment,
- a dedicated frontend for answers, citations, retrieval scores, latency, and cost.

## Why this project exists

A RAG demo can be built by connecting an embedding model to a vector database and an LLM. That is not the problem busiRAG is trying to solve.

The goal here is to build the **engineering system around RAG**: reproducible ingestion, versioned data pipelines, multiple retrieval strategies, reranking, grounded generation, caching, observability, testing, migrations, containers, and CI.

That makes the project a practical exploration of what it takes to move an AI application from a prototype toward a maintainable production service.
