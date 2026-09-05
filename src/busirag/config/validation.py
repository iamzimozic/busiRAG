from busirag.errors import ConfigurationError
from busirag.versioning import EMBEDDING_MODEL


def validate_embedding_configuration(configured_model: str) -> None:
    if configured_model != EMBEDDING_MODEL:
        raise ConfigurationError(
            "Configured embedding model does not match the indexed "
            f"embedding model. Configured: {configured_model!r}; "
            f"Indexed: {EMBEDDING_MODEL!r}."
        )