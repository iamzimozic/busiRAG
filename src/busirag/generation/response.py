from dataclasses import dataclass

from pydantic import BaseModel

from busirag.generation.context import ContextItem


class GeneratedAnswer(BaseModel):
    answer: str
    citations: list[str]


@dataclass(frozen=True)
class RAGResponse:
    answer: str
    sources: list[ContextItem]