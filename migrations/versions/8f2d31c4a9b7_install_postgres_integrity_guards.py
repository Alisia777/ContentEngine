"""install PostgreSQL integrity guards at a forward revision

Revision ID: 8f2d31c4a9b7
Revises: 5b7130c8f42e
Create Date: 2026-07-12

"""

from typing import Sequence, Union

from alembic import op

from app.postgres_integrity import install_postgresql_integrity_guards


revision: str = "8f2d31c4a9b7"
down_revision: Union[str, Sequence[str], None] = "5b7130c8f42e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        install_postgresql_integrity_guards(bind)


def downgrade() -> None:
    # Revision 24aaca5b4358 already defines these guards for a fresh database.
    # This forward revision repairs databases stamped by an earlier copy of
    # that migration, so downgrading it must preserve the 5b schema contract.
    pass
