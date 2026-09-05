from pathlib import Path

from busirag.embeddings import LocalEmbeddingProvider
from busirag.evaluation import (
    evaluate_case,
    load_cases,
    mean_reciprocal_rank,
    recall_at_k,
)


def main():

    evaluation_path = Path(
        "data/evaluation/retrieval.json"
    )

    cases = load_cases(evaluation_path)

    provider = LocalEmbeddingProvider()

    results = []

    for case in cases:

        result = evaluate_case(
            case=case,
            embedding_provider=provider,
            top_k=10,
        )

        results.append(result)

        rank = result.relevant_rank

        if rank is None:
            status = "MISS"
        else:
            status = f"HIT @ {rank}"

        print(
            f"{status:10} | "
            f"{case.id}"
        )

    print("\n" + "=" * 80)
    print("RETRIEVAL EVALUATION")
    print("=" * 80)

    print(
        f"Cases:      {len(results)}"
    )

    print(
        f"Recall@1:   {recall_at_k(results, 1):.3f}"
    )

    print(
        f"Recall@3:   {recall_at_k(results, 3):.3f}"
    )

    print(
        f"Recall@5:   {recall_at_k(results, 5):.3f}"
    )

    print(
        f"Recall@10:  {recall_at_k(results, 10):.3f}"
    )

    print(
        f"MRR:        {mean_reciprocal_rank(results):.3f}"
    )


if __name__ == "__main__":
    main()