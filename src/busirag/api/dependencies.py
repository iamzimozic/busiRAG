from collections.abc import Generator

from fastapi import Request, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from busirag.auth.jwt import decode_access_token
from busirag.config import Settings
from busirag.db.models import User
from busirag.db.session import SessionLocal
from busirag.rag.service import RAGService

security = HTTPBearer()

def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def get_rag_service(request: Request) -> RAGService:
    return request.app.state.rag_service

def get_current_tenant_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_db),
) -> int:
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

    return user.tenant_id