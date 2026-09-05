from typing import Protocol


class EmbeddingProvider(Protocol):
    """Interface implemented by all embedding providers."""

    @property
    def dimension(self) -> int:
        """Return the dimensionality of the embedding vectors."""
        ...

    def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """Embed multiple documents."""
        ...

    def embed_query(
        self,
        text: str,
    ) -> list[float]:
        """Embed a search query."""
        ...