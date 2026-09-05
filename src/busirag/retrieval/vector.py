from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from busirag.db.models import Chunk, Document
from busirag.embeddings import EmbeddingProvider


@dataclass
class RetrievalResult:
    chunk_id: int
    document_id: int
    text: str
    company: str
    year: int
    page_number: int | None
    section: str | None
    element_type: str
    similarity: float


def retrieve_similar_chunks(
    session: Session,
    query: str,
    embedding_provider: EmbeddingProvider,
    top_k: int = 5,
    chunking_version: str | None = None,
    embedding_model: str | None = None,
) -> list[RetrievalResult]:
    """
    Retrieve the chunks most semantically similar to a query.
    """

    if not query.strip():
        raise ValueError("Query cannot be empty.")

    if top_k <= 0:
        raise ValueError("top_k must be greater than zero.")

    query_embedding = embedding_provider.embed_query(query)

    distance = Chunk.embedding.cosine_distance(
        query_embedding
    )

    filters = [] 

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
            distance.label("distance"), 
            ) 
        .join( 
            Document, 
            Chunk.document_id == Document.id, 
        ) 
        .where(*filters) 
        .order_by(distance) 
        .limit(top_k) 
    )

    rows = session.execute(statement).all()

    results = []

    for chunk, document, distance_value in rows:
        results.append(
            RetrievalResult(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                text=chunk.text,
                company=document.company,
                year=document.year,
                page_number=chunk.page_number,
                section=chunk.section,
                element_type=chunk.element_type,
                similarity=1.0 - float(distance_value),
            )
        )

    return results