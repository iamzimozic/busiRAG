from fastapi.testclient import TestClient

from busirag.api.dependencies import get_rag_service
from busirag.api.main import app
from busirag.auth.jwt import create_access_token
from busirag.db.models import User
from busirag.db.session import SessionLocal
from busirag.cache import RedisCache
from busirag.cache.keys import build_query_cache_key
from busirag.cache.serialization import serialize_rag_response
from busirag.generation.context import ContextItem
from busirag.generation.response import RAGResponse
from busirag.errors import InvalidQueryError
from busirag.config import Settings

from sqlalchemy import select

from uuid import uuid4

def test_register_user():
    email = f"register-test-{uuid4().hex}@busirag.local"

    with TestClient(app) as client:
        response = client.post(
            "/auth/register",
            json={
                "email": email,
                "password": "password123",
            },
        )

    assert response.status_code == 201

    data = response.json()

    assert data["email"] == email
    assert data["tenant_id"] > 0
    assert data["id"] > 0

def test_login_user():
    email = f"login-test-{uuid4().hex}@busirag.local"

    with TestClient(app) as client:
        register_response = client.post(
            "/auth/register",
            json={
                "email": email,
                "password": "password123",
            },
        )

        assert register_response.status_code == 201

        response = client.post(
            "/auth/login",
            json={
                "email": email,
                "password": "password123",
            },
        )

    assert response.status_code == 200

    data = response.json()

    assert data["token_type"] == "bearer"
    assert isinstance(data["access_token"], str)
    assert len(data["access_token"]) > 0

def test_login_user_rejects_invalid_password():
    email = f"invalid-login-test-{uuid4().hex}@busirag.local"

    with TestClient(app) as client:
        register_response = client.post(
            "/auth/register",
            json={
                "email": email,
                "password": "password123",
            },
        )

        assert register_response.status_code == 201

        response = client.post(
            "/auth/login",
            json={
                "email": email,
                "password": "wrongpassword",
            },
        )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid email or password",
    }

class MockRAGService:
    def query(self, session, query, tenant_id, request_id=None):
        return RAGResponse(
            answer="Apple's net income was $96,995 million.",
            sources=[
                ContextItem(
                    citation_id="S1",
                    rank=1,
                    chunk_id=435,
                    company="apple",
                    year=2023,
                    page_number=32,
                    section=None,
                    element_type="text",
                    text="Net income was $96,995 million.",
                )
            ],
        )


def test_query_endpoint():
    app.dependency_overrides[get_rag_service] = (
        lambda: MockRAGService()
    )

    try:
        client = TestClient(app)

        response = client.post(
            "/query",
            json={
                "query": "What was Apple's net income in 2023?"
            },
            headers=get_test_auth_headers(),
        )

        assert response.status_code == 200

        data = response.json()

        assert data["answer"] == (
            "Apple's net income was $96,995 million."
        )

        assert data["sources"] == [
            {
                "citation_id": "S1",
                "company": "apple",
                "year": 2023,
                "page_number": 32,
                "chunk_id": 435,
            }
        ]

    finally:
        app.dependency_overrides.clear()

def test_query_endpoint_rejects_blank_query():
    app.dependency_overrides[get_rag_service] = (
        lambda: MockRAGService()
    )

    try:
        client = TestClient(app)

        response = client.post(
            "/query",
            json={
                "query": "   "
            },
            headers=get_test_auth_headers(),
        )

        assert response.status_code == 422

    finally:
        app.dependency_overrides.clear()

def test_invalid_query_error_handler():
    class FailingRAGService:
        def query(self, session, query, tenant_id, request_id=None):
            raise InvalidQueryError("query must not be empty")

    app.dependency_overrides[get_rag_service] = lambda: FailingRAGService()

    try:
        client = TestClient(app)

        response = client.post(
            "/query",
            json={"query": "valid query"},
            headers=get_test_auth_headers(),
        )

        assert response.status_code == 400
        assert response.json() == {
            "error": "invalid_query",
            "message": "query must not be empty",
        }
    finally:
        app.dependency_overrides.clear()

def test_query_endpoint_returns_cached_response():
    settings = Settings()
    cache = RedisCache(settings.redis_url)

    query = "What was Apple's revenue?"

    cached_response = RAGResponse(
        answer="Cached Apple revenue answer.",
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
                text="Cached source.",
            )
        ],
    )

    cache_key = build_query_cache_key(
        query=query,
        chunking_version="v3-table-context",
        embedding_model="BAAI/bge-small-en-v1.5",
        candidate_k=50,
        tenant_id=1,
        top_k=10,
    )

    cache.set(
        key=cache_key,
        value=serialize_rag_response(cached_response),
        ttl=30,
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/query",
                json={"query": query},
                headers=get_test_auth_headers(),
            )

        assert response.status_code == 200

        assert response.json() == {
            "answer": "Cached Apple revenue answer.",
            "sources": [
                {
                    "citation_id": "S1",
                    "company": "apple",
                    "year": 2023,
                    "page_number": 10,
                    "chunk_id": 123,
                }
            ],
        }

    finally:
        cache.client.delete(cache_key)

def test_query_endpoint_caches_fresh_response():
    from busirag.cache import RedisCache
    from busirag.cache.keys import build_query_cache_key
    from busirag.cache.serialization import deserialize_rag_response
    from busirag.config import Settings
    from busirag.generation.context import ContextItem
    from busirag.generation.response import RAGResponse
    from busirag.rag.service import RAGService

    settings = Settings()
    cache = RedisCache(settings.redis_url)

    query = "What was Apple's revenue?"

    class FakeEmbeddingProvider:
        pass

    class FakeReranker:
        pass

    class FakeGenerationService:
        def generate(self, query, retrieval_results):
            return RAGResponse(
                answer="Fresh API answer.",
                sources=[
                    ContextItem(
                        citation_id="S1",
                        rank=1,
                        chunk_id=456,
                        company="apple",
                        year=2023,
                        page_number=20,
                        section=None,
                        element_type="text",
                        text="Fresh source.",
                    )
                ],
            )

    service = RAGService(
        embedding_provider=FakeEmbeddingProvider(),
        reranker=FakeReranker(),
        generation_service=FakeGenerationService(),
        cache=cache,
        chunking_version="v3-table-context",
        embedding_model="BAAI/bge-small-en-v1.5",
        candidate_k=50,
        top_k=10,
    )

    import busirag.rag.service as rag_service_module

    original_retrieval = rag_service_module.retrieve_reranked_chunks

    def fake_retrieval(**kwargs):
        return []

    rag_service_module.retrieve_reranked_chunks = fake_retrieval

    cache_key = build_query_cache_key(
        query=query,
        chunking_version="v3-table-context",
        embedding_model="BAAI/bge-small-en-v1.5",
        candidate_k=50,
        tenant_id=1,
        top_k=10,
    )

    cache.client.delete(cache_key)

    app.dependency_overrides[get_rag_service] = lambda: service

    try:
        with TestClient(app) as client:
            response = client.post(
                "/query",
                json={"query": query},
                headers=get_test_auth_headers(),
            )

        assert response.status_code == 200

        assert response.json() == {
            "answer": "Fresh API answer.",
            "sources": [
                {
                    "citation_id": "S1",
                    "company": "apple",
                    "year": 2023,
                    "page_number": 20,
                    "chunk_id": 456,
                }
            ],
        }

        cached_value = cache.get(cache_key)

        assert cached_value is not None

        cached_response = deserialize_rag_response(cached_value)

        assert cached_response.answer == "Fresh API answer."
        assert cached_response.sources[0].chunk_id == 456

    finally:
        rag_service_module.retrieve_reranked_chunks = original_retrieval
        app.dependency_overrides.clear()
        cache.client.delete(cache_key)

def get_test_auth_headers() -> dict[str, str]:
    settings = Settings()

    with SessionLocal() as session:
        user = session.scalar(
            select(User).where(User.email == "test@busirag.local")
        )

        if user is None:
            user = User(
                email="test@busirag.local",
                password_hash="test",
                tenant_id=1,
            )
            session.add(user)
            session.commit()
            session.refresh(user)

        token = create_access_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            settings=settings,
        )

    return {"Authorization": f"Bearer {token}"}