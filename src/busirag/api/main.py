import uuid
from pathlib import Path
from uuid import uuid4
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials

from sqlalchemy import select
from sqlalchemy.orm import Session

from busirag.api.dependencies import (
    get_current_tenant_id,
    get_db,
    get_rag_service,
    security,
)
from busirag.config import Settings
from busirag.cache import RedisCache
from busirag.api.schemas import (
    DocumentResponse,
    LoginRequest,
    QueryRequest,
    QueryResponse,
    RegisterRequest,
    RegisterResponse,
    SourceResponse,
    TokenResponse,
    UserResponse,
    WorkspaceResponse,
)
from busirag.auth.jwt import create_access_token, decode_access_token
from busirag.auth.passwords import hash_password, verify_password
from busirag.db.models import Document, Tenant, User
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
from busirag.ingestion import ingest_document
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

    app.state.embedding_provider = embedding_provider

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get(
    "/auth/me",
    response_model=UserResponse,
)
def get_current_user(
    session: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserResponse:
    settings = Settings()

    try:
        payload = decode_access_token(
            credentials.credentials,
            settings,
        )
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )

    user_id = payload.get("sub")

    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
        )

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
        )

    user = session.scalar(
        select(User).where(User.id == user_id)
    )

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User not found",
        )

    return UserResponse(
        id=user.id,
        email=user.email,
        tenant_id=user.tenant_id,
        created_at=user.created_at,
    )

@app.post(
    "/auth/register",
    response_model=RegisterResponse,
    status_code=201,
)
def register(
    payload: RegisterRequest,
    session: Session = Depends(get_db),
) -> RegisterResponse:
    existing_user = session.scalar(
        select(User).where(User.email == payload.email)
    )

    if existing_user is not None:
        raise HTTPException(
            status_code=409,
            detail="Email already registered",
        )

    tenant = Tenant(
        name=payload.email,
    )
    session.add(tenant)
    session.flush()

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        tenant_id=tenant.id,
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    return RegisterResponse(
        id=user.id,
        email=user.email,
        tenant_id=user.tenant_id,
    )

@app.post(
    "/auth/login",
    response_model=TokenResponse,
)
def login(
    payload: LoginRequest,
    session: Session = Depends(get_db),
) -> TokenResponse:
    user = session.scalar(
        select(User).where(User.email == payload.email)
    )

    if user is None or not verify_password(
        payload.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    settings = Settings()

    access_token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        settings=settings,
    )

    return TokenResponse(
        access_token=access_token,
    )

@app.get(
    "/documents",
    response_model=list[DocumentResponse],
)
def list_documents(
    session: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> list[DocumentResponse]:
    documents = session.scalars(
        select(Document)
        .where(Document.tenant_id == tenant_id)
        .order_by(Document.created_at.desc())
    ).all()

    return [
        DocumentResponse(
            id=document.id,
            company=document.company,
            year=document.year,
            filename=document.filename,
        )
        for document in documents
    ]

@app.post(
    "/documents",
    status_code=201,
)
def upload_document(
    file: UploadFile = File(...),
    company: str = Form(...),
    year: int = Form(...),
    session: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> dict[str, object]:
    if not file.filename:
        raise ValueError("filename is required")

    extension = Path(file.filename).suffix.lower()

    if extension not in {".pdf", ".docx"}:
        raise ValueError("only PDF and DOCX files are supported")

    company = company.strip()

    if not company:
        raise ValueError("company must not be empty")

    upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_filename = f"{uuid4().hex}{extension}"
    destination = upload_dir / safe_filename

    with destination.open("wb") as output:
        while chunk := file.file.read(1024 * 1024):
            output.write(chunk)

    try:
        chunk_count = ingest_document(
            path=destination,
            company=company,
            year=year,
            embedding_provider=app.state.embedding_provider,
            tenant_id=tenant_id,
        )
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    return {
        "message": "Document uploaded successfully",
        "filename": file.filename,
        "company": company,
        "year": year,
        "chunks": chunk_count,
    }

from fastapi import HTTPException

@app.delete(
    "/documents/{document_id}",
    status_code=204,
)
def delete_document(
    document_id: int,
    session: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> None:
    document = session.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
        )
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    source_path = Path(document.source_path)

    session.delete(document)
    session.commit()

    source_path.unlink(missing_ok=True)

@app.get(
    "/workspace",
    response_model=WorkspaceResponse,
)
def get_workspace(
    session: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> WorkspaceResponse:
    tenant = session.scalar(
        select(Tenant).where(Tenant.id == tenant_id)
    )

    if tenant is None:
        raise HTTPException(
            status_code=404,
            detail="Workspace not found",
        )

    return WorkspaceResponse(
        id=tenant.id,
        name=tenant.name,
        created_at=tenant.created_at,
    )

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
    tenant_id: int = Depends(get_current_tenant_id),
    rag_service: RAGService = Depends(get_rag_service),
) -> QueryResponse:
    result = rag_service.query(
        session=session,
        query=request.query,
        tenant_id=tenant_id,
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