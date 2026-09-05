from dataclasses import dataclass

from sqlalchemy.orm import Session

from busirag.embeddings import EmbeddingProvider
from busirag.retrieval.sparse import retrieve_sparse_chunks
from busirag.retrieval.vector import retrieve_similar_chunks


@dataclass
class HybridRetrievalResult:
    chunk_id: int
    document_id: int
    text: str
    company: str
    year: int
    page_number: int | None
    section: str | None
    element_type: str
    score: float


def retrieve_hybrid_chunks(
    session: Session,
    query: str,
    embedding_provider: EmbeddingProvider,
    top_k: int = 5,
    candidate_k: int = 10,
    chunking_version: str | None = None,
    embedding_model: str | None = None,
    rrf_k: int = 60,
) -> list[HybridRetrievalResult]:

    if not query.strip():
        raise ValueError("Query cannot be empty.")

    if top_k <= 0:
        raise ValueError("top_k must be greater than zero.")

    if candidate_k <= 0:
        raise ValueError("candidate_k must be greater than zero.")

    dense_results = retrieve_similar_chunks(
        session=session,
        query=query,
        embedding_provider=embedding_provider,
        top_k=candidate_k,
        chunking_version=chunking_version,
        embedding_model=embedding_model,
    )

    sparse_results = retrieve_sparse_chunks(
        session=session,
        query=query,
        top_k=candidate_k,
        chunking_version=chunking_version,
        embedding_model=embedding_model,
    )

    candidates = {}

    for rank, result in enumerate(dense_results, start=1):
        candidates.setdefault(
            result.chunk_id,
            {
                "result": result,
                "score": 0.0,
            },
        )

        candidates[result.chunk_id]["score"] += (
            1.0 / (rrf_k + rank)
        )

    for rank, result in enumerate(sparse_results, start=1):
        candidates.setdefault(
            result.chunk_id,
            {
                "result": result,
                "score": 0.0,
            },
        )

        candidates[result.chunk_id]["score"] += (
            1.0 / (rrf_k + rank)
        )

    ranked = sorted(
        candidates.values(),
        key=lambda item: item["score"],
        reverse=True,
    )

    results = []

    for item in ranked[:top_k]:
        result = item["result"]

        results.append(
            HybridRetrievalResult(
                chunk_id=result.chunk_id,
                document_id=result.document_id,
                text=result.text,
                company=result.company,
                year=result.year,
                page_number=result.page_number,
                section=result.section,
                element_type=result.element_type,
                score=item["score"],
            )
        )

    return results