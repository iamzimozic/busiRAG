import os
from dotenv import load_dotenv

import pytest

from busirag.cache import RedisCache

load_dotenv()

@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("REDIS_URL"),
    reason="REDIS_URL not configured",
)
def test_redis_cache_round_trip():
    cache = RedisCache(os.environ["REDIS_URL"])

    cache.set(
        key="busirag:test:integration",
        value="hello",
        ttl=30,
    )

    try:
        assert cache.get("busirag:test:integration") == "hello"
    finally:
        cache.client.delete("busirag:test:integration")


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("REDIS_URL"),
    reason="REDIS_URL not configured",
)
def test_redis_cache_sets_ttl():
    cache = RedisCache(os.environ["REDIS_URL"])

    key = "busirag:test:ttl"

    cache.set(
        key=key,
        value="hello",
        ttl=30,
    )

    try:
        ttl = cache.client.ttl(key)

        assert 0 < ttl <= 30
    finally:
        cache.client.delete(key)