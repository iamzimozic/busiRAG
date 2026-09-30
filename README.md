# busiRAG

**Ask questions about annual reports and financial documents, and get answers you can verify: every figure links to the exact passage and page it came from.**

<!--
  DEMO GIF: record a 20–30 second screen capture (question → answer →
  expand a citation → open diagnostics), save it as docs/demo.gif and
  replace the line below with:  ![busiRAG demo](docs/demo.gif)
-->
> _Demo recording coming soon._

<!-- LIVE DEMO: replace "coming soon" with the deployed frontend URL. -->
**Live demo:** _coming soon_ · **Deployment guide:** [DEPLOYMENT.md](DEPLOYMENT.md)

## Measured results

Tested on 40 real questions over 12 annual reports (Apple, Microsoft, NVIDIA and JPMorgan Chase; 5,345 indexed passages). The question set covers exact figures from financial tables, changes over time, comparisons between companies and narrative risk disclosures. Every expected answer was checked against the source documents.

| Search approach | Finds the right passage in the top 5 | … in the top 10 | Typical search time |
|---|---:|---:|---:|
| Keyword search only | 23% | 28% | 2 ms |
| Semantic (vector) search only | 38% | 59% | 30 ms |
| Hybrid (keyword + semantic) | 50% | 56% | 43 ms |
| **Hybrid + AI reranking (busiRAG default)** | **64%** | **68%** | 3.7 s |

Search time is measured on a laptop GPU, before the answer is written. Combining search methods and reranking finds the supporting passage in the top 5 **1.7× as often** as vector search alone, which is the approach most basic RAG demos use. Full methodology and per-category results are under [Evaluation](#evaluation).

<!--
  ANSWER ACCURACY: after running `python scripts/evaluate_answers.py`,
  add the numeric-accuracy, citation-support and refusal rows from
  data/evaluation/results/answer_eval.md here.
-->

## What this means for your business

- **Answers you can check, not just trust.** Every answer cites the document, page and passage it is based on, and the source text is one click away. The system is instructed to say "the documents don't contain this" rather than guess, and the evaluation suite tests for exactly that.
- **Accuracy that is measured, not claimed.** A repeatable benchmark scores every change to the search pipeline, so improvements, and regressions, show up as numbers before they reach users. It can be rebuilt around your own documents and questions.
- **Runs on your own infrastructure.** Search runs entirely on your servers (PostgreSQL plus open-source models). The answer-writing model is swappable: Google Gemini, OpenAI, or a fully local model via Ollama, so confidential documents never have to leave your network.
- **Built for real documents.** PDF and Word files, including financial tables. Per-client workspaces, caching, rate limiting and monitoring are built in, not bolted on later.

---

## How it works

busiRAG ingests company reports in PDF and DOCX formats, preserves document structure and table context, creates versioned chunks and embeddings, and indexes them in PostgreSQL.

At query time it:

1. Validates the request (length limit, per-client and daily rate limits).
2. Checks Redis for a deterministic cached response.
3. Retrieves candidates using both vector similarity and PostgreSQL full-text search.
4. Fuses the retrieval results with Reciprocal Rank Fusion (RRF).
5. Reranks the candidates with `BAAI/bge-reranker-v2-m3` (configurable; can be disabled for CPU hosting).
6. Builds a numbered context for the generation model.
7. Generates a structured answer with the configured LLM (Gemini, OpenAI or Ollama) and validates its citations.
8. Returns the answer, the cited source passages and per-request diagnostics (scores, cache status, latency breakdown).
9. Records latency, cache, source-count and error metrics.

## Architecture

```text
                   ┌──────────────────────────┐
                   │   React frontend (Vite)  │
                   │ answers · citations ·    │
                   │ diagnostics              │
                   └────────────┬─────────────┘
                                ▼
                   ┌──────────────────────────┐
                   │   FastAPI  /query        │
                   │ auth · rate limit · CORS │
                   └────────────┬─────────────┘
                                ▼
                   ┌──────────────────────────┐
                   │       RAG Service        │
                   └────────────┬─────────────┘
                                │
                ┌───────────────┴───────────────┐
                ▼                               ▼
         ┌─────────────┐                 ┌─────────────┐
         │    Redis    │                 │  Retrieval  │
         │    Cache    │                 │   Pipeline  │
         └─────────────┘                 └──────┬──────┘
                                                │
                          ┌─────────────────────┴─────────────────────┐
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
                                  │  (optional)        │
                                  └──────────┬─────────┘
                                             ▼
                                  ┌────────────────────┐
                                  │  Context Builder   │
                                  └──────────┬─────────┘
                                             ▼
                                  ┌────────────────────┐
                                  │ LLM provider       │
                                  │ Gemini · OpenAI ·  │
                                  │ Ollama             │
                                  └──────────┬─────────┘
                                             ▼
                                  ┌────────────────────┐
                                  │ Answer + Citations │
                                  │ + Diagnostics      │
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
│ + generated FTS index│
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
- **Sparse retrieval** uses PostgreSQL full-text search over a generated `tsvector` column with a GIN index.
- **RRF** combines the ranked candidate lists without requiring the scores from the two retrieval systems to be directly comparable.
- **Reranking** applies `BAAI/bge-reranker-v2-m3` to the fused candidates before generation.

`RETRIEVAL_MODE` selects `dense`, `sparse`, `hybrid` or `hybrid_rerank` (default). The default configuration reranks 50 candidates and returns 10 sources. The reranker is only loaded when the mode uses it.

### Evaluation-driven development

Every retrieval mode is measured on the same benchmark (see [Evaluation](#evaluation)). The first ablation run exposed a production bug that unit tests could not: the full-text `search_vector` column was only populated by the migration that created it, so every chunk ingested afterwards was invisible to sparse search and "hybrid" retrieval was silently dense-only. It is now a generated column, and sparse search contributes measurably (hybrid Recall@5 0.375 → 0.500).

### Citation-grounded generation

Generation sits behind a provider interface. `LLM_PROVIDER` selects Gemini (default), OpenAI or a local Ollama model; a mock and a scripted provider support deterministic tests. Contract tests check that every provider produces identical answers and citations for the same model output.

The generation prompt requires the model to:

- answer only from retrieved sources,
- avoid inventing financial figures,
- preserve units and reporting periods,
- cite factual claims using the supplied sources,
- return a structured response containing an answer and citations.

Citations are validated against the supplied context; provider failures and invalid citations surface as a `GenerationError` (HTTP 502).

### Deterministic caching

Redis caches complete RAG responses using a deterministic cache key derived from the normalized query and retrieval/pipeline configuration.

The key includes version-sensitive parameters:

- workspace (tenant),
- chunking version,
- embedding model,
- candidate count and final top-k,
- retrieval mode,
- LLM provider and model.

This prevents a response generated under one configuration from silently being reused after the pipeline, retrieval strategy or model changes.

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

Each request receives an `X-Request-ID` response header, and `/query` returns a `diagnostics` object (cache hit/miss, retrieval mode, model, latency breakdown, every retrieved chunk with its retrieval and reranker scores). The frontend shows this in a collapsible panel.

### Error boundaries and public-demo protection

Application-specific exceptions separate invalid input, retrieval failures, generation failures, configuration failures, rate limiting and disabled features. FastAPI maps them to appropriate HTTP responses (400, 403, 429 with `Retry-After`, 500, 502) rather than leaking implementation details.

For a public demo, `/query` enforces a maximum query length and Redis-backed rate limits (per client IP per minute, and a global daily cap to bound LLM spend). `DEMO_MODE` makes the workspace read-only.

## Tech stack

| Area | Technology |
|---|---|
| API | FastAPI |
| Language | Python 3.12+ |
| Frontend | React 19, TypeScript, Vite |
| Database | PostgreSQL 16 |
| Vector search | pgvector |
| Sparse search | PostgreSQL Full-Text Search |
| Embeddings | `BAAI/bge-small-en-v1.5` |
| Reranking | `BAAI/bge-reranker-v2-m3` |
| Generation | Gemini (default), OpenAI, Ollama |
| Cache / rate limiting | Redis 7 |
| ORM | SQLAlchemy |
| Migrations | Alembic |
| Validation | Pydantic |
| Testing | pytest |
| Metrics | Prometheus client |
| Containers | Docker / Docker Compose |
| CI | GitHub Actions |
| Hosting | Railway (see [DEPLOYMENT.md](DEPLOYMENT.md)) |

## Project structure

```text
busiRAG/
├── src/busirag/
│   ├── api/                 # FastAPI app, schemas, dependencies, rate limiting
│   ├── cache/               # Cache abstraction, Redis implementation, keys, serialization
│   ├── config/              # Settings and configuration validation
│   ├── db/                  # SQLAlchemy models, database session, base metadata
│   ├── embeddings/          # Embedding provider abstraction and local provider
│   ├── errors/              # Application-specific exceptions
│   ├── extraction/          # PDF/DOCX extraction, normalization, and table handling
│   ├── generation/          # LLM providers (Gemini, OpenAI, Ollama, mocks), factory, prompts
│   ├── observability/       # Structured logging and Prometheus metrics
│   ├── rag/                 # End-to-end RAG orchestration
│   ├── reranking/           # Reranker abstraction and local implementation
│   ├── retrieval/           # Dense, sparse, hybrid, reranked retrieval and mode dispatch
│   ├── answer_evaluation.py # End-to-end answer checks (numbers, citations, refusals)
│   ├── evaluation.py        # Retrieval metrics and benchmark loading
│   ├── chunking.py          # Chunk construction
│   ├── ingestion.py         # Document ingestion orchestration
│   ├── parser.py            # Document parser routing
│   ├── hashing.py           # Content hashing
│   └── versioning.py        # Pipeline identity/version definitions
│
├── frontend/                # React + TypeScript UI
├── alembic/                 # Database migrations
├── data/
│   └── evaluation/          # Benchmarks, answer templates and committed results
├── docs/                    # Demo questions
├── docker/
│   └── postgres/            # PostgreSQL initialization
├── scripts/                 # Ingestion, evaluation and demo setup scripts
├── tests/                   # Unit/API/integration tests
├── DEPLOYMENT.md
├── Dockerfile
├── docker-compose.yml
├── railway.json
├── requirements.txt
├── requirements.docker.txt
└── pyproject.toml
```

## Running locally

### Prerequisites

- Python 3.12+
- Node.js 20+ (frontend)
- Docker Desktop with WSL2 integration (or Docker Engine)
- A Gemini or OpenAI API key, or a local [Ollama](https://ollama.com) model

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

Copy the example file and fill in your secrets:

```bash
cp .env.example .env
```

`.env.example` lists every setting with its default. At minimum set `JWT_SECRET_KEY` and the key for your LLM provider.

**Never commit `.env` or API keys.**

#### Choosing a generation provider

Retrieval always runs locally; only answer generation uses an LLM. Select it with `LLM_PROVIDER` (default `gemini`):

| Provider | Settings | Notes |
|---|---|---|
| `gemini` | `GEMINI_API_KEY`, `GEMINI_MODEL` | Default; native structured output |
| `openai` | `OPENAI_API_KEY`, `OPENAI_MODEL` (default `gpt-4.1-mini`), optional `OPENAI_BASE_URL` | Native structured output; `OPENAI_BASE_URL` works with any OpenAI-compatible API |
| `ollama` | `OLLAMA_MODEL` (default `qwen2.5:7b`), `OLLAMA_BASE_URL` (default `http://localhost:11434/v1`) | Fully local, no API key; JSON mode + validated parsing |

All providers return the same structured answer and citations and are validated identically. The provider and model are part of the cache key. From the Docker `api` container, reach an Ollama server on the host with `OLLAMA_BASE_URL=http://host.docker.internal:11434/v1`.

### 4. Start infrastructure

```bash
docker compose up -d postgres redis
```

Run database migrations (the first migration also enables the `vector` extension):

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

The ingestion script discovers PDF and DOCX files, derives company/year metadata from the directory structure, extracts and chunks documents, creates embeddings, and inserts new versioned chunks into workspace 1 (`--tenant-id` to change). Already-ingested files are skipped.

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

### 7. Start the frontend

```bash
cd frontend
cp .env.example .env.local   # set VITE_API_BASE_URL if the API is not on 127.0.0.1:8000
npm install
npm run dev                   # http://localhost:5173
```

Create an account on the sign-in page, or sign in with an existing user.

## API

### Query

`POST /query`

Example:

```bash
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"What was Apple'"'"'s net income in 2023?"}'
```

`$TOKEN` comes from `POST /auth/login`. The response contains:

- `answer`: the generated answer
- `sources`: the cited chunks, with document, company, year, page, section, chunk text, retrieval score and reranker score
- `diagnostics`: request id, cache hit/miss, retrieval mode, generation model, a latency breakdown (`retrieval_ms`, `generation_ms`, `total_ms`) and every retrieved chunk with its scores and whether it was cited

Errors return `{"error": ..., "message": ...}`: 400 for invalid or over-long queries, 403 for actions disabled in demo mode, 429 (with `Retry-After`) when rate limited, 502 when the LLM provider fails.

### Documents and auth

`POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `GET /workspace`, `GET|POST /documents` and `DELETE /documents/{id}` manage users, workspaces and uploaded documents. Every workspace only sees its own documents.

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

Integration tests call real services (the LLM API, a local Ollama server, Redis) and are explicitly marked:

```bash
pytest -m integration
```

The CI pipeline runs the non-integration suite against PostgreSQL/pgvector and Redis services and also builds the Docker image.

## Evaluation

### Retrieval benchmark

The benchmark is [`data/evaluation/retrieval.json`](data/evaluation/retrieval.json): 40 questions over 12 annual reports (Apple 2022–2025, Microsoft 2023–2025, NVIDIA 2024–2026, JPMorgan Chase 2024–2025), in four categories:

| Category | Questions | Example |
|---|---:|---|
| `table_numeric` | 27 | What was JPMorgan Chase's CET1 capital ratio at the end of 2024? |
| `narrative` | 7 | How have U.S. export controls affected NVIDIA's ability to sell to China? |
| `multi_period` | 3 | How did Apple's total net sales change from 2022 to 2023? |
| `comparison` | 3 | Which company had higher net income in fiscal 2025, Microsoft or NVIDIA? |

Relevant chunks are identified by company, year and text anchors (e.g. `["net income", "96,995"]`) rather than database ids, so labels survive re-ingestion, and a fact reported in several places (income statement, cash-flow statement, later filings) counts wherever it appears. Comparison questions must retrieve evidence for every company involved. The evaluation script warns if any label no longer matches the index.

Results (top 10, 50 candidates; latency is retrieval only, measured on an RTX 3060 laptop GPU):

| Retrieval | Recall@5 | Recall@10 | MRR | p50 latency | p95 latency |
|---|---:|---:|---:|---:|---:|
| Dense (pgvector) | 0.375 | 0.588 | 0.259 | 30 ms | 45 ms |
| Sparse (Postgres FTS) | 0.225 | 0.275 | 0.146 | 2 ms | 4 ms |
| Hybrid (RRF) | 0.500 | 0.562 | 0.295 | 43 ms | 53 ms |
| Hybrid + reranker | 0.637 | 0.675 | 0.483 | 3736 ms | 5734 ms |

Recall@10 by question type:

| Retrieval | comparison (n=3) | multi_period (n=3) | narrative (n=7) | table_numeric (n=27) |
|---|---:|---:|---:|---:|
| Dense (pgvector) | 0.500 | 0.667 | 0.857 | 0.519 |
| Sparse (Postgres FTS) | 0.000 | 0.667 | 0.143 | 0.296 |
| Hybrid (RRF) | 0.500 | 0.333 | 0.857 | 0.519 |
| Hybrid + reranker | 0.667 | 1.000 | 0.857 | 0.593 |

Source: [`data/evaluation/results/retrieval_ablation.md`](data/evaluation/results/retrieval_ablation.md). CPU results and the reranker latency/quality tradeoff are in [DEPLOYMENT.md](DEPLOYMENT.md#reranker-latency-vs-quality). With 40 questions, one question moves Recall by 2.5 points, so small differences between modes are within noise.

Reproduce:

```bash
python scripts/evaluate_ablation.py
CUDA_VISIBLE_DEVICES="" python scripts/evaluate_ablation.py --output-dir data/evaluation/results/cpu
```

**Known limitations.** Most misses happen before reranking: the supporting chunk never reaches the 50-candidate pool. Two patterns dominate. First, Microsoft's financial-statement tables (DOCX filings) are not retrieved for net income/revenue questions. Second, Apple's four 10-Ks contain near-identical tables, so a question about 2023 retrieves the same table from another year. Filtering retrieval by the company and fiscal year named in the question is the next planned improvement.

### Answer evaluation

`data/evaluation/answers.json` holds 25 end-to-end cases (20 answerable, 5 deliberately unanswerable). Copy [`answers.template.json`](data/evaluation/answers.template.json) to add your own. Each generated answer is checked for:

- **Numeric accuracy**: the expected figure in the right units (`$96,995 million` and `$97.0 billion` both pass; `$96,995` is a unit error)
- **Citation support**: every cited-evidence requirement is met by a cited chunk that matches the evidence spec or states the expected figure for the right company
- **Refusals**: unanswerable questions are declined, answerable ones are not

The checks are unit-tested with a scripted mock provider. Running against a real provider is a separate, explicit step because it calls the LLM once per case:

```bash
python scripts/evaluate_answers.py                       # LLM_PROVIDER from .env
python scripts/evaluate_answers.py --provider ollama     # local model, no API calls
python scripts/evaluate_answers.py --ids apple_net_income_2023 --sleep 5
pytest -m integration tests/test_answer_evaluation_integration.py
```

Results are written to `data/evaluation/results/answer_eval.json` and `answer_eval.md`.

## Deployment

**Free option:** the demo runs at no cost with the API on Render (a PyTorch-free image that fits the 512 MB free tier by running embeddings with ONNX Runtime), the frontend on Vercel, Neon (PostgreSQL/pgvector), Upstash (Redis) and the Gemini free tier, using documents ingested ahead of time; no file storage needed. See [Free deployment](DEPLOYMENT.md#free-deployment-render--vercel--neon--upstash).

[DEPLOYMENT.md](DEPLOYMENT.md) walks through deploying a public, read-only demo on Railway (API + PostgreSQL/pgvector + Redis) with the frontend on a static host. It covers the measured reranker latency/quality tradeoff for CPU hosting, demo-corpus setup (`scripts/setup_demo.py`) and public-demo protection (`RATE_LIMIT_PER_MINUTE`, `RATE_LIMIT_PER_DAY`, `MAX_QUERY_LENGTH`, `DEMO_MODE`). Suggested demo questions, with their measured retrieval ranks, are in [docs/DEMO_QUESTIONS.md](docs/DEMO_QUESTIONS.md).

## CI/CD

GitHub Actions runs two jobs:

1. **Tests**
   - Python 3.12
   - PostgreSQL + pgvector service
   - Redis service
   - project installation
   - Alembic migrations
   - non-integration pytest suite

2. **Docker build**
   - builds the application image (CPU-only PyTorch) after the tests pass

This provides a basic quality gate before changes reach the main branch.

## Current scope

The current implementation covers the production-oriented RAG path end to end:

- structure-aware PDF/DOCX ingestion with versioned chunking and embeddings,
- dense, sparse, hybrid and reranked retrieval, selectable by configuration,
- citation-grounded generation with Gemini, OpenAI or Ollama,
- retrieval ablation and end-to-end answer evaluation,
- Redis response caching and rate limiting,
- multi-tenant workspaces with JWT authentication,
- a React frontend with citations and diagnostics,
- structured logging and Prometheus metrics,
- Docker, migrations, CI and a documented Railway deployment.

## Roadmap

- company/fiscal-year metadata filtering at query time (the main retrieval gap above),
- published end-to-end answer accuracy results,
- asynchronous ingestion workers with Celery,
- incremental document update/deletion workflows,
- query expansion,
- OpenTelemetry tracing,
- per-query cost tracking.

## Why this project exists

A RAG demo can be built by connecting an embedding model to a vector database and an LLM. That is not the problem busiRAG is trying to solve.

The goal here is to build the **engineering system around RAG**: reproducible ingestion, versioned data pipelines, multiple retrieval strategies, reranking, grounded generation, caching, observability, evaluation, testing, migrations, containers, and CI.

That makes the project a practical exploration of what it takes to move an AI application from a prototype toward a maintainable production service.
