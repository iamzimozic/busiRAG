from datetime import datetime
from pydantic import BaseModel, Field, field_validator



class QueryRequest(BaseModel):
    query: str = Field(min_length=1)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be empty")

        return value


class SourceResponse(BaseModel):
    citation_id: str
    company: str
    filename: str
    year: int
    page_number: int | None
    chunk_id: int
    section: str | None = None
    element_type: str | None = None
    text: str | None = None
    retrieval_score: float | None = None
    rerank_score: float | None = None


class RetrievedChunkResponse(BaseModel):
    citation_id: str
    chunk_id: int
    company: str
    filename: str
    year: int
    page_number: int | None
    element_type: str
    retrieval_score: float | None
    rerank_score: float | None
    cited: bool


class TimingsResponse(BaseModel):
    retrieval_ms: float
    generation_ms: float
    total_ms: float


class DiagnosticsResponse(BaseModel):
    request_id: str
    cache_hit: bool
    retrieval_mode: str
    generation_model: str | None
    timings: TimingsResponse
    retrieved: list[RetrievedChunkResponse]


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceResponse]
    diagnostics: DiagnosticsResponse | None = None

class DocumentResponse(BaseModel):
    id: int
    company: str
    year: int
    filename: str

class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)


class RegisterResponse(BaseModel):
    id: int
    email: str
    tenant_id: int


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class WorkspaceResponse(BaseModel):
    id: int
    name: str
    created_at: datetime

class UserResponse(BaseModel):
    id: int
    email: str
    tenant_id: int
    created_at: datetime