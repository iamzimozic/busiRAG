from dataclasses import dataclass

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from busirag.db.models import Chunk, Document


@dataclass
class SparseRetrievalResult:
    chunk_id: int
    document_id: int
    text: str
    company: str
    year: int
    page_number: int | None
    section: str | None
    element_type: str
    score: float


def retrieve_sparse_chunks(
    session: Session,
    query: str,
    top_k: int = 5,
    chunking_version: str | None = None,
    embedding_model: str | None = None,
) -> list[SparseRetrievalResult]:
    if not query.strip():
        raise ValueError("Query cannot be empty.")

    if top_k <= 0:
        raise ValueError("top_k must be greater than zero.")

    search_query = func.plainto_tsquery(
        "english",
        query,
    )

    score = func.ts_rank_cd(
        Chunk.search_vector,
        search_query,
    )

    filters = [
        Chunk.search_vector.op("@@")(search_query)
    ]

    if chunking_version is not None:
        filters.append(
            Chunk.chunking_version == chunking_version
        )

    if embedding_model is not None:
        filters.append(
            Chunk.embedding_model == embedding_model
        )

    statement = (
        select(
            Chunk,
            Document,
            score.label("score"),
        )
        .join(
            Document,
            Chunk.document_id == Document.id,
        )
        .where(*filters)
        .order_by(score.desc())
        .limit(top_k)
    )

    rows = session.execute(statement).all()

    results = []

    for chunk, document, score_value in rows:
        results.append(
            SparseRetrievalResult(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                text=chunk.text,
                company=document.company,
                year=document.year,
                page_number=chunk.page_number,
                section=chunk.section,
                element_type=chunk.element_type,
                score=float(score_value),
            )
        )

    return results