# Deploying the BusiRAG demo

This guide deploys a public, read-only demo: the FastAPI backend with PostgreSQL + pgvector and Redis on **Railway**, and the React frontend as a static site.

## Choosing a host

The API loads local models (embeddings, optionally a reranker), so memory is the deciding constraint, not CPU:

| Configuration | Measured memory (CPU) |
|---|---:|
| Embeddings only (`RETRIEVAL_MODE=hybrid`) | ~0.93 GB |
| + `cross-encoder/ms-marco-MiniLM-L-6-v2` | ~1.0 GB |
| + `BAAI/bge-reranker-base` | ~1.7 GB |
| + `BAAI/bge-reranker-v2-m3` (default) | ~2.6 GB |

Resident memory of a Python process after loading each model, measured with the CUDA build of PyTorch with the GPU hidden; the CPU-only image built by the `Dockerfile` should use somewhat less. Allow headroom for requests.

| Option | Fit |
|---|---|
| **Railway** (recommended) | Deploys the `Dockerfile` from GitHub, has one-click PostgreSQL with pgvector and Redis in the same project, and instance memory is not capped at 512 MB. `railway.json` configures migrations and health checks. |
| Render | Works, but the smallest instance sizes do not have enough memory for the models; you need a larger instance plus a Postgres plan with pgvector. |
| Fly.io | Works with a larger machine size; Postgres is either self-managed on Fly or a separate managed product, so there is more to operate. |
| Small VM (Hetzner, DigitalOcean, …) | Cheapest per GB of RAM and runs the existing `docker-compose.yml`, but you own OS updates, TLS, backups and monitoring. |

Pricing changes often; check each provider's current plans before choosing.

## Reranker: latency vs. quality

The cross-encoder reranker is the most expensive step. Measured on the 40-question benchmark (`data/evaluation/retrieval.json`), top-10 retrieval with 50 candidates:

| Configuration | Hardware | Recall@5 | Recall@10 | MRR | p50 latency | p95 latency |
|---|---|---:|---:|---:|---:|---:|
| Hybrid (no reranker) | RTX 3060 laptop GPU | 0.500 | 0.562 | 0.295 | 43 ms | 53 ms |
| Hybrid + `bge-reranker-v2-m3` | RTX 3060 laptop GPU | 0.637 | 0.675 | 0.483 | 3736 ms | 5734 ms |
| Hybrid (no reranker) | CPU, 2 torch threads | 0.500 | 0.562 | 0.295 | 47 ms | 55 ms |
| Hybrid + `ms-marco-MiniLM-L-6-v2` | CPU, 2 torch threads | 0.412 | 0.588 | 0.326 | 5300 ms | 5748 ms |

Sources: `data/evaluation/results/retrieval_ablation.json` and `data/evaluation/results/cpu-minilm/retrieval_ablation.json`. Latency is retrieval only; LLM generation comes on top.

What this means for a CPU host:

- **Use `RETRIEVAL_MODE=hybrid` for the public demo.** Retrieval stays under ~60 ms, the reranker is not loaded (saving ~0.07–1.6 GB), and quality equals hybrid on a GPU.
- **The small MiniLM reranker is not worth it here**: on CPU it adds ~5 s per query and lowers Recall@5 (0.412 vs 0.500) on this financial corpus.
- **`bge-reranker-v2-m3` gives the best quality** (+0.137 Recall@5, +0.188 MRR over hybrid) but already takes ~3.7 s per query on a GPU. It was not measured on CPU, where it will be far slower than MiniLM's 5.3 s; use it only with a GPU host or where latency does not matter.

To measure other configurations yourself:

```bash
# Hide the GPU to measure CPU latency
CUDA_VISIBLE_DEVICES="" python scripts/evaluate_ablation.py \
  --modes hybrid hybrid_rerank \
  --reranker-model BAAI/bge-reranker-base \
  --output-dir data/evaluation/results/cpu-bge-base

# Fewer rerank candidates = proportionally less reranking time
python scripts/evaluate_ablation.py --modes hybrid_rerank --candidate-k 20 \
  --output-dir data/evaluation/results/rerank-k20
```

## 1. Prepare

- Push the repository to GitHub.
- Get an API key for your generation provider (`GEMINI_API_KEY` or `OPENAI_API_KEY`). The Gemini free tier allows only a small number of requests per day, so set `RATE_LIMIT_PER_DAY` below it or use a paid key.
- Generate secrets locally:

  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(48))"   # JWT_SECRET_KEY
  python -c "import secrets; print(secrets.token_urlsafe(16))"   # DEMO_PASSWORD
  ```

## 2. Create the Railway project

1. Create a new project on Railway.
2. Add a **PostgreSQL with pgvector** database (Railway's *pgvector* template).
3. Add a **Redis** database.
4. Add a service from your **GitHub repository**. Railway detects `railway.json`, builds the `Dockerfile` (CPU-only PyTorch, embedding model baked in) and runs `alembic upgrade head` before every deploy. The first migration creates the `vector` extension.

## 3. Configure the API service

Set these variables on the API service. Railway's reference syntax (`${{Service.VARIABLE}}`) links the databases; replace the service names with yours.

| Variable | Value |
|---|---|
| `DATABASE_URL` | `${{pgvector.DATABASE_URL}}` (plain `postgresql://` URLs are converted to the psycopg driver automatically) |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` |
| `JWT_SECRET_KEY` | the generated secret |
| `LLM_PROVIDER` | `gemini` (or `openai`) |
| `GEMINI_API_KEY` / `OPENAI_API_KEY` | your key |
| `RETRIEVAL_MODE` | `hybrid` (see the tradeoff above) |
| `DEMO_MODE` | `true` (disables registration and document upload/delete) |
| `RATE_LIMIT_PER_MINUTE` | `5` (per client IP) |
| `RATE_LIMIT_PER_DAY` | e.g. `200` (global cap on queries; keep it under your LLM quota) |
| `MAX_QUERY_LENGTH` | `500` |
| `CORS_ORIGINS` | your frontend URL, e.g. `https://busirag-demo.pages.dev` (comma-separated for several) |
| `FORWARDED_ALLOW_IPS` | `*`, so uvicorn trusts Railway's proxy headers and rate limits see real client IPs |

Then, under the service's networking settings, generate a public domain and open `https://<api-domain>/health`; it should return `{"status": "ok"}`.

## 4. Load the demo corpus

Place the filings as `data/raw/<company>/<year>/<file>.pdf|docx`. Ingestion (PDF parsing and embeddings) is heavy, so run it **from your machine** against the Railway database rather than on the small API instance:

1. Enable public networking (TCP proxy) on the pgvector service and copy its public connection URL.
2. Run:

   ```bash
   source ~/.venvs/ai/bin/activate   # or your environment
   DATABASE_URL='postgresql://…public-railway-url…' \
   DEMO_PASSWORD='the generated password' \
   python scripts/setup_demo.py
   ```

   This creates the demo user (`demo@busirag.app` by default; change with `--email`) and a demo workspace, then ingests every document into it. Re-running skips files that are already ingested.
3. Disable public networking on the database again if you do not need it.

The local `.env` must use the same `EMBEDDING_MODEL` as the server (the default `BAAI/bge-small-en-v1.5`).

## 5. Deploy the frontend

Any static host works (Cloudflare Pages, Netlify, Vercel, or a Railway static service):

| Setting | Value |
|---|---|
| Root directory | `frontend` |
| Build command | `npm ci && npm run build` |
| Output directory | `dist` |

Build-time variables (see `frontend/.env.example`):

| Variable | Value |
|---|---|
| `VITE_API_BASE_URL` | `https://<api-domain>` |
| `VITE_DEMO_EMAIL` | the demo email |
| `VITE_DEMO_PASSWORD` | the demo password; this shows a **Try the demo** button. It is visible in the browser bundle, which is why the API must run with `DEMO_MODE=true` |
| `VITE_DEMO_MODE` | `true` (hides upload/delete and registration) |
| `VITE_MAX_QUERY_LENGTH` | same as `MAX_QUERY_LENGTH` |

Finally, make sure `CORS_ORIGINS` on the API matches the frontend's URL exactly (scheme and host, no trailing slash).

## 6. Verify

- Sign in with **Try the demo** and ask the questions in [docs/DEMO_QUESTIONS.md](docs/DEMO_QUESTIONS.md).
- Expand a citation and the diagnostics panel; ask the same question twice to see a cache hit.
- Send more than `RATE_LIMIT_PER_MINUTE` questions in a minute: the UI shows the rate-limit message (HTTP 429 with `Retry-After`).
- `https://<api-domain>/metrics` exposes Prometheus metrics.

## Alternative: a single VM with Docker Compose

On a VM with at least 2 GB of RAM (4 GB if you keep the default reranker):

```bash
git clone <repo> && cd busirag
cp .env.example .env   # or create .env as in the README, plus the demo variables above
docker compose up -d --build postgres redis migrate api
```

Put a reverse proxy with TLS (e.g. Caddy) in front of port 8000, serve `frontend/dist` as static files, and set up backups for the `postgres_data` volume. `docker-compose.yml` publishes Postgres and Redis ports for local development; remove those `ports:` entries on a public server.

## Operational notes

- **Uploads are stored on the container filesystem** (`data/uploads/`) and are lost on redeploy. That is fine for the read-only demo; a production deployment that accepts uploads needs a volume or object storage.
- **Cache**: answers are cached in Redis for `CACHE_TTL` seconds (default 1 hour), keyed by query, workspace, retrieval settings and LLM model, so repeated demo questions cost no LLM calls.
- **Rate limiting fails open**: if Redis is unreachable, requests are allowed and an error is logged.
- **Reranker downloads**: only the embedding model is baked into the image. If you enable `hybrid_rerank`, the reranker is downloaded on first start; mount a volume at `/app/.cache/huggingface` to keep it across deploys.
