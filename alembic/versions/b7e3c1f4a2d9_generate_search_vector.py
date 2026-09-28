"""generate search_vector from chunk text

The original full-text migration populated search_vector once for
existing rows, but ingestion never set it, so every chunk inserted
afterwards had a NULL vector and was invisible to sparse retrieval.
A generated column keeps it in sync with text on every insert/update.

Revision ID: b7e3c1f4a2d9
Revises: 945b2e8862ed
Create Date: 2026-09-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b7e3c1f4a2d9'
down_revision: Union[str, Sequence[str], None] = '945b2e8862ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(
        "ix_chunks_search_vector",
        table_name="chunks",
    )

    op.drop_column(
        "chunks",
        "search_vector",
    )

    op.add_column(
        "chunks",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('english', text)",
                persisted=True,
            ),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_chunks_search_vector",
        "chunks",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_chunks_search_vector",
        table_name="chunks",
    )

    op.drop_column(
        "chunks",
        "search_vector",
    )

    op.add_column(
        "chunks",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            nullable=True,
        ),
    )

    op.execute(
        """
        UPDATE chunks
        SET search_vector = to_tsvector(
            'english',
            text
        )
        """
    )

    op.create_index(
        "ix_chunks_search_vector",
        "chunks",
        ["search_vector"],
        postgresql_using="gin",
    )
