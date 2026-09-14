"""add users

Revision ID: 945b2e8862ed
Revises: 3de9f208a709
Create Date: 2026-09-14 22:59:52.875557

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '945b2e8862ed'
down_revision: Union[str, Sequence[str], None] = '3de9f208a709'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_users_email"),
        "users",
        ["email"],
        unique=True,
    )

    op.create_index(
        op.f("ix_users_tenant_id"),
        "users",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_users_tenant_id"),
        table_name="users",
    )

    op.drop_index(
        op.f("ix_users_email"),
        table_name="users",
    )

    op.drop_table("users")
