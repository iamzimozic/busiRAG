"""
Hugging Face Space entry point (Gradio SDK, free CPU hardware).

Docker Spaces are not available on the free plan, but Gradio-SDK
Spaces simply run `python app.py`. This starts the busiRAG FastAPI app
(API + prebuilt frontend in ./dist) on the Space port instead of a
Gradio UI.

Space secrets: DATABASE_URL, REDIS_URL, GEMINI_API_KEY, JWT_SECRET_KEY.
Migrations are run from your machine (alembic upgrade head) beforehand.
"""

import os
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Must be set before busirag.api.main is imported (read at import time).
os.environ.setdefault("FRONTEND_DIST", str(HERE / "dist"))
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("RETRIEVAL_MODE", "hybrid")
os.environ.setdefault("CACHE_TTL", "2592000")

import uvicorn  # noqa: E402

from busirag.api.main import app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "7860")),
        # Behind the Spaces proxy: use X-Forwarded-For for client IPs
        # so per-client rate limits work.
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
