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