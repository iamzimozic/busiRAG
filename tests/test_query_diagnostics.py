import json

import pytest
from fastapi.testclient import TestClient

from busirag.api.dependencies import get_rag_service
from busirag.api.main import app
from busirag.cache.serialization import (
    deserialize_rag_response,
    serialize_rag_response,
)
from busirag.generation.context import ContextItem, build_context
from busirag.generation.mock import MockLLMProvider
from busirag.generation.response import QueryDiagnostics, RAGResponse
from busirag.generation.service import GenerationService
from busirag.rag.service import RAGService
from busirag.retrieval.hybrid import HybridRetrievalResult
from busirag.retrieval.reranked import RerankedRetrievalResult
from busirag.retrieval.vector import RetrievalResult

from test_api import get_test_auth_headers

COMMON = dict(
    document_id=1,
    text="Net income $ 96,995",
    company="apple",
    filename="apple-2023.pdf",
    year=2023,
    page_number=32,
    section="Income statement",
    element_type="table",
)


def item(citation_id, chunk_id, retrieval_score=0.03, rerank_score=0.9):
    return ContextItem(
        citation_id=citation_id,
        rank=int(citation_id[1:]),
        chunk_id=chunk_id,
        company="apple",
        filename="apple-2023.pdf",
        year=2023,
        page_number=32,
        section=None,
        element_type="table",
        text=f"chunk {chunk_id}",
        retrieval_score=retrieval_score,
        rerank_score=rerank_score,
    )


def test_build_context_keeps_scores_for_each_retrieval_mode():
    reranked, hybrid, dense = build_context(
        [
            RerankedRetrievalResult(
                chunk_id=1, score=0.97, retrieval_score=0.032, **COMMON
            ),
            HybridRetrievalResult(chunk_id=2, score=0.016, **COMMON),
            RetrievalResult(chunk_id=3, similarity=0.81, **COMMON),
        ]
    )

    assert (reranked.retrieval_score, reranked.rerank_score) == (0.032, 0.97)
    assert (hybrid.retrieval_score, hybrid.rerank_score) == (0.016, None)
    assert (dense.retrieval_score, dense.rerank_score) == (0.81, None)


def test_generation_service_returns_all_retrieved_items():
    response = GenerationService(MockLLMProvider()).generate(
        "q",
        [
            RetrievalResult(chunk_id=1, similarity=0.8, **COMMON),
            RetrievalResult(chunk_id=2, similarity=0.7, **COMMON),
        ],
    )

    assert response.sources == []
    assert [i.chunk_id for i in response.retrieved] == [1, 2]


def test_serialization_round_trips_retrieved_and_skips_diagnostics():
    response = RAGResponse(
        answer="a",
        sources=[item("S1", 1)],
        retrieved=[item("S1", 1), item("S2", 2, rerank_score=None)],
        diagnostics=QueryDiagnostics(
            request_id="r",
            cache_hit=False,
            retrieval_mode="hybrid_rerank",
            generation_model="gemini:m",
            retrieval_ms=1.0,
            generation_ms=2.0,
            total_ms=3.0,
        ),
    )

    serialized = serialize_rag_response(response)

    assert "diagnostics" not in json.loads(serialized)

    restored = deserialize_rag_response(serialized)

    assert restored == response
    assert restored.diagnostics is None
    assert restored.retrieved[1].rerank_score is None


def test_entries_cached_before_scores_still_deserialize():
    legacy = json.dumps(
        {
            "answer": "old",
            "sources": [
                {
                    "citation_id": "S1",
                    "rank": 1,
                    "chunk_id": 1,
                    "company": "apple",
                    "filename": "apple-2023.pdf",
                    "year": 2023,
                    "page_number": 1,
                    "section": None,
                    "element_type": "text",
                    "text": "t",
                }
            ],
        }
    )

    restored = deserialize_rag_response(legacy)

    assert restored.sources[0].retrieval_score is None
    assert restored.retrieved == []


class DictCache:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ttl):
        self.values[key] = value


def test_rag_service_attaches_diagnostics_on_miss_and_hit(monkeypatch):
    import busirag.rag.service as rag_service_module

    monkeypatch.setattr(
        rag_service_module,
        "retrieve_reranked_chunks",
        lambda **kwargs: [
            RerankedRetrievalResult(
                chunk_id=1, score=0.9, retrieval_score=0.03, **COMMON
            )
        ],
    )

    service = RAGService(
        embedding_provider=object(),
        reranker=object(),
        generation_service=GenerationService(MockLLMProvider()),
        cache=DictCache(),
        generation_model="mock:model",
    )

    miss = service.query(None, "q", tenant_id=1, request_id="req-1")
    hit = service.query(None, "q", tenant_id=1, request_id="req-2")

    assert miss.diagnostics.cache_hit is False
    assert miss.diagnostics.request_id == "req-1"
    assert miss.diagnostics.retrieval_mode == "hybrid_rerank"
    assert miss.diagnostics.generation_model == "mock:model"
    assert miss.diagnostics.total_ms >= miss.diagnostics.retrieval_ms

    assert hit.diagnostics.cache_hit is True
    assert hit.diagnostics.request_id == "req-2"
    assert hit.diagnostics.retrieval_ms == 0.0
    assert hit.retrieved[0].rerank_score == 0.9
    assert hit == miss


class DiagnosticsRAGService:
    def query(self, session, query, tenant_id, request_id=None):
        return RAGResponse(
            answer="Apple's net income was $96,995 million.",
            sources=[item("S2", 20, rerank_score=0.95)],
            retrieved=[
                item("S1", 10, rerank_score=0.4),
                item("S2", 20, rerank_score=0.95),
            ],
            diagnostics=QueryDiagnostics(
                request_id=request_id,
                cache_hit=False,
                retrieval_mode="hybrid_rerank",
                generation_model="gemini:gemini-2.5-flash",
                retrieval_ms=120.5,
                generation_ms=800.25,
                total_ms=925.0,
            ),
        )


def test_query_endpoint_returns_diagnostics():
    app.dependency_overrides[get_rag_service] = DiagnosticsRAGService

    try:
        response = TestClient(app).post(
            "/query",
            json={"query": "What was Apple's net income?"},
            headers=get_test_auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    data = response.json()

    assert data["sources"][0]["text"] == "chunk 20"
    assert data["sources"][0]["rerank_score"] == 0.95

    diagnostics = data["diagnostics"]

    assert diagnostics["request_id"] == response.headers["X-Request-ID"]
    assert diagnostics["generation_model"] == "gemini:gemini-2.5-flash"
    assert diagnostics["timings"] == {
        "retrieval_ms": 120.5,
        "generation_ms": 800.25,
        "total_ms": 925.0,
    }
    assert [
        (chunk["citation_id"], chunk["cited"])
        for chunk in diagnostics["retrieved"]
    ] == [("S1", False), ("S2", True)]


class FailingCache:
    def get(self, key):
        raise ConnectionError("redis over quota")

    def set(self, key, value, ttl):
        raise ConnectionError("redis over quota")


def _reranked_service(monkeypatch, cache, budget=None):
    import busirag.rag.service as rag_service_module

    monkeypatch.setattr(
        rag_service_module,
        "retrieve_reranked_chunks",
        lambda **kwargs: [
            RerankedRetrievalResult(
                chunk_id=1, score=0.9, retrieval_score=0.03, **COMMON
            )
        ],
    )

    return RAGService(
        embedding_provider=object(),
        reranker=object(),
        generation_service=GenerationService(MockLLMProvider()),
        cache=cache,
        generation_budget=budget,
    )


def test_cache_failures_degrade_to_a_miss(monkeypatch):
    service = _reranked_service(monkeypatch, FailingCache())

    result = service.query(None, "q", tenant_id=1)

    assert result.answer == "MOCK ANSWER"
    assert result.diagnostics.cache_hit is False


class ExhaustedBudget:
    def __init__(self):
        self.checks = 0

    def check_daily_budget(self):
        from busirag.errors import RateLimitExceededError

        self.checks += 1
        raise RateLimitExceededError("daily cap", retry_after=60)


def test_daily_budget_applies_only_to_cache_misses(monkeypatch):
    from busirag.errors import RateLimitExceededError

    cache = DictCache()
    budget = ExhaustedBudget()

    # Warm the cache without a budget, then exhaust the budget.
    _reranked_service(monkeypatch, cache).query(None, "cached q", tenant_id=1)
    service = _reranked_service(monkeypatch, cache, budget)

    hit = service.query(None, "cached q", tenant_id=1)

    assert hit.diagnostics.cache_hit is True
    assert budget.checks == 0

    with pytest.raises(RateLimitExceededError):
        service.query(None, "new q", tenant_id=1)

    assert budget.checks == 1


def test_build_rag_service_cache_key_matches_api_configuration(monkeypatch):
    from busirag.cache.keys import build_query_cache_key
    from busirag.config import Settings
    from busirag.rag.factory import build_rag_service

    for name in ("LLM_PROVIDER", "RETRIEVAL_MODE", "TOP_K", "CANDIDATE_K"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://u:p@localhost/db",
        jwt_secret_key="secret",
        llm_provider="ollama",
        retrieval_mode="hybrid",
        top_k=8,
    )

    service = build_rag_service(
        settings=settings,
        cache=None,
        embedding_provider=object(),
    )

    assert service.reranker is None
    assert service.cache_key("  What was   revenue? ", 7) == (
        build_query_cache_key(
            query="What was revenue?",
            tenant_id=7,
            chunking_version="v3-table-context",
            embedding_model="BAAI/bge-small-en-v1.5",
            candidate_k=50,
            top_k=8,
            retrieval_mode="hybrid",
            generation_model="ollama:qwen2.5:7b",
        )
    )
