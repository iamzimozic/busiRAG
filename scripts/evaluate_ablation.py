"""
Retrieval ablation: run the same benchmark through every retrieval mode.

    python scripts/evaluate_ablation.py
    python scripts/evaluate_ablation.py --modes dense hybrid
    CUDA_VISIBLE_DEVICES="" python scripts/evaluate_ablation.py \
        --output-dir data/evaluation/results/cpu

Writes <output-dir>/retrieval_ablation.json and retrieval_ablation.md.
"""

import argparse
import json
import subprocess
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import torch
from sqlalchemy import func, select

from busirag.db.models import Chunk, Document
from busirag.db.session import SessionLocal
from busirag.embeddings import LocalEmbeddingProvider
from busirag.evaluation import (
    evaluate_results,
    load_cases,
    matches,
    render_markdown,
    summarize,
    summarize_by_category,
)
from busirag.reranking import LocalReranker
from busirag.retrieval.modes import RETRIEVAL_MODES, retrieve_chunks
from busirag.versioning import CHUNKING_VERSION, EMBEDDING_MODEL


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("data/evaluation/retrieval.json"),
    )
    parser.add_argument("--tenant-id", type=int, default=1)
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=RETRIEVAL_MODES,
        default=list(RETRIEVAL_MODES),
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--candidate-k", type=int, default=50)
    parser.add_argument(
        "--reranker-model",
        default="BAAI/bge-reranker-v2-m3",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=3,
        help="Untimed queries per mode before measuring latency.",
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


def check_labels(session, cases, tenant_id: int) -> list[str]:
    """Return relevance specs that match no chunk in the tenant's index."""

    rows = session.execute(
        select(
            Chunk.id,
            Chunk.text,
            Document.company,
            Document.year,
        )
        .join(Document, Chunk.document_id == Document.id)
        .where(
            Document.tenant_id == tenant_id,
            Chunk.chunking_version == CHUNKING_VERSION,
            Chunk.embedding_model == EMBEDDING_MODEL,
        )
    ).all()

    chunks = [
        SimpleNamespace(
            chunk_id=row.id,
            text=row.text,
            company=row.company,
            year=row.year,
        )
        for row in rows
    ]

    problems = []

    for case in cases:
        for relevant in case.relevant_chunks:
            if not any(matches(chunk, relevant) for chunk in chunks):
                problems.append(
                    f"{case.id}: no chunk matches "
                    f"{relevant.company}/{relevant.year} "
                    f"contains={list(relevant.contains)}"
                )

    return problems


def main():
    args = parse_args()

    cases = load_cases(args.cases)

    embedding_provider = LocalEmbeddingProvider(
        model_name=EMBEDDING_MODEL,
    )

    reranker = (
        LocalReranker(model_name=args.reranker_model)
        if "hybrid_rerank" in args.modes
        else None
    )

    report = {
        "config": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "git_commit": git_commit(),
            "cases_file": str(args.cases),
            "cases": len(cases),
            "tenant_id": args.tenant_id,
            "top_k": args.top_k,
            "candidate_k": args.candidate_k,
            "chunking_version": CHUNKING_VERSION,
            "embedding_model": EMBEDDING_MODEL,
            "reranker_model": args.reranker_model,
            "device": (
                torch.cuda.get_device_name(0)
                if torch.cuda.is_available()
                else "cpu"
            ),
            "warmup_queries": args.warmup,
        },
        "modes": {},
    }

    with SessionLocal() as session:
        report["config"]["documents"] = session.scalar(
            select(func.count(Document.id)).where(
                Document.tenant_id == args.tenant_id
            )
        )

        problems = check_labels(session, cases, args.tenant_id)

        for problem in problems:
            print(f"WARNING {problem}")

        report["config"]["unmatched_labels"] = problems

        for mode in args.modes:

            def run(query):
                return retrieve_chunks(
                    mode=mode,
                    session=session,
                    query=query,
                    tenant_id=args.tenant_id,
                    embedding_provider=embedding_provider,
                    reranker=reranker,
                    top_k=args.top_k,
                    candidate_k=args.candidate_k,
                    chunking_version=CHUNKING_VERSION,
                    embedding_model=EMBEDDING_MODEL,
                )

            for case in cases[: args.warmup]:
                run(case.query)

            case_results = []

            print()
            print("=" * 80)
            print(mode)
            print("=" * 80)

            for case in cases:
                start = time.perf_counter()
                results = run(case.query)
                latency_ms = (time.perf_counter() - start) * 1000

                case_result = evaluate_results(
                    results,
                    case,
                    latency_ms=latency_ms,
                )
                case_results.append(case_result)

                rank = case_result.relevant_rank
                status = "MISS" if rank is None else f"HIT @ {rank}"

                print(
                    f"{status:10} | {latency_ms:7.1f} ms | {case.id}"
                )

            summary = summarize(case_results)

            print(
                f"Recall@5 {summary['recall_at_5']:.3f} | "
                f"Recall@10 {summary['recall_at_10']:.3f} | "
                f"MRR {summary['mrr']:.3f} | "
                f"p50 {summary['latency_p50_ms']:.0f} ms | "
                f"p95 {summary['latency_p95_ms']:.0f} ms"
            )

            report["modes"][mode] = {
                "summary": summary,
                "by_category": summarize_by_category(case_results),
                "cases": [asdict(result) for result in case_results],
            }

    args.output_dir.mkdir(parents=True, exist_ok=True)

    json_path = args.output_dir / "retrieval_ablation.json"
    markdown_path = args.output_dir / "retrieval_ablation.md"

    json_path.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    markdown = render_markdown(report)
    markdown_path.write_text(markdown, encoding="utf-8")

    print()
    print(markdown)
    print(f"Wrote {json_path} and {markdown_path}")


if __name__ == "__main__":
    main()
