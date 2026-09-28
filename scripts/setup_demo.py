"""
Set up the public demo workspace.

1. Creates (or reuses) a demo workspace and a demo user.
2. Ingests every PDF/DOCX under <root>/<company>/<year>/ into it.

Run it from your machine against the deployed database; ingestion
(PDF parsing + embeddings) then uses your local CPU/GPU instead of the
small demo host:

    DATABASE_URL=postgresql+psycopg://...  \
    DEMO_PASSWORD='a-long-random-password' \
    python scripts/setup_demo.py

Re-running is safe: the user is reused and already-ingested files are
skipped. The demo password is not a secret in the usual sense (the
frontend's "Try the demo" button embeds it); run the API with
DEMO_MODE=true so the account is read-only.
"""

import argparse
import os
from pathlib import Path

from sqlalchemy import select

from busirag.auth.passwords import hash_password, verify_password
from busirag.db.models import Tenant, User
from busirag.db.session import SessionLocal
from busirag.embeddings import LocalEmbeddingProvider

from ingest_corpus import ingest_directory


def ensure_demo_user(
    email: str,
    password: str,
    workspace_name: str,
) -> int:
    """Return the demo user's tenant id, creating user/workspace if needed."""

    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.email == email))

        if user is not None:
            if not verify_password(password, user.password_hash):
                user.password_hash = hash_password(password)
                session.commit()
                print(f"Updated password for {email}")

            print(f"Using existing demo user {email} (tenant {user.tenant_id})")
            return user.tenant_id

        tenant = session.scalar(
            select(Tenant).where(Tenant.name == workspace_name)
        )

        if tenant is None:
            tenant = Tenant(name=workspace_name)
            session.add(tenant)
            session.flush()

        user = User(
            email=email,
            password_hash=hash_password(password),
            tenant_id=tenant.id,
        )
        session.add(user)
        session.commit()

        print(f"Created demo user {email} (tenant {tenant.id})")
        return tenant.id


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--root", type=Path, default=Path("data/raw"))
    parser.add_argument(
        "--email",
        default=os.getenv("DEMO_EMAIL", "demo@busirag.app"),
    )
    parser.add_argument(
        "--workspace",
        default="BusiRAG demo",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Only create the demo user.",
    )

    args = parser.parse_args()

    password = os.getenv("DEMO_PASSWORD")

    if not password or len(password) < 8:
        raise SystemExit(
            "Set DEMO_PASSWORD (at least 8 characters) in the environment."
        )

    tenant_id = ensure_demo_user(
        email=args.email,
        password=password,
        workspace_name=args.workspace,
    )

    if not args.skip_ingest:
        ingest_directory(
            data_root=args.root,
            tenant_id=tenant_id,
            provider=LocalEmbeddingProvider(),
        )

    print()
    print(f"Demo login: {args.email}")
    print(
        "Set VITE_DEMO_EMAIL and VITE_DEMO_PASSWORD on the frontend "
        "to show a 'Try the demo' button."
    )


if __name__ == "__main__":
    main()
