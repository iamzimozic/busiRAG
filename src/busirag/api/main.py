import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from sqlalchemy.orm import Session

from busirag.api.dependencies import get_db, get_rag_service
from busirag.config import Settings
from busirag.cache import RedisCache
from busirag.api.schemas import QueryRequest, QueryResponse, SourceResponse
from busirag.embeddings.local import LocalEmbeddingProvider
from busirag.generation.gemini import GeminiProvider
from busirag.generation.service import GenerationService
from busirag.rag.service import RAGService
from busirag.reranking.local import LocalReranker
from busirag.config.validation import validate_embedding_configuration
from busirag.errors import (
    BusiragError,
    GenerationError,
    InvalidQueryError,
    RetrievalError,
)
from busirag.versioning import CHUNKING_VERSION, EMBEDDING_MODEL

from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

import logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    validate_embedding_configuration(settings.embedding_model)

    cache = RedisCache(settings.redis_url)

    embedding_provider = LocalEmbeddingProvider(
        model_name=settings.embedding_model,
    )

    reranker = LocalReranker(
        model_name=settings.reranker_model,
    )

    llm = GeminiProvider(
        model=settings.gemini_model,
        api_key=settings.gemini_api_key,
    )

    generation_service = GenerationService(llm)

    app.state.rag_service = RAGService(
        embedding_provider=embedding_provider,
        reranker=reranker,
        generation_service=generation_service,
        cache=cache,
        chunking_version=CHUNKING_VERSION,
        embedding_model=EMBEDDING_MODEL,
        candidate_k=settings.candidate_k,
        top_k=settings.top_k,
        cache_ttl=settings.cache_ttl,
    )

    yield

    # Resources that require explicit cleanup can be
    # released here later.

logging.basicConfig(
    level=logging.INFO,
)

app = FastAPI(
    title="Busirag",
    description="Financial and Business Intelligence RAG API",
    version="0.1.0",
    lifespan=lifespan,
)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/metrics")
def metrics() -> Response:
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())

    request.state.request_id = request_id

    response = await call_next(request)

    response.headers["X-Request-ID"] = request_id

    return response

@app.exception_handler(InvalidQueryError)
async def invalid_query_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={
            "error": "invalid_query",
            "message": str(exc),
        },
    )

@app.exception_handler(RetrievalError)
async def retrieval_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "error": "retrieval_error",
            "message": "Failed to retrieve relevant sources.",
        },
    )

@app.exception_handler(GenerationError)
async def generation_error_handler(request, exc):
    return JSONResponse(
        status_code=502,
        content={
            "error": "generation_error",
            "message": "Failed to generate an answer.",
        },
    )

@app.exception_handler(BusiragError)
async def busirag_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "error": "application_error",
            "message": "An application error occurred.",
        },
    )

@app.post("/query", response_model=QueryResponse)
def query(
    request: QueryRequest,
    http_request: Request,
    session: Session = Depends(get_db),
    rag_service: RAGService = Depends(get_rag_service),
) -> QueryResponse:
    result = rag_service.query(
        session=session,
        query=request.query,
        request_id=http_request.state.request_id,
    )

    return QueryResponse(
        answer=result.answer,
        sources=[
            SourceResponse(
                citation_id=source.citation_id,
                company=source.company,
                year=source.year,
                page_number=source.page_number,
                chunk_id=source.chunk_id,
            )
            for source in result.sources
        ],
    )