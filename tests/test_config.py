import pytest

from busirag.config.validation import validate_embedding_configuration
from busirag.errors import ConfigurationError
from busirag.versioning import EMBEDDING_MODEL


def test_matching_embedding_model_is_valid():
    validate_embedding_configuration(EMBEDDING_MODEL)


def test_mismatched_embedding_model_is_rejected():
    with pytest.raises(ConfigurationError, match="does not match"):
        validate_embedding_configuration("some-other-embedding-model")


def _settings(**overrides):
    from busirag.config import Settings

    return Settings(
        _env_file=None,
        database_url="postgresql+psycopg://u:p@localhost/db",
        jwt_secret_key="secret",
        gemini_api_key="key",
        **overrides,
    )


def test_retrieval_mode_defaults_to_hybrid_rerank():
    assert _settings().retrieval_mode == "hybrid_rerank"


def test_retrieval_mode_can_be_configured():
    assert _settings(retrieval_mode="dense").retrieval_mode == "dense"


def test_unknown_retrieval_mode_is_rejected():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _settings(retrieval_mode="bm25")
