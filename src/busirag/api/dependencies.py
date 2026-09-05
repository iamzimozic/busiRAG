from collections.abc import Generator

from fastapi import Request
from sqlalchemy.orm import Session

from busirag.db.session import SessionLocal
from busirag.rag.service import RAGService


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def get_rag_service(request: Request) -> RAGService:
    return request.app.state.rag_service