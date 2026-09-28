from busirag.cache.keys import build_query_cache_key


def test_cache_key_is_deterministic():
    key1 = build_query_cache_key(
        query="What was Apple's revenue?",
        chunking_version="v3-table-context",
        embedding_model="BAAI/bge-small-en-v1.5",
        candidate_k=50,
        tenant_id=1,
        top_k=10,
    )

    key2 = build_query_cache_key(
        query="  What   was Apple's revenue?  ",
        chunking_version="v3-table-context",
        embedding_model="BAAI/bge-small-en-v1.5",
        candidate_k=50,
        tenant_id=1,
        top_k=10,
    )

    assert key1 == key2


def test_different_queries_have_different_keys():
    key1 = build_query_cache_key(
        query="What was Apple's revenue?",
        chunking_version="v3-table-context",
        embedding_model="BAAI/bge-small-en-v1.5",
        candidate_k=50,
        tenant_id=1,
        top_k=10,
    )

    key2 = build_query_cache_key(
        query="What was Apple's net income?",
        chunking_version="v3-table-context",
        embedding_model="BAAI/bge-small-en-v1.5",
        candidate_k=50,
        tenant_id=1,
        top_k=10,
    )

    assert key1 != key2


def test_retrieval_configuration_changes_key():
    key1 = build_query_cache_key(
        query="What was Apple's revenue?",
        chunking_version="v3-table-context",
        embedding_model="BAAI/bge-small-en-v1.5",
        candidate_k=50,
        tenant_id=1,
        top_k=10,
    )

    key2 = build_query_cache_key(
        query="What was Apple's revenue?",
        chunking_version="v3-table-context",
        embedding_model="BAAI/bge-small-en-v1.5",
        candidate_k=100,
        tenant_id=1,
        top_k=10,
    )

    assert key1 != key2

def test_different_tenants_have_different_keys():
    key1 = build_query_cache_key(
        query="What was Apple's revenue?",
        tenant_id=1,
        chunking_version="v3-table-context",
        embedding_model="BAAI/bge-small-en-v1.5",
        candidate_k=50,
        top_k=10,
    )

    key2 = build_query_cache_key(
        query="What was Apple's revenue?",
        tenant_id=2,
        chunking_version="v3-table-context",
        embedding_model="BAAI/bge-small-en-v1.5",
        candidate_k=50,
        top_k=10,
    )

    assert key1 != key2

def test_retrieval_mode_changes_key():
    common = dict(
        query="What was Apple's revenue?",
        tenant_id=1,
        chunking_version="v3-table-context",
        embedding_model="BAAI/bge-small-en-v1.5",
        candidate_k=50,
        top_k=10,
    )

    default_key = build_query_cache_key(**common)

    assert default_key == build_query_cache_key(
        **common,
        retrieval_mode="hybrid_rerank",
    )
    assert default_key != build_query_cache_key(
        **common,
        retrieval_mode="dense",
    )


def test_generation_model_changes_key():
    common = dict(
        query="What was Apple's revenue?",
        tenant_id=1,
        chunking_version="v3-table-context",
        embedding_model="BAAI/bge-small-en-v1.5",
        candidate_k=50,
        top_k=10,
    )

    gemini_key = build_query_cache_key(
        **common,
        generation_model="gemini:gemini-2.5-flash",
    )

    assert gemini_key != build_query_cache_key(
        **common,
        generation_model="ollama:qwen2.5:7b",
    )
    assert "llm=gemini:gemini-2.5-flash:" in gemini_key
