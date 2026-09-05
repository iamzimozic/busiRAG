from typing import Protocol


class Cache(Protocol):
    def get(self, key: str) -> str | None:
        ...

    def set(self, key: str, value: str, ttl: int) -> None:
        ...