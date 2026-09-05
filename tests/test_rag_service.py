from busirag.cache.serialization import (
    deserialize_rag_response,
    serialize_rag_response,
)
from busirag.generation.context import ContextItem
from busirag.generation.mock import MockLLMProvider
from busirag.generation.response import RAGResponse
from busirag.generation.service import GenerationService
from busirag.rag.service import RAGService


def test_generation_service_with_mock():
    llm = MockLLMProvider()
    service = GenerationService(llm)

    result = service.generate(
        query="What was Apple's net income in 2023?",
        retrieval_results=[],
    )

    assert result.answer == "MOCK ANSWER"
    assert result.sources == []


def test_rag_service_returns_cached_response_without_running_pipeline():
    class FakeCache:
        def __init__(self, value):
            self.value = value
            self.get_calls = []
            self.set_calls = []

        def get(self, key):
            self.get_calls.append(key)
            return self.value

        def set(self, key, value, ttl):
            self.set_calls.append((key, value, ttl))

    class FailingEmbeddingProvider:
        def embed_query(self, query):
            raise AssertionError(
                "Retrieval should not run on cache hit"
            )

    class FailingReranker:
        def rerank(self, query, documents, top_k=None):
            raise AssertionError(
                "Reranking should not run on cache hit"
            )

    class FailingGenerationService:
        def generate(self, query, retrieval_results):
            raise AssertionError(
                "Generation should not run on cache hit"
            )

    cached_response = RAGResponse(
        answer="Cached answer",
        sources=[
            ContextItem(
                citation_id="S1",
                rank=1,
                chunk_id=123,
                company="apple",
                year=2023,
                page_number=10,
                section=None,
                element_type="text",
                text="Cached source",
            )
        ],
    )

    cache = FakeCache(
        serialize_rag_response(cached_response)
    )

    service = RAGService(
        embedding_provider=FailingEmbeddingProvider(),
        reranker=FailingReranker(),
        generation_service=FailingGenerationService(),
        cache=cache,
        chunking_version="v3-table-context",
        embedding_model="BAAI/bge-small-en-v1.5",
        candidate_k=50,
        top_k=10,
    )

    result = service.query(
        session=None,
        query="What was Apple's revenue?",
    )

    assert result == cached_response
    assert len(cache.get_calls) == 1
    assert cache.set_calls == []


def test_rag_service_runs_pipeline_and_caches_on_miss():
    class FakeCache:
        def __init__(self):
            self.get_calls = []
            self.set_calls = []

        def get(self, key):
            self.get_calls.append(key)
            return None

        def set(self, key, value, ttl):
            self.set_calls.append((key, value, ttl))

    class FakeEmbeddingProvider:
        pass

    class FakeReranker:
        pass

    class FakeGenerationService:
        def __init__(self):
            self.calls = []

        def generate(self, query, retrieval_results):
            self.calls.append((query, retrieval_results))

            return RAGResponse(
                answer="Fresh answer",
                sources=[],
            )

    fake_results = []

    cache = FakeCache()
    generation_service = FakeGenerationService()

    service = RAGService(
        embedding_provider=FakeEmbeddingProvider(),
        reranker=FakeReranker(),
        generation_service=generation_service,
        cache=cache,
        chunking_version="v3-table-context",
        embedding_model="BAAI/bge-small-en-v1.5",
        candidate_k=50,
        top_k=10,
    )

    import busirag.rag.service as rag_service_module

    original_retrieval = (
        rag_service_module.retrieve_reranked_chunks
    )

    def fake_retrieval(**kwargs):
        return fake_results

    rag_service_module.retrieve_reranked_chunks = fake_retrieval

    try:
        result = service.query(
            session=None,
            query="What was Apple's revenue?",
        )
    finally:
        rag_service_module.retrieve_reranked_chunks = (
            original_retrieval
        )

    assert result.answer == "Fresh answer"

    assert len(cache.get_calls) == 1

    assert len(generation_service.calls) == 1
    assert generation_service.calls[0] == (
        "What was Apple's revenue?",
        fake_results,
    )

    assert len(cache.set_calls) == 1

    key, value, ttl = cache.set_calls[0]

    assert key == cache.get_calls[0]
    assert ttl == 3600

    restored = deserialize_rag_response(value)

    assert restored == result


def test_rag_service_logs_cache_hit_metrics(monkeypatch):
    cached_response = RAGResponse(
        answer="Cached answer",
        sources=[
            ContextItem(
                citation_id="S1",
                rank=1,
                chunk_id=123,
                company="apple",
                year=2023,
                page_number=10,
                section=None,
                element_type="text",
                text="Cached source",
            )
        ],
    )

    class FakeCache:
        def get(self, key):
            return serialize_rag_response(cached_response)

        def set(self, key, value, ttl):
            raise AssertionError(
                "Cache set should not run on a cache hit"
            )

    captured = []

    def fake_log_query_metrics(metrics):
        captured.append(metrics)

    monkeypatch.setattr(
        "busirag.rag.service.log_query_metrics",
        fake_log_query_metrics,
    )

    service = RAGService(
        embedding_provider=None,
        reranker=None,
        generation_service=None,
        cache=FakeCache(),
        chunking_version="v3-table-context",
        embedding_model="BAAI/bge-small-en-v1.5",
        candidate_k=50,
        top_k=10,
    )

    result = service.query(
        session=None,
        query="What was Apple's revenue?",
        request_id="test-request-id",
    )

    assert result == cached_response

    assert len(captured) == 1

    metrics = captured[0]

    assert metrics.request_id == "test-request-id"
    assert metrics.cache_hit is True
    assert metrics.retrieval_ms == 0
    assert metrics.generation_ms == 0
    assert metrics.total_ms >= 0
    assert metrics.source_count == 1


def test_rag_service_logs_cache_miss_metrics(monkeypatch):
    class FakeCache:
        def get(self, key):
            return None

        def set(self, key, value, ttl):
            pass

    class FakeGenerationService:
        def generate(self, query, retrieval_results):
            return RAGResponse(
                answer="Fresh answer",
                sources=[],
            )

    captured = []

    def fake_log_query_metrics(metrics):
        captured.append(metrics)

    monkeypatch.setattr(
        "busirag.rag.service.log_query_metrics",
        fake_log_query_metrics,
    )

    service = RAGService(
        embedding_provider=None,
        reranker=None,
        generation_service=FakeGenerationService(),
        cache=FakeCache(),
        chunking_version="v3-table-context",
        embedding_model="BAAI/bge-small-en-v1.5",
        candidate_k=50,
        top_k=10,
    )

    import busirag.rag.service as rag_service_module

    monkeypatch.setattr(
        rag_service_module,
        "retrieve_reranked_chunks",
        lambda **kwargs: [],
    )

    result = service.query(
        session=None,
        query="What was Apple's revenue?",
        request_id="test-request-id",
    )

    assert result.answer == "Fresh answer"

    assert len(captured) == 1

    metrics = captured[0]

    assert metrics.request_id == "test-request-id"
    assert metrics.cache_hit is False
    assert metrics.retrieval_ms >= 0
    assert metrics.generation_ms >= 0
    assert metrics.total_ms >= 0
    assert metrics.source_count == 0