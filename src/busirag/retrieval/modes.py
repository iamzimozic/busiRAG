from typing import Literal, get_args

from sqlalchemy.orm import Session

from busirag.embeddings import EmbeddingProvider
from busirag.reranking import Reranker
from busirag.retrieval.hybrid import retrieve_hybrid_chunks
from busirag.retrieval.reranked import retrieve_reranked_chunks
from busirag.retrieval.sparse import retrieve_sparse_chunks
from busirag.retrieval.vector import retrieve_similar_chunks

RetrievalMode = Literal["dense", "sparse", "hybrid", "hybrid_rerank"]

RETRIEVAL_MODES: tuple[str, ...] = get_args(RetrievalMode)

DEFAULT_RETRIEVAL_MODE: RetrievalMode = "hybrid_rerank"


def retrieve_chunks(
    mode: RetrievalMode,
    session: Session,
    query: str,
    tenant_id: int,
    embedding_provider: EmbeddingProvider | None = None,
    reranker: Reranker | None = None,
    top_k: int = 10,
    candidate_k: int = 50,
    chunking_version: str | None = None,
    embedding_model: str | None = None,
) -> list:
    """
    Retrieve chunks using the given retrieval strategy.

    dense:         pgvector cosine similarity only
    sparse:        PostgreSQL full-text search only
    hybrid:        dense + sparse fused with reciprocal rank fusion
    hybrid_rerank: hybrid candidate pool re-scored by a cross-encoder
    """

    if mode == "dense":
        return retrieve_similar_chunks(
            session=session,
            query=query,
            embedding_provider=embedding_provider,
            tenant_id=tenant_id,
            top_k=top_k,
            chunking_version=chunking_version,
            embedding_model=embedding_model,
        )

    if mode == "sparse":
        return retrieve_sparse_chunks(
            session=session,
            query=query,
            tenant_id=tenant_id,
            top_k=top_k,
            chunking_version=chunking_version,
            embedding_model=embedding_model,
        )

    if mode == "hybrid":
        return retrieve_hybrid_chunks(
            session=session,
            query=query,
            embedding_provider=embedding_provider,
            tenant_id=tenant_id,
            top_k=top_k,
            candidate_k=candidate_k,
            chunking_version=chunking_version,
            embedding_model=embedding_model,
        )

    if mode == "hybrid_rerank":
        if reranker is None:
            raise ValueError(
                "hybrid_rerank retrieval requires a reranker"
            )

        return retrieve_reranked_chunks(
            session=session,
            query=query,
            embedding_provider=embedding_provider,
            reranker=reranker,
            tenant_id=tenant_id,
            top_k=top_k,
            candidate_k=candidate_k,
            chunking_version=chunking_version,
            embedding_model=embedding_model,
        )

    raise ValueError(
        f"Unknown retrieval mode {mode!r}. "
        f"Expected one of: {', '.join(RETRIEVAL_MODES)}"
    )
