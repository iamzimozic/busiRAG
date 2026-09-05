import hashlib


def build_query_cache_key(
    query: str,
    chunking_version: str | None,
    embedding_model: str | None,
    candidate_k: int,
    top_k: int,
) -> str:
    normalized_query = " ".join(query.strip().split())

    query_hash = hashlib.sha256(
        normalized_query.encode("utf-8")
    ).hexdigest()

    return (
        "rag:v1:"
        f"chunking={chunking_version}:"
        f"embedding={embedding_model}:"
        f"candidate_k={candidate_k}:"
        f"top_k={top_k}:"
        f"query={query_hash}"
    )