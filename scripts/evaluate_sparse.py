from busirag.db.session import SessionLocal
from busirag.evaluation import load_cases, is_relevant
from busirag.retrieval.sparse import retrieve_sparse_chunks
from pathlib import Path
from busirag.versioning import CHUNKING_VERSION, EMBEDDING_MODEL


def reciprocal_rank(results, case):
    for rank, result in enumerate(results, start=1):
        if (
            result.company == case.company
            and result.year == case.year
            and is_relevant(result.text, case.expected_terms)
        ):
            return 1.0 / rank
    return 0.0


def main():
    cases = load_cases(
        Path("data/evaluation/retrieval.json")
    )

    ranks = []

    with SessionLocal() as session:
        for case in cases:
            results = retrieve_sparse_chunks(
                session,
                case.query,
                top_k=10,
                chunking_version=CHUNKING_VERSION,
                embedding_model=EMBEDDING_MODEL,
            )

            rank = None

            for i, result in enumerate(results, start=1):
                if (
                    result.company == case.company
                    and result.year == case.year
                    and is_relevant(result.text, case.expected_terms)
                ):
                    rank = i
                    break

            ranks.append(rank)

            if rank is None:
                print(f"MISS       | {case.id}")
            else:
                print(f"HIT @ {rank:<5} | {case.id}")

    print("\n" + "=" * 80)
    print("SPARSE RETRIEVAL EVALUATION")
    print("=" * 80)

    for k in [1, 3, 5, 10]:
        hits = sum(
            rank is not None and rank <= k
            for rank in ranks
        )
        print(f"Recall@{k:<2}:", f"{hits / len(cases):.3f}")

    mrr = sum(
        1 / rank
        for rank in ranks
        if rank is not None
    ) / len(ranks)

    print(f"MRR:       {mrr:.3f}")


if __name__ == "__main__":
    main()