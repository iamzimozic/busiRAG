from pathlib import Path

from busirag.db.session import SessionLocal
from busirag.embeddings import LocalEmbeddingProvider
from busirag.evaluation import is_relevant, load_cases
from busirag.retrieval.hybrid import retrieve_hybrid_chunks
from busirag.retrieval.sparse import retrieve_sparse_chunks
from busirag.retrieval.vector import retrieve_similar_chunks
from busirag.reranking import LocalReranker
from busirag.versioning import CHUNKING_VERSION, EMBEDDING_MODEL


CHUNKING_VERSION = CHUNKING_VERSION
EMBEDDING_MODEL = EMBEDDING_MODEL

CANDIDATE_K = 50


def print_results(title, results, case):
    print()
    print(title)

    for i, result in enumerate(results, start=1):
        relevant = (
            result.company == case.company
            and result.year == case.year
            and is_relevant(
                result.text,
                case.expected_terms,
            )
        )

        marker = " <-- CORRECT" if relevant else ""

        score = (
            result.score
            if hasattr(result, "score")
            else result.similarity
        )

        print(
            f"  #{i:<2} "
            f"chunk={result.chunk_id:<4} "
            f"score={score:.4f}"
            f"{marker}"
        )


def main():
    cases = load_cases(Path("data/evaluation/retrieval.json"))

    provider = LocalEmbeddingProvider()

    reranker = LocalReranker()

    with SessionLocal() as session:

        for case in cases:

            print()
            print("#" * 80)
            print(case.query)
            print("#" * 80)

            dense_results = retrieve_similar_chunks(
                session=session,
                query=case.query,
                embedding_provider=provider,
                top_k=CANDIDATE_K,
                chunking_version=CHUNKING_VERSION,
                embedding_model=EMBEDDING_MODEL,
            )

            sparse_results = retrieve_sparse_chunks(
                session=session,
                query=case.query,
                top_k=CANDIDATE_K,
                chunking_version=CHUNKING_VERSION,
                embedding_model=EMBEDDING_MODEL,
            )

            hybrid_results = retrieve_hybrid_chunks(
                session=session,
                query=case.query,
                embedding_provider=provider,
                top_k=CANDIDATE_K,
                candidate_k=CANDIDATE_K,
                chunking_version=CHUNKING_VERSION,
                embedding_model=EMBEDDING_MODEL,
            )

            reranked_indices = reranker.rerank(
                case.query,
                [result.text for result in hybrid_results],
                top_k=10,
            )

            reranked_results = [
                hybrid_results[index]
                for index, _ in reranked_indices
            ]

            print_results(
                "DENSE",
                dense_results,
                case,
            )

            print_results(
                "SPARSE",
                sparse_results,
                case,
            )

            print_results(
                "HYBRID",
                hybrid_results,
                case,
            )

            print_results(
                "RERANKED",
                reranked_results,
                case,
            )


if __name__ == "__main__":
    main()