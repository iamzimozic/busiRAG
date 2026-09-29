import logging
import time
from typing import Protocol

from busirag.errors import RateLimitExceededError

logger = logging.getLogger(__name__)


class CounterStore(Protocol):
    """The subset of the Redis client the limiter uses."""

    def pipeline(self): ...


class RateLimiter:
    """
    Fixed-window query limits stored in Redis:

    - per client (IP) per minute, against bursts from one visitor
    - global per UTC day, to cap LLM spend for a public demo

    A limit of 0 disables it. If Redis is unavailable the limiter
    fails open (logs and allows the request) so the cache/limiter
    outage does not take the API down.
    """

    def __init__(
        self,
        store: CounterStore,
        per_minute: int = 0,
        per_day: int = 0,
        prefix: str = "ratelimit:query",
        clock=time.time,
    ):
        self.store = store
        self.per_minute = per_minute
        self.per_day = per_day
        self.prefix = prefix
        self.clock = clock

    @property
    def enabled(self) -> bool:
        return self.per_minute > 0 or self.per_day > 0

    def check(self, client_id: str) -> None:
        """Apply both the per-client and the global daily limit."""

        self._check_windows(
            self._client_windows(client_id) + self._daily_windows()
        )

    def check_client(self, client_id: str) -> None:
        """Per-client burst limit; applied to every query."""

        self._check_windows(self._client_windows(client_id))

    def check_daily_budget(self) -> None:
        """
        Global daily cap. RAGService applies it only on cache misses,
        so it limits LLM calls while cached answers keep working.
        """

        self._check_windows(self._daily_windows())

    def _client_windows(self, client_id: str) -> list[tuple]:
        if self.per_minute <= 0:
            return []

        now = self.clock()

        return [
            (
                f"{self.prefix}:minute:{int(now // 60)}:{client_id}",
                self.per_minute,
                60,
                60 - int(now % 60),
                "Too many questions. Please wait a minute and try again.",
            )
        ]

    def _daily_windows(self) -> list[tuple]:
        if self.per_day <= 0:
            return []

        now = self.clock()

        return [
            (
                f"{self.prefix}:day:{int(now // 86400)}",
                self.per_day,
                86400,
                86400 - int(now % 86400),
                "The demo's daily limit for new questions has been "
                "reached. Suggested questions still work; please try "
                "other questions tomorrow.",
            )
        ]

    def _check_windows(self, windows: list[tuple]) -> None:
        if not windows:
            return

        try:
            pipeline = self.store.pipeline()

            for key, _, ttl, _, _ in windows:
                pipeline.incr(key)
                pipeline.expire(key, ttl)

            results = pipeline.execute()
        except Exception:
            logger.exception("Rate limiter unavailable; allowing request")
            return

        counts = results[::2]

        for count, (_, limit, _, retry_after, message) in zip(
            counts,
            windows,
        ):
            if count > limit:
                raise RateLimitExceededError(
                    message,
                    retry_after=retry_after,
                )
