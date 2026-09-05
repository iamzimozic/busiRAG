import json

from busirag.generation.context import ContextItem
from busirag.generation.response import RAGResponse


def serialize_rag_response(response: RAGResponse) -> str:
    payload = {
        "answer": response.answer,
        "sources": [
            {
                "citation_id": source.citation_id,
                "rank": source.rank,
                "chunk_id": source.chunk_id,
                "company": source.company,
                "year": source.year,
                "page_number": source.page_number,
                "section": source.section,
                "element_type": source.element_type,
                "text": source.text,
            }
            for source in response.sources
        ],
    }

    return json.dumps(payload)


def deserialize_rag_response(value: str) -> RAGResponse:
    payload = json.loads(value)

    sources = [
        ContextItem(
            citation_id=source["citation_id"],
            rank=source["rank"],
            chunk_id=source["chunk_id"],
            company=source["company"],
            year=source["year"],
            page_number=source["page_number"],
            section=source["section"],
            element_type=source["element_type"],
            text=source["text"],
        )
        for source in payload["sources"]
    ]

    return RAGResponse(
        answer=payload["answer"],
        sources=sources,
    )