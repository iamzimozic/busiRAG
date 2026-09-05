import redis


class RedisCache:
    def __init__(
        self,
        url: str,
    ):
        self.client = redis.Redis.from_url(
            url,
            decode_responses=True,
        )

    def get(self, key: str) -> str | None:
        return self.client.get(key)

    def set(
        self,
        key: str,
        value: str,
        ttl: int,
    ) -> None:
        self.client.set(
            key,
            value,
            ex=ttl,
        )