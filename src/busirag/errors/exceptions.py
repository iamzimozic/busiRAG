class BusiragError(Exception):
    """Base exception for application-level errors."""


class InvalidQueryError(BusiragError):
    """Raised when a query is invalid."""


class RetrievalError(BusiragError):
    """Raised when retrieval fails."""


class GenerationError(BusiragError):
    """Raised when answer generation fails."""


class ConfigurationError(BusiragError):
    """Raised when application configuration is invalid."""


class RateLimitExceededError(BusiragError):
    """Raised when a client exceeds the query rate limit."""

    def __init__(self, message: str, retry_after: int):
        super().__init__(message)
        self.retry_after = retry_after


class FeatureDisabledError(BusiragError):
    """Raised when an endpoint is disabled by configuration."""
