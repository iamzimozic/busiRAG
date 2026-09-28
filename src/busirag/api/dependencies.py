from collections.abc import Generator

from fastapi import Request, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from busirag.api.rate_limit import RateLimiter
from busirag.auth.jwt import decode_access_token
from busirag.config import Settings
from busirag.db.models import User
from busirag.db.session import SessionLocal
from busirag.errors import FeatureDisabledError
from busirag.rag.service import RAGService

security = HTTPBearer()

def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def get_rag_service(request: Request) -> RAGService:
    return request.app.state.rag_service


def get_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)

    return settings if settings is not None else Settings()


def get_rate_limiter(request: Request) -> RateLimiter | None:
    return getattr(request.app.state, "rate_limiter", None)


def require_writable_workspace(
    settings: Settings = Depends(get_settings),
) -> None:
    """Block account and document changes on a public read-only demo."""

    if settings.demo_mode:
        raise FeatureDisabledError(
            "This action is disabled in the public demo."
        )

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