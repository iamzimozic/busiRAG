"""
Pre-answer the demo questions so the live demo serves them from cache.

!! Calls the configured LLM once per question that is not cached yet.

Run from your machine with the SAME settings as the deployed API
(DATABASE_URL, REDIS_URL, LLM_PROVIDER + key, RETRIEVAL_MODE, TOP_K,
CANDIDATE_K, CACHE_TTL): the cache key includes all of them, so any
difference means the live demo will not find these answers.

    DATABASE_URL='postgresql://…neon…' \
    REDIS_URL='rediss://…upstash…' \
    RETRIEVAL_MODE=hybrid CACHE_TTL=2592000 \
    python scripts/warm_cache.py

Questions come from docs/demo_questions.txt (one per line, # comments).
"""

import argparse
import os
import time
from pathlib import Path

from sqlalchemy import select

from busirag.cache import RedisCache
from busirag.config import Settings
from busirag.db.models import User
from busirag.db.session import SessionLocal
from busirag.rag.factory import build_rag_service


def load_questions(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=Path("docs/demo_questions.txt"),
    )
    parser.add_argument(
        "--email",
        default=os.getenv("DEMO_EMAIL", "demo@busirag.app"),
        help="Demo user whose workspace is queried.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=5.0,
        help="Seconds between LLM calls (provider rate limits).",
    )

    args = parser.parse_args()

    settings = Settings()
    questions = load_questions(args.questions)

    with SessionLocal() as session:
        user = session.scalar(
            select(User).where(User.email == args.email)
        )

    if user is None:
        raise SystemExit(
            f"Demo user {args.email} not found; run scripts/setup_demo.py first."
        )

    cache = RedisCache(settings.redis_url)

    # No generation budget: warming is an explicit operator action.
    service = build_rag_service(settings=settings, cache=cache)

    print(
        f"Warming {len(questions)} questions for {args.email} "
        f"(tenant {user.tenant_id}), retrieval={service.retrieval_mode}, "
        f"llm={service.generation_model}, ttl={settings.cache_ttl}s"
    )

    answered = 0

    with SessionLocal() as session:
        for question in questions:
            key = service.cache_key(question, user.tenant_id)

            if cache.get(key) is not None:
                print(f"CACHED  | {question}")
                continue

            if answered:
                time.sleep(args.sleep)

            try:
                result = service.query(
                    session=session,
                    query=question,
                    tenant_id=user.tenant_id,
                )
            except Exception as exc:
                print(f"ERROR   | {question} | {type(exc).__name__}: {exc}")
                continue

            answered += 1
            citations = ", ".join(s.citation_id for s in result.sources)
            print(f"WARMED  | {question}")
            print(f"          {result.answer[:160]} [{citations}]")

    print(f"\nDone: {answered} new answers cached.")


if __name__ == "__main__":
    main()
