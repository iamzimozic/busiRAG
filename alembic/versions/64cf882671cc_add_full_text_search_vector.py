"""add full text search vector

Revision ID: 64cf882671cc
Revises: 1c38ba154912
Create Date: 2026-09-03 20:15:47.909602

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '64cf882671cc'
down_revision: Union[str, Sequence[str], None] = '1c38ba154912'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_index(
        "ix_chunks_search_vector",
        table_name="chunks",
    )

    op.drop_column(
        "chunks",
        "search_vector",
    )
