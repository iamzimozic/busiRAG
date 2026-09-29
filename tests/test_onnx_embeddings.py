import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from busirag.embeddings.onnx import OnnxEmbeddingProvider


class FakeTokenizer:
    def __init__(self):
        self.truncation = None
        self.padding = False

    def enable_truncation(self, max_length):
        self.truncation = max_length

    def enable_padding(self):
        self.padding = True

    def encode_batch(self, texts):
        return [
            SimpleNamespace(
                ids=[101, len(text), 102],
                attention_mask=[1, 1, 1],
                type_ids=[0, 0, 0],
            )
            for text in texts
        ]


class FakeSession:
    def __init__(self, with_token_types=True):
        names = ["input_ids", "attention_mask"]

        if with_token_types:
            names.append("token_type_ids")

        self.inputs = [SimpleNamespace(name=name) for name in names]
        self.feeds = []

    def get_inputs(self):
        return self.inputs

    def run(self, output_names, feed):
        self.feeds.append(feed)
        batch = feed["input_ids"].shape[0]
        hidden = np.zeros((batch, 3, 2), dtype=np.float32)
        # CLS token = [3, 4] (norm 5); other positions must be ignored.
        hidden[:, 0] = [3.0, 4.0]
        hidden[:, 1:] = 100.0
        return [hidden]


def provider(**kwargs):
    return OnnxEmbeddingProvider(
        tokenizer=FakeTokenizer(),
        session=kwargs.pop("session", FakeSession()),
        **kwargs,
    )


def test_uses_normalized_cls_embedding():
    assert provider().embed_query("net income") == pytest.approx([0.6, 0.8])


def test_configures_tokenizer_and_feeds_all_model_inputs():
    session = FakeSession()
    embedder = provider(session=session, max_length=256)

    embedder.embed_query("q")

    assert embedder.tokenizer.truncation == 256
    assert embedder.tokenizer.padding is True
    assert set(session.feeds[0]) == {
        "input_ids",
        "attention_mask",
        "token_type_ids",
    }
    assert session.feeds[0]["input_ids"].dtype == np.int64


def test_omits_token_type_ids_when_model_has_no_such_input():
    session = FakeSession(with_token_types=False)

    provider(session=session).embed_query("q")

    assert set(session.feeds[0]) == {"input_ids", "attention_mask"}


def test_embed_documents_batches():
    session = FakeSession()
    embeddings = provider(session=session, batch_size=2).embed_documents(
        ["a", "b", "c", "d", "e"]
    )

    assert len(embeddings) == 5
    assert [feed["input_ids"].shape[0] for feed in session.feeds] == [2, 2, 1]
    assert provider().dimension == 2


def test_factory_selects_embedding_backend(monkeypatch):
    import busirag.embeddings.local as local_module
    import busirag.embeddings.onnx as onnx_module
    from busirag.config import Settings
    from busirag.rag.factory import create_embedding_provider

    created = []

    monkeypatch.setattr(
        onnx_module.OnnxEmbeddingProvider,
        "__init__",
        lambda self, model_name, threads: created.append(
            ("onnx", model_name, threads)
        ),
    )

    class FakeSentenceTransformer:
        def __init__(self, model_name, device=None):
            created.append(("sentence_transformers", model_name, device))

    monkeypatch.setattr(
        local_module,
        "SentenceTransformer",
        FakeSentenceTransformer,
    )

    for name in ("EMBEDDING_BACKEND", "EMBEDDING_THREADS", "MODEL_DEVICE"):
        monkeypatch.delenv(name, raising=False)

    def settings(**overrides):
        return Settings(
            _env_file=None,
            database_url="postgresql+psycopg://u:p@localhost/db",
            jwt_secret_key="secret",
            gemini_api_key="key",
            **overrides,
        )

    create_embedding_provider(settings())
    create_embedding_provider(
        settings(embedding_backend="onnx", embedding_threads=1)
    )

    assert created == [
        ("sentence_transformers", "BAAI/bge-small-en-v1.5", None),
        ("onnx", "BAAI/bge-small-en-v1.5", 1),
    ]


def test_importing_the_api_does_not_load_pytorch():
    """The Render image has no PyTorch, so the API must import without it."""

    code = (
        "import sys, busirag.api.main; "
        "heavy = [m for m in ('torch', 'sentence_transformers', "
        "'transformers', 'pymupdf') if m in sys.modules]; "
        "print(','.join(heavy))"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == ""


@pytest.mark.integration
def test_onnx_matches_sentence_transformers():
    """Downloads the model; run with: pytest -m integration."""

    from busirag.embeddings.local import LocalEmbeddingProvider

    texts = [
        "What was Apple's net income in 2023?",
        "Net income $ 96,995 $ 99,803 $ 94,680",
    ]

    onnx = np.array(OnnxEmbeddingProvider().embed_documents(texts))
    torch_based = np.array(
        LocalEmbeddingProvider(device="cpu").embed_documents(texts)
    )

    assert (onnx * torch_based).sum(axis=1).min() > 0.9999
