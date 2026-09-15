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
    year: int
    page_number: int | None
    chunk_id: int


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceResponse]

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