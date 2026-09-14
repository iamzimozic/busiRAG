from datetime import datetime, timedelta, timezone

import jwt

from busirag.config import Settings


def create_access_token(
    user_id: int,
    tenant_id: int,
    settings: Settings,
    expires_minutes: int = 60,
) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "tenant_id": tenant_id,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(
    token: str,
    settings: Settings,
) -> dict:
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )