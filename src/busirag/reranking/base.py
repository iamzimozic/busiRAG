from typing import Protocol


class Reranker(Protocol):
    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
    ) -> list[tuple[int, float]]:
        """
        Return (original_document_index, relevance_score),
        ordered from most relevant to least relevant.
        """
        ...