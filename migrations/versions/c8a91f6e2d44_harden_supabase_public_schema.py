"""harden Supabase public schema for server-owned application data

Revision ID: c8a91f6e2d44
Revises: 8f2d31c4a9b7
Create Date: 2026-07-12

"""

from typing import Sequence, Union

from alembic import op

from app.postgres_security import install_postgresql_public_schema_security


revision: str = "c8a91f6e2d44"
down_revision: Union[str, Sequence[str], None] = "8f2d31c4a9b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        install_postgresql_public_schema_security(bind)


def downgrade() -> None:
    # Never automatically weaken database isolation or guess which historical
    # grants should be restored.  This is also intentionally a safe no-op on
    # SQLite, where the upgrade does not execute PostgreSQL DDL.
    pass
