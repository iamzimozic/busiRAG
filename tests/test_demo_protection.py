import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from busirag.api.dependencies import (
    get_rag_service,
    get_rate_limiter,
    get_settings,
)
from busirag.api.main import app
from busirag.api.rate_limit import RateLimiter
from busirag.config import ApiSettings, Settings
from busirag.errors import RateLimitExceededError
from busirag.generation.response import RAGResponse

from test_api import get_test_auth_headers


class FakePipeline:
    def __init__(self, store):
        self.store = store
        self.ops = []

    def incr(self, key):
        self.ops.append(("incr", key))

    def expire(self, key, ttl):
        self.ops.append(("expire", key, ttl))

    def execute(self):
        results = []

        for op in self.ops:
            if op[0] == "incr":
                self.store.counts[op[1]] = self.store.counts.get(op[1], 0) + 1
                results.append(self.store.counts[op[1]])
            else:
                self.store.ttls[op[1]] = op[2]
                results.append(True)

        return results


class FakeStore:
    def __init__(self):
        self.counts = {}
        self.ttls = {}

    def pipeline(self):
        return FakePipeline(self)


class BrokenStore:
    def pipeline(self):
        raise ConnectionError("redis down")


def test_disabled_limiter_never_touches_store():
    limiter = RateLimiter(BrokenStore())

    assert not limiter.enabled
    limiter.check("1.2.3.4")


def test_per_minute_limit_is_per_client_and_window():
    now = [120.0]
    limiter = RateLimiter(
        FakeStore(),
        per_minute=2,
        clock=lambda: now[0],
    )

    limiter.check("a")
    limiter.check("a")
    limiter.check("b")

    with pytest.raises(RateLimitExceededError) as exc_info:
        limiter.check("a")

    assert exc_info.value.retry_after == 60

    now[0] = 180.0
    limiter.check("a")


def test_daily_limit_is_global_across_clients():
    store = FakeStore()
    limiter = RateLimiter(
        store,
        per_day=2,
        clock=lambda: 86400 * 3 + 3600,
    )

    limiter.check("a")
    limiter.check("b")

    with pytest.raises(RateLimitExceededError, match="daily") as exc_info:
        limiter.check("c")

    assert exc_info.value.retry_after == 86400 - 3600
    assert store.ttls == {"ratelimit:query:day:3": 86400}


def test_limiter_fails_open_when_store_is_unavailable():
    RateLimiter(BrokenStore(), per_minute=1).check("a")


@pytest.mark.skipif(
    not os.getenv("REDIS_URL") and not os.path.exists(".env"),
    reason="Redis not configured",
)
def test_limiter_against_real_redis():
    from busirag.cache import RedisCache

    client = RedisCache(Settings().redis_url).client
    prefix = f"ratelimit:test:{uuid4().hex}"
    limiter = RateLimiter(client, per_minute=1, prefix=prefix)

    try:
        limiter.check("client")

        with pytest.raises(RateLimitExceededError):
            limiter.check("client")
    finally:
        for key in client.scan_iter(f"{prefix}:*"):
            client.delete(key)


class OkRAGService:
    def query(self, session, query, tenant_id, request_id=None):
        return RAGResponse(answer="ok", sources=[])


def settings(**overrides):
    return Settings(
        _env_file=None,
        database_url="postgresql+psycopg://u:p@localhost/db",
        jwt_secret_key="secret",
        gemini_api_key="key",
        **overrides,
    )


@pytest.fixture
def client():
    app.dependency_overrides[get_rag_service] = OkRAGService

    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_query_longer_than_limit_is_rejected(client):
    app.dependency_overrides[get_settings] = lambda: settings(
        max_query_length=20
    )

    response = client.post(
        "/query",
        json={"query": "x" * 21},
        headers=get_test_auth_headers(),
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": "invalid_query",
        "message": "query must be at most 20 characters",
    }


def test_query_rate_limit_returns_429_with_retry_after(client):
    limiter = RateLimiter(FakeStore(), per_minute=1)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter

    headers = get_test_auth_headers()

    first = client.post("/query", json={"query": "q"}, headers=headers)
    second = client.post("/query", json={"query": "q"}, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"] == "rate_limited"
    assert 0 < int(second.headers["Retry-After"]) <= 60


def test_demo_mode_blocks_writes(client):
    app.dependency_overrides[get_settings] = lambda: settings(demo_mode=True)

    headers = get_test_auth_headers()

    register = client.post(
        "/auth/register",
        json={"email": f"demo-{uuid4().hex}@x.io", "password": "password1"},
    )
    upload = client.post(
        "/documents",
        files={"file": ("a.pdf", b"%PDF", "application/pdf")},
        data={"company": "acme", "year": "2024"},
        headers=headers,
    )
    delete = client.delete("/documents/999999", headers=headers)

    for response in (register, upload, delete):
        assert response.status_code == 403
        assert response.json()["error"] == "feature_disabled"

    # Reading still works.
    assert client.post(
        "/query",
        json={"query": "q"},
        headers=headers,
    ).status_code == 200


def test_cors_origins_are_parsed_from_a_comma_separated_list():
    api_settings = ApiSettings(
        _env_file=None,
        cors_origins="https://demo.example.com/, http://localhost:5173 ,",
    )

    assert api_settings.cors_origin_list == [
        "https://demo.example.com",
        "http://localhost:5173",
    ]
