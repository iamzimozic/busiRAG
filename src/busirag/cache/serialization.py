import json
from dataclasses import asdict

from busirag.generation.context import ContextItem
from busirag.generation.response import RAGResponse


def _deserialize_item(item: dict) -> ContextItem:
    return ContextItem(
        citation_id=item["citation_id"],
        rank=item["rank"],
        chunk_id=item["chunk_id"],
        company=item["company"],
        filename=item["filename"],
        year=item["year"],
        page_number=item["page_number"],
        section=item["section"],
        element_type=item["element_type"],
        text=item["text"],
        # Absent in entries cached before scores were stored.
        retrieval_score=item.get("retrieval_score"),
        rerank_score=item.get("rerank_score"),
    )


def serialize_rag_response(response: RAGResponse) -> str:
    # Diagnostics describe a single request and are not cached.
    payload = {
        "answer": response.answer,
        "sources": [asdict(source) for source in response.sources],
        "retrieved": [asdict(item) for item in response.retrieved],
    }

    return json.dumps(payload)


def deserialize_rag_response(value: str) -> RAGResponse:
    payload = json.loads(value)

    return RAGResponse(
        answer=payload["answer"],
        sources=[
            _deserialize_item(source)
            for source in payload["sources"]
        ],
        retrieved=[
            _deserialize_item(item)
            for item in payload.get("retrieved", [])
        ],
    )
