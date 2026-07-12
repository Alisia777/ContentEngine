"""durable recipe input artifacts

Revision ID: 5b7130c8f42e
Revises: 24aaca5b4358
Create Date: 2026-07-12

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5b7130c8f42e"
down_revision: Union[str, Sequence[str], None] = "24aaca5b4358"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("product_assets", schema=None) as batch_op:
        batch_op.add_column(sa.Column("media_artifact_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            "ix_product_assets_media_artifact_id",
            ["media_artifact_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_product_assets_media_artifact",
            "media_artifacts",
            ["media_artifact_id"],
            ["id"],
        )

    with op.batch_alter_table("product_ugc_recipe_drafts", schema=None) as batch_op:
        batch_op.alter_column(
            "character_image_path",
            existing_type=sa.String(length=1000),
            nullable=True,
        )
        batch_op.add_column(
            sa.Column("character_media_artifact_id", sa.Integer(), nullable=True)
        )
        batch_op.create_index(
            "ix_product_ugc_recipe_drafts_character_media_artifact_id",
            ["character_media_artifact_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_ugc_drafts_character_artifact",
            "media_artifacts",
            ["character_media_artifact_id"],
            ["id"],
        )


def downgrade() -> None:
    # The legacy column is NOT NULL.  Preserve a fail-closed marker instead of
    # inventing a local path or leaking an object capability during rollback.
    op.execute(
        sa.text(
            "UPDATE product_ugc_recipe_drafts "
            "SET character_image_path = 'durable-input-unavailable-after-downgrade' "
            "WHERE character_image_path IS NULL"
        )
    )
    with op.batch_alter_table("product_ugc_recipe_drafts", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_ugc_drafts_character_artifact",
            type_="foreignkey",
        )
        batch_op.drop_index(
            "ix_product_ugc_recipe_drafts_character_media_artifact_id"
        )
        batch_op.drop_column("character_media_artifact_id")
        batch_op.alter_column(
            "character_image_path",
            existing_type=sa.String(length=1000),
            nullable=False,
        )

    with op.batch_alter_table("product_assets", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_product_assets_media_artifact",
            type_="foreignkey",
        )
        batch_op.drop_index("ix_product_assets_media_artifact_id")
        batch_op.drop_column("media_artifact_id")
