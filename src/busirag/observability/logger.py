import json
import logging

from busirag.observability.models import QueryMetrics


logger = logging.getLogger("busirag")


def log_query_metrics(metrics: QueryMetrics) -> None:
    logger.info(
        json.dumps(
            {
                "event": "rag_query",
                "request_id": metrics.request_id,
                "cache_hit": metrics.cache_hit,
                "retrieval_ms": round(metrics.retrieval_ms, 2),
                "generation_ms": round(metrics.generation_ms, 2),
                "total_ms": round(metrics.total_ms, 2),
                "source_count": metrics.source_count,
            }
        )
    )