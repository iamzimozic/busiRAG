from dataclasses import dataclass, field

from pydantic import BaseModel

from busirag.generation.context import ContextItem


class GeneratedAnswer(BaseModel):
    answer: str
    citations: list[str]


@dataclass(frozen=True)
class QueryDiagnostics:
    """Per-request details for the UI; never cached."""

    request_id: str
    cache_hit: bool
    retrieval_mode: str
    generation_model: str | None
    retrieval_ms: float
    generation_ms: float
    total_ms: float


@dataclass(frozen=True)
class RAGResponse:
    answer: str
    # Context items the answer cites.
    sources: list[ContextItem]
    # Every context item given to the LLM, in retrieval order.
    retrieved: list[ContextItem] = field(default_factory=list)
    diagnostics: QueryDiagnostics | None = field(
        default=None,
        compare=False,
    )