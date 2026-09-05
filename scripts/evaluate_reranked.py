from pathlib import Path

from busirag.db.session import SessionLocal
from busirag.embeddings import LocalEmbeddingProvider
from busirag.evaluation import first_relevant_rank, load_cases
from busirag.reranking import LocalReranker
from busirag.retrieval.hybrid import retrieve_hybrid_chunks
from busirag.retrieval.reranked import retrieve_reranked_chunks
from busirag.versioning import CHUNKING_VERSION, EMBEDDING_MODEL


CANDIDATE_K = 50
TOP_K = 10


def calculate_metrics(ranks):
    total = len(ranks)

    if total == 0:
        return {
            "recall_at_1": 0.0,
            "recall_at_3": 0.0,
            "recall_at_5": 0.0,
            "recall_at_10": 0.0,
            "mrr": 0.0,
        }

    recall_at_1 = sum(
        rank is not None and rank <= 1
        for rank in ranks
    ) / total

    recall_at_3 = sum(
        rank is not None and rank <= 3
        for rank in ranks
    ) / total

    recall_at_5 = sum(
        rank is not None and rank <= 5
        for rank in ranks
    ) / total

    recall_at_10 = sum(
        rank is not None and rank <= 10
        for rank in ranks
    ) / total

    mrr = sum(
        1 / rank if rank is not None else 0
        for rank in ranks
    ) / total

    return {
        "recall_at_1": recall_at_1,
        "recall_at_3": recall_at_3,
        "recall_at_5": recall_at_5,
        "recall_at_10": recall_at_10,
        "mrr": mrr,
    }


def print_metrics(title, metrics):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)
    print(f"Recall@1 :  {metrics['recall_at_1']:.3f}")
    print(f"Recall@3 :  {metrics['recall_at_3']:.3f}")
    print(f"Recall@5 :  {metrics['recall_at_5']:.3f}")
    print(f"Recall@10:  {metrics['recall_at_10']:.3f}")
    print(f"MRR:        {metrics['mrr']:.3f}")


def main():
    cases = load_cases(
        Path("data/evaluation/retrieval.json")
    )

    provider = LocalEmbeddingProvider()

    reranker = LocalReranker(
        model_name="BAAI/bge-reranker-v2-m3"
    )

    candidate_ranks = []
    reranked_ranks = []

    with SessionLocal() as session:
        for case in cases:

            # ---------------------------------------------------------
            # 1. Retrieve the hybrid candidate pool
            # ---------------------------------------------------------
            candidates = retrieve_hybrid_chunks(
                session=session,
                query=case.query,
                embedding_provider=provider,
                top_k=CANDIDATE_K,
                candidate_k=CANDIDATE_K,
                chunking_version=CHUNKING_VERSION,
                embedding_model=EMBEDDING_MODEL,
            )

            # ---------------------------------------------------------
            # 2. Find the first gold chunk in the candidate pool
            # ---------------------------------------------------------
            candidate_rank = first_relevant_rank(
                candidates,
                case,
            )

            candidate_ranks.append(candidate_rank)

            # ---------------------------------------------------------
            # 3. Rerank the same candidate pool
            # ---------------------------------------------------------
            reranked = retrieve_reranked_chunks(
                session=session,
                query=case.query,
                embedding_provider=provider,
                reranker=reranker,
                top_k=TOP_K,
                candidate_k=CANDIDATE_K,
                chunking_version=CHUNKING_VERSION,
                embedding_model=EMBEDDING_MODEL,
            )

            # ---------------------------------------------------------
            # 4. Find the first gold chunk after reranking
            # ---------------------------------------------------------
            reranked_rank = first_relevant_rank(
                reranked,
                case,
            )

            reranked_ranks.append(reranked_rank)

            # ---------------------------------------------------------
            # 5. Print per-query diagnostics
            # ---------------------------------------------------------
            print()
            print(f"QUERY: {case.query}")

            if candidate_rank is None:
                print("Candidate pool: NOT FOUND")
            else:
                print(
                    f"Candidate pool: FOUND @ {candidate_rank}"
                )

            if reranked_rank is None:
                print("After reranking: NOT FOUND")
            else:
                print(
                    f"After reranking: FOUND @ {reranked_rank}"
                )

            print("-" * 80)

    # -------------------------------------------------------------
    # 6. Calculate metrics for both stages
    # -------------------------------------------------------------
    candidate_metrics = calculate_metrics(
        candidate_ranks
    )

    reranked_metrics = calculate_metrics(
        reranked_ranks
    )

    # -------------------------------------------------------------
    # 7. Print final comparison
    # -------------------------------------------------------------
    print_metrics(
        "HYBRID CANDIDATE RETRIEVAL",
        candidate_metrics,
    )

    print_metrics(
        "RERANKED RETRIEVAL",
        reranked_metrics,
    )


if __name__ == "__main__":
    main()