from busirag.cache import Cache
from busirag.config import Settings
from busirag.embeddings import EmbeddingProvider
from busirag.generation.factory import create_llm_provider, llm_identity
from busirag.generation.service import GenerationService
from busirag.rag.service import RAGService
from busirag.versioning import CHUNKING_VERSION, EMBEDDING_MODEL


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Embedding provider for EMBEDDING_BACKEND (models load lazily)."""

    if settings.embedding_backend == "onnx":
        from busirag.embeddings.onnx import OnnxEmbeddingProvider

        return OnnxEmbeddingProvider(
            model_name=settings.embedding_model,
            threads=settings.embedding_threads,
        )

    from busirag.embeddings.local import LocalEmbeddingProvider

    return LocalEmbeddingProvider(
        model_name=settings.embedding_model,
        device=settings.model_device,
    )


def build_rag_service(
    settings: Settings,
    cache: Cache | None,
    embedding_provider: EmbeddingProvider | None = None,
    generation_budget=None,
) -> RAGService:
    """
    Build the RAG service from settings.

    Used by the API and by scripts that must share its cache keys
    (e.g. scripts/warm_cache.py), so both derive retrieval and model
    configuration from the same place.
    """

    if embedding_provider is None:
        embedding_provider = create_embedding_provider(settings)

    # Only hybrid_rerank uses the cross-encoder (and PyTorch); skipping
    # it saves memory and startup time on small CPU hosts.
    reranker = None

    if settings.retrieval_mode == "hybrid_rerank":
        from busirag.reranking.local import LocalReranker

        reranker = LocalReranker(
            model_name=settings.reranker_model,
            device=settings.model_device,
        )

    return RAGService(
        embedding_provider=embedding_provider,
        reranker=reranker,
        generation_service=GenerationService(
            create_llm_provider(settings)
        ),
        cache=cache,
        chunking_version=CHUNKING_VERSION,
        embedding_model=EMBEDDING_MODEL,
        candidate_k=settings.candidate_k,
        top_k=settings.top_k,
        cache_ttl=settings.cache_ttl,
        retrieval_mode=settings.retrieval_mode,
        generation_model=llm_identity(settings),
        generation_budget=generation_budget,
    )
