from dataclasses import dataclass


@dataclass(slots=True)
class QueryMetrics:
    request_id: str
    cache_hit: bool
    retrieval_ms: float
    generation_ms: float
    total_ms: float
    source_count: int