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


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "postgres://u:p@host:5432/db",
            "postgresql+psycopg://u:p@host:5432/db",
        ),
        (
            "postgresql://u:p@host/db?sslmode=require",
            "postgresql+psycopg://u:p@host/db?sslmode=require",
        ),
        (
            "postgresql+psycopg://u:p@host/db",
            "postgresql+psycopg://u:p@host/db",
        ),
    ],
)
def test_database_url_uses_psycopg_driver(url, expected):
    from busirag.db.session import normalize_database_url

    assert normalize_database_url(url) == expected


def test_model_device_is_passed_to_local_models(monkeypatch):
    import busirag.embeddings.local as embeddings_module
    import busirag.reranking.local as reranking_module
    from busirag.rag.factory import build_rag_service

    created = []

    class FakeModel:
        def __init__(self, model_name, device=None):
            created.append((model_name, device))

    monkeypatch.setattr(embeddings_module, "SentenceTransformer", FakeModel)
    monkeypatch.setattr(reranking_module, "CrossEncoder", FakeModel)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("RETRIEVAL_MODE", raising=False)

    build_rag_service(
        settings=_settings(
            model_device="cpu",
            retrieval_mode="hybrid_rerank",
        ),
        cache=None,
    )

    assert created == [
        ("BAAI/bge-small-en-v1.5", "cpu"),
        ("BAAI/bge-reranker-v2-m3", "cpu"),
    ]


def test_model_device_defaults_to_automatic():
    assert _settings().model_device is None
