from busirag.cache.serialization import (
    deserialize_rag_response,
    serialize_rag_response,
)
from busirag.generation.context import ContextItem
from busirag.generation.response import RAGResponse


def test_rag_response_round_trip():
    original = RAGResponse(
        answer="Apple's net income was $96,995 million.",
        sources=[
            ContextItem(
                citation_id="S1",
                rank=1,
                chunk_id=435,
                company="apple",
                year=2023,
                page_number=32,
                section="Financial Statements",
                element_type="text",
                text="Net income was $96,995 million.",
            )
        ],
    )

    serialized = serialize_rag_response(original)
    restored = deserialize_rag_response(serialized)

    assert restored == original