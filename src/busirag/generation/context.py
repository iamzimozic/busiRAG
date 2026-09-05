from dataclasses import dataclass

from busirag.retrieval.vector import RetrievalResult


@dataclass(frozen=True)
class ContextItem:
    citation_id: str
    rank: int
    chunk_id: int
    company: str
    year: int
    page_number: int | None
    section: str | None
    element_type: str
    text: str

def build_context(results: list[RetrievalResult]) -> list[ContextItem]:
    return [
        ContextItem(
            citation_id=f"S{rank}",
            rank=rank,
            chunk_id=result.chunk_id,
            company=result.company,
            year=result.year,
            page_number=result.page_number,
            section=result.section,
            element_type=result.element_type,
            text=result.text,
        )
        for rank, result in enumerate(results, start=1)
    ]