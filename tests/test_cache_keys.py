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