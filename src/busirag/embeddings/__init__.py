from busirag.embeddings.base import EmbeddingProvider

__all__ = [
    "EmbeddingProvider",
    "LocalEmbeddingProvider",
    "OnnxEmbeddingProvider",
]


def __getattr__(name: str):
    # Providers are imported lazily so that importing the package (as
    # the API does) does not load PyTorch unless a provider that needs
    # it is actually used. The ONNX provider runs without PyTorch.
    if name == "LocalEmbeddingProvider":
        from busirag.embeddings.local import LocalEmbeddingProvider

        return LocalEmbeddingProvider

    if name == "OnnxEmbeddingProvider":
        from busirag.embeddings.onnx import OnnxEmbeddingProvider

        return OnnxEmbeddingProvider

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
