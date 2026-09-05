from dataclasses import dataclass

from sqlalchemy.orm import Session

from busirag.embeddings import EmbeddingProvider
from busirag.reranking import LocalReranker
from busirag.retrieval.hybrid import retrieve_hybrid_chunks


@dataclass
class RerankedRetrievalResult:
    chunk_id: int
    document_id: int
    text: str
    company: str
    year: int
    page_number: int | None
    section: str | None
    element_type: str
    score: float


def retrieve_reranked_chunks(
    session: Session,
    query: str,
    embedding_provider: EmbeddingProvider,
    reranker: LocalReranker,
    top_k: int = 5,
    candidate_k: int = 20,
    chunking_version: str | None = None,
    embedding_model: str | None = None,
) -> list[RerankedRetrievalResult]:

    if not query.strip():
        raise ValueError("query must not be empty")

    if top_k <= 0:
        raise ValueError("top_k must be positive")

    if candidate_k <= 0:
        raise ValueError("candidate_k must be positive")

    candidates = retrieve_hybrid_chunks(
        session=session,
        query=query,
        embedding_provider=embedding_provider,
        top_k=candidate_k,
        candidate_k=candidate_k,
        chunking_version=chunking_version,
        embedding_model=embedding_model,
    )

    if not candidates:
        return []

    documents = [candidate.text for candidate in candidates]

    ranked = reranker.rerank(
        query=query,
        documents=documents,
        top_k=top_k,
    )

    return [
        RerankedRetrievalResult(
            chunk_id=candidates[index].chunk_id,
            document_id=candidates[index].document_id,
            text=candidates[index].text,
            company=candidates[index].company,
            year=candidates[index].year,
            page_number=candidates[index].page_number,
            section=candidates[index].section,
            element_type=candidates[index].element_type,
            score=score,
        )
        for index, score in ranked
    ]