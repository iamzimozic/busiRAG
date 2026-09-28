from dataclasses import dataclass

from busirag.retrieval.vector import RetrievalResult


@dataclass(frozen=True)
class ContextItem:
    citation_id: str
    rank: int
    chunk_id: int
    company: str
    filename: str
    year: int
    page_number: int | None
    section: str | None
    element_type: str
    text: str
    retrieval_score: float | None = None
    rerank_score: float | None = None


def _scores(result) -> tuple[float | None, float | None]:
    """(retrieval_score, rerank_score) for any retrieval result type."""

    if hasattr(result, "retrieval_score"):
        return result.retrieval_score, result.score

    if hasattr(result, "similarity"):
        return result.similarity, None

    return getattr(result, "score", None), None


def build_context(results: list[RetrievalResult]) -> list[ContextItem]:
    return [
        ContextItem(
            citation_id=f"S{rank}",
            rank=rank,
            chunk_id=result.chunk_id,
            company=result.company,
            filename=result.filename,
            year=result.year,
            page_number=result.page_number,
            section=result.section,
            element_type=result.element_type,
            text=result.text,
            retrieval_score=_scores(result)[0],
            rerank_score=_scores(result)[1],
        )
        for rank, result in enumerate(results, start=1)
    ]