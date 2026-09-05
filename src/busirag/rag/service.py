from sqlalchemy.orm import Session

import uuid
import time
from busirag.embeddings import EmbeddingProvider
from busirag.generation.service import GenerationService
from busirag.reranking import LocalReranker
from busirag.retrieval.reranked import retrieve_reranked_chunks
from busirag.generation.response import RAGResponse
from busirag.errors import InvalidQueryError
from busirag.cache import Cache
from busirag.cache.keys import build_query_cache_key
from busirag.cache.serialization import (
    deserialize_rag_response,
    serialize_rag_response,
)
from busirag.observability.logger import (
    log_query_metrics,
)
from busirag.observability.models import (
    QueryMetrics,
)
from busirag.observability.metrics import (
    record_query,
    record_query_error,
)

class RAGService:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        reranker: LocalReranker,
        generation_service: GenerationService,
        cache: Cache | None = None,
        chunking_version: str | None = None,
        embedding_model: str | None = None,
        candidate_k: int = 50,
        top_k: int = 10,
        cache_ttl: int = 3600,
    ):
        self.embedding_provider = embedding_provider
        self.reranker = reranker
        self.generation_service = generation_service
        self.cache = cache
        self.chunking_version = chunking_version
        self.embedding_model = embedding_model
        self.candidate_k = candidate_k
        self.top_k = top_k
        self.cache_ttl = cache_ttl

    def query(
        self,
        session: Session,
        query: str,
        request_id: str | None = None,
    ) -> RAGResponse:
        if not query.strip():
            raise InvalidQueryError("query must not be empty")

        total_start = time.perf_counter()

        if request_id is None:
            request_id = str(uuid.uuid4())

        cache_key = build_query_cache_key(
            query=query,
            chunking_version=self.chunking_version,
            embedding_model=self.embedding_model,
            candidate_k=self.candidate_k,
            top_k=self.top_k,
        )

        #cache lookup goes here
        if self.cache is not None:
            cached_value = self.cache.get(cache_key)

            if cached_value is not None:
                result = deserialize_rag_response(cached_value)

                total_ms = (
                    time.perf_counter() - total_start
                ) * 1000

                log_query_metrics(
                    metrics=QueryMetrics(
                        request_id=request_id,
                        cache_hit=True,
                        retrieval_ms=0,
                        generation_ms=0,
                        total_ms=total_ms,
                        source_count=len(result.sources),
                    ),
                )

                record_query(
                    cache_hit=True,
                    retrieval_ms=0.0,
                    generation_ms=0.0,
                    total_ms=total_ms,
                )

                return result
        try:
            retrieval_start = time.perf_counter()

            retrieval_results = retrieve_reranked_chunks(
                session=session,
                query=query,
                embedding_provider=self.embedding_provider,
                reranker=self.reranker,
                top_k=self.top_k,
                candidate_k=self.candidate_k,
                chunking_version=self.chunking_version,
                embedding_model=self.embedding_model,
            )

            retrieval_ms = (
                time.perf_counter() - retrieval_start
            ) * 1000

            generation_start = time.perf_counter()

            result = self.generation_service.generate(
                query=query,
                retrieval_results=retrieval_results,
            )

            generation_ms = (
                time.perf_counter() - generation_start
            ) * 1000

            #cache store goes here
            if self.cache is not None:
                self.cache.set(
                    key=cache_key,
                    value=serialize_rag_response(result),
                    ttl=self.cache_ttl,
                )

            total_ms = (
                time.perf_counter() - total_start
            ) * 1000

            log_query_metrics(
                metrics=QueryMetrics(
                    request_id=request_id,
                    cache_hit=False,
                    retrieval_ms=retrieval_ms,
                    generation_ms=generation_ms,
                    total_ms=total_ms,
                    source_count=len(result.sources),
                ),
            )

            record_query(
                cache_hit=False,
                retrieval_ms=retrieval_ms,
                generation_ms=generation_ms,
                total_ms=total_ms,
            )

            return result

        except Exception:
            record_query_error()
            raise