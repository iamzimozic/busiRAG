"""add tenants and document tenant

Revision ID: 3de9f208a709
Revises: 68e602c1a302
Create Date: 2026-09-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3de9f208a709"
down_revision: Union[str, Sequence[str], None] = "64cf882671cc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the tenants table first.
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # Create a tenant for the existing single-user data.
    op.execute(
        sa.text(
            "INSERT INTO tenants (name) VALUES (:name)"
        ).bindparams(name="default")
    )

    # Add the column as nullable temporarily so existing rows can be migrated.
    op.add_column(
        "documents",
        sa.Column("tenant_id", sa.Integer(), nullable=True),
    )

    # Assign every existing document to the default tenant.
    op.execute(
        sa.text(
            """
            UPDATE documents
            SET tenant_id = (
                SELECT id
                FROM tenants
                WHERE name = :name
            )
            """
        ).bindparams(name="default")
    )

    # Now that every existing document has a tenant, enforce the constraint.
    op.alter_column(
        "documents",
        "tenant_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.create_index(
        "ix_documents_tenant_id",
        "documents",
        ["tenant_id"],
    )

    op.create_foreign_key(
        "fk_documents_tenant_id",
        "documents",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_documents_tenant_id",
        "documents",
        type_="foreignkey",
    )

    op.drop_index(
        "ix_documents_tenant_id",
        table_name="documents",
    )

    op.drop_column(
        "documents",
        "tenant_id",
    )

    op.drop_table("tenants")