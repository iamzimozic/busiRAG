from busirag.reranking.base import Reranker

__all__ = ["LocalReranker", "Reranker"]


def __getattr__(name: str):
    # Imported lazily: LocalReranker loads PyTorch via sentence-transformers.
    if name == "LocalReranker":
        from busirag.reranking.local import LocalReranker

        return LocalReranker

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
