# Deploying the BusiRAG demo

Two ways to run a public, read-only demo:

- **[Free deployment](#free-deployment-hugging-face-spaces--neon--upstash)**: Hugging Face Spaces + Neon + Upstash + the Gemini free tier. No credit card; best for a portfolio demo.
- **[Railway](#paid-deployment-railway)**: always-on, more control, usage-based billing.

Both use pre-ingested documents. At query time busiRAG only reads chunk text and embeddings from PostgreSQL and never opens the original files, so **no file or object storage is needed**; the demo answers only from the documents you ingested (the whole 12-report corpus is ~33 MB in PostgreSQL).

## Free deployment (Hugging Face Spaces + Neon + Upstash)

| Piece | Free service |
|---|---|
| API + frontend (one app, one URL) | [Hugging Face Spaces](https://huggingface.co/spaces), Gradio SDK (runs our FastAPI app), free CPU hardware |
| PostgreSQL + pgvector | [Neon](https://neon.tech) free plan |
| Redis (answer cache, rate limits) | [Upstash](https://upstash.com) free plan |
| Answer generation | Gemini API free tier ([Google AI Studio](https://aistudio.google.com) key) |
| Document ingestion | your own machine, once |

Free-tier limits change; check each provider's current limits. The one that matters most is the **Gemini free quota** (when tested for this project, `gemini-2.5-flash` allowed 20 requests per day). The demo is built around it:

- answers are cached in Redis for 30 days, and `scripts/warm_cache.py` pre-answers the demo questions, so the suggested questions never use quota;
- `RATE_LIMIT_PER_DAY` caps **new** (uncached) questions only; cached answers keep working after the cap is reached;
- if Upstash is unavailable or over its limits, queries still work (the cache degrades to a miss and rate limiting fails open).

### 1. Create the accounts and databases

1. **Neon**: create a project and copy the **direct** connection string (host without `-pooler`; the pooled endpoint does not work well with psycopg's prepared statements). It looks like `postgresql://user:pass@ep-xxx.region.aws.neon.tech/neondb?sslmode=require`; busiRAG switches it to the psycopg driver automatically.
2. **Upstash**: create a Redis database and copy its `rediss://default:…@….upstash.io:6379` URL.
3. **Google AI Studio**: create a Gemini API key.
4. **Hugging Face**: create an account.

### 2. Load the documents from your machine

Ingestion (PDF parsing and embeddings) runs locally, using your CPU/GPU, straight into Neon. Place the reports as `data/raw/<company>/<year>/<file>.pdf|docx`, then:

```bash
source ~/.venvs/ai/bin/activate          # or your environment
export DATABASE_URL='postgresql://…neon…?sslmode=require'
export REDIS_URL='rediss://default:…@….upstash.io:6379'
export DEMO_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(12))')"
export RETRIEVAL_MODE=hybrid CACHE_TTL=2592000

alembic upgrade head                     # creates the schema and the vector extension
python scripts/setup_demo.py             # demo user + ingest data/raw
python scripts/warm_cache.py             # pre-answer docs/demo_questions.txt
echo "$DEMO_PASSWORD"                    # needed for the Space variables
```

Exported variables override your local `.env`. `warm_cache.py` must run with the same `LLM_PROVIDER`, `GEMINI_MODEL`, `RETRIEVAL_MODE`, `TOP_K`, `CANDIDATE_K` and `EMBEDDING_MODEL` as the Space, because they are all part of the cache key. It uses one Gemini request per uncached question (10 in the default list) and skips questions already cached, so it is safe to re-run on another day if it hits the quota.

To add documents later, drop them into `data/raw/` and re-run `setup_demo.py` (and `warm_cache.py` for new demo questions). The Space does not need a rebuild.

### 3. Create the Space

Docker Spaces are not available on the free plan, so the Space uses the **Gradio SDK**: Hugging Face installs `requirements.txt` and runs `python app.py`, and [`deploy/huggingface-gradio/app.py`](deploy/huggingface-gradio/app.py) starts the busiRAG API (serving the prebuilt frontend) instead of a Gradio UI.

1. **Build the frontend** on your machine, with the demo login baked in (same terminal as step 2, so `$DEMO_PASSWORD` is set):

   ```bash
   cd frontend
   VITE_API_BASE_URL= VITE_DEMO_MODE=true \
   VITE_DEMO_EMAIL=demo@busirag.app VITE_DEMO_PASSWORD="$DEMO_PASSWORD" \
   npm run build
   cd ..
   ```

   The empty `VITE_API_BASE_URL` makes the page call the API on its own origin.
2. On Hugging Face, **New Space** → SDK **Gradio** → blank template → public. Pick the free CPU hardware, or **ZeroGPU** if CPU basic is not selectable: busiRAG runs its models on CPU either way (`app.py` sets `MODEL_DEVICE=cpu` and registers the placeholder GPU function ZeroGPU expects), and `requirements.txt` pins a ZeroGPU-supported torch version. Keep the `README.md` Hugging Face generates (its header selects the SDK and `app_file: app.py`).
3. Upload to the Space repository root:
   - `deploy/huggingface-gradio/app.py`
   - `deploy/huggingface-gradio/requirements.txt` (installs busiRAG from GitHub; it points at the `portfolio-upgrade` branch, so change `@portfolio-upgrade` to `@main` once merged)
   - the **contents** of `frontend/dist/` into a folder named `dist/` (so the Space has `dist/index.html` and `dist/assets/…`)
4. In **Settings → Variables and secrets**, add the secrets `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET_KEY` and `GEMINI_API_KEY`, and the variables `RATE_LIMIT_PER_MINUTE=5` and `RATE_LIMIT_PER_DAY` (e.g. `8`). `app.py` already sets `DEMO_MODE=true`, `RETRIEVAL_MODE=hybrid`, `CACHE_TTL=2592000` and trusts the proxy's client-IP header.
5. The Space installs the requirements (several minutes: PyTorch CPU wheels) and starts at `https://<user>-<space>.hf.space`. The embedding model downloads on first start.

Migrations are not run by the Space; you already ran `alembic upgrade head` in step 2. Run it again from your machine after pulling changes that add migrations.

If your account can use Docker Spaces, [`deploy/huggingface/`](deploy/huggingface/) is a Docker alternative that clones the repository and builds the frontend itself (set `VITE_DEMO_EMAIL`, `VITE_DEMO_PASSWORD`, `CACHE_TTL`, `FORWARDED_ALLOW_IPS=*` and `GIT_REF` as Space variables).

### 4. Verify

- Open the Space and click **Try the demo**.
- Click a suggested question: the diagnostics panel shows **Cache hit** and an instant answer.
- Ask a new question from [docs/DEMO_QUESTIONS.md](docs/DEMO_QUESTIONS.md): it goes to Gemini and is cached afterwards.

### Free-tier behaviour to expect

- **Cold starts**: free Spaces sleep after a period without visitors and Neon suspends idle compute; the first request after a pause takes noticeably longer while both wake up.
- **Updating code**: push to GitHub, then **Settings → Factory rebuild** on the Space (it reinstalls busiRAG from the branch in `requirements.txt`). Frontend changes need a new `npm run build` and re-uploading `dist/`.
- **Read-only**: uploads, deletes and registration are disabled (`DEMO_MODE`), which is also why no file storage is needed.

## Paid deployment (Railway)

The rest of this guide deploys the FastAPI backend with PostgreSQL + pgvector and Redis on **Railway**, and the React frontend as a static site.

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
| `RATE_LIMIT_PER_DAY` | e.g. `200` (global daily cap on new, uncached questions, i.e. LLM calls; keep it under your LLM quota) |
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
