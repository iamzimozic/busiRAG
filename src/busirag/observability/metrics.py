from prometheus_client import Counter, Histogram


QUERY_COUNT = Counter(
    "busirag_queries_total",
    "Total number of RAG queries.",
)

CACHE_HITS = Counter(
    "busirag_cache_hits_total",
    "Total number of RAG cache hits.",
)

CACHE_MISSES = Counter(
    "busirag_cache_misses_total",
    "Total number of RAG cache misses.",
)

QUERY_ERRORS = Counter(
    "busirag_query_errors_total",
    "Total number of RAG query errors.",
)

RETRIEVAL_LATENCY = Histogram(
    "busirag_retrieval_duration_seconds",
    "Time spent retrieving documents.",
)

GENERATION_LATENCY = Histogram(
    "busirag_generation_duration_seconds",
    "Time spent generating an answer.",
)

QUERY_LATENCY = Histogram(
    "busirag_query_duration_seconds",
    "Total time spent processing a RAG query.",
)


def record_query(
    *,
    cache_hit: bool,
    retrieval_ms: float,
    generation_ms: float,
    total_ms: float,
) -> None:
    QUERY_COUNT.inc()

    if cache_hit:
        CACHE_HITS.inc()
    else:
        CACHE_MISSES.inc()

    RETRIEVAL_LATENCY.observe(retrieval_ms / 1000)
    GENERATION_LATENCY.observe(generation_ms / 1000)
    QUERY_LATENCY.observe(total_ms / 1000)


def record_query_error() -> None:
    QUERY_ERRORS.inc()