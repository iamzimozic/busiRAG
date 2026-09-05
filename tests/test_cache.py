from busirag.cache.base import Cache


class InMemoryCache:
    def __init__(self):
        self.data = {}

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def set(self, key: str, value: str, ttl: int) -> None:
        self.data[key] = value


def test_cache_contract():
    cache: Cache = InMemoryCache()

    assert cache.get("missing") is None

    cache.set(
        key="test-key",
        value="test-value",
        ttl=60,
    )

    assert cache.get("test-key") == "test-value"