"""
End-to-end answer evaluation against the REAL generation provider.

!! This script calls the configured LLM provider once per case and sends
!! retrieved document text to it. Hosted providers (Gemini, OpenAI) need an
!! API key in .env and are billed / rate limited. It is not run in CI.

    python scripts/evaluate_answers.py                    # LLM_PROVIDER from .env
    python scripts/evaluate_answers.py --provider ollama  # local model, no API
    python scripts/evaluate_answers.py --cases data/evaluation/answers.json \
        --retrieval-mode hybrid

Writes <output-dir>/answer_eval.json and answer_eval.md.
"""

import argparse
import json
import subprocess
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from busirag.answer_evaluation import (
    AnswerCheck,
    evaluate_answer,
    load_answer_cases,
    render_answer_markdown,
    summarize_answers,
)
from busirag.config import Settings
from busirag.db.session import SessionLocal
from busirag.embeddings import LocalEmbeddingProvider
from busirag.generation.factory import (
    create_llm_provider,
    llm_identity,
    llm_model_name,
)
from busirag.generation.service import GenerationService
from busirag.rag.service import RAGService
from busirag.reranking import LocalReranker
from busirag.retrieval.modes import RETRIEVAL_MODES
from busirag.versioning import CHUNKING_VERSION, EMBEDDING_MODEL


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("data/evaluation/answers.json"),
    )
    parser.add_argument("--tenant-id", type=int, default=1)
    parser.add_argument(
        "--retrieval-mode",
        choices=RETRIEVAL_MODES,
        default=None,
        help="Defaults to RETRIEVAL_MODE from settings.",
    )
    parser.add_argument(
        "--provider",
        choices=["gemini", "openai", "ollama"],
        default=None,
        help="Defaults to LLM_PROVIDER from settings.",
    )
    parser.add_argument(
        "--ids",
        nargs="+",
        help="Only run these case ids (e.g. to stay within a free tier).",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="Seconds to wait between cases (provider rate limits).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/evaluation/results"),
    )

    return parser.parse_args()


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main():
    args = parse_args()
    settings = (
        Settings(llm_provider=args.provider)
        if args.provider
        else Settings()
    )

    retrieval_mode = args.retrieval_mode or settings.retrieval_mode

    cases = load_answer_cases(args.cases)

    if args.ids:
        unknown = set(args.ids) - {case.id for case in cases}

        if unknown:
            raise SystemExit(f"Unknown case ids: {sorted(unknown)}")

        cases = [case for case in cases if case.id in args.ids]

    llm = create_llm_provider(settings)

    # No cache: every case must exercise retrieval and generation.
    rag_service = RAGService(
        embedding_provider=LocalEmbeddingProvider(
            model_name=settings.embedding_model,
        ),
        reranker=(
            LocalReranker(model_name=settings.reranker_model)
            if retrieval_mode == "hybrid_rerank"
            else None
        ),
        generation_service=GenerationService(llm),
        cache=None,
        chunking_version=CHUNKING_VERSION,
        embedding_model=EMBEDDING_MODEL,
        candidate_k=settings.candidate_k,
        top_k=settings.top_k,
        retrieval_mode=retrieval_mode,
        generation_model=llm_identity(settings),
    )

    checks = []

    with SessionLocal() as session:
        for index, case in enumerate(cases):
            if index and args.sleep:
                time.sleep(args.sleep)

            start = time.perf_counter()

            try:
                result = rag_service.query(
                    session=session,
                    query=case.query,
                    tenant_id=args.tenant_id,
                )
            except Exception as exc:
                check = AnswerCheck(
                    case_id=case.id,
                    query=case.query,
                    answerable=case.answerable,
                    answer="",
                    citations=[],
                    refused=False,
                    error=f"{type(exc).__name__}: {exc}",
                )
                checks.append(check)
                print(f"ERROR | {case.id} | {check.error}")
                continue

            latency_ms = (time.perf_counter() - start) * 1000

            check = evaluate_answer(
                case,
                result.answer,
                result.sources,
                latency_ms=latency_ms,
            )
            checks.append(check)

            status = "PASS" if check.passed else "FAIL"

            print(
                f"{status} | {latency_ms:7.0f} ms | {case.id} | "
                f"{', '.join(check.failures)}"
            )
            print(f"       {result.answer[:200]}")

    report = {
        "config": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "git_commit": git_commit(),
            "cases_file": str(args.cases),
            "tenant_id": args.tenant_id,
            "provider": settings.llm_provider,
            "model": llm_model_name(settings),
            "retrieval_mode": retrieval_mode,
            "top_k": settings.top_k,
            "candidate_k": settings.candidate_k,
        },
        "summary": summarize_answers(checks),
        "cases": [asdict(check) for check in checks],
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)

    json_path = args.output_dir / "answer_eval.json"
    markdown_path = args.output_dir / "answer_eval.md"

    json_path.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    markdown = render_answer_markdown(report)
    markdown_path.write_text(markdown, encoding="utf-8")

    print()
    print(markdown)
    print(f"Wrote {json_path} and {markdown_path}")


if __name__ == "__main__":
    main()
