"""文件解析结果字段

Revision ID: 1a2e2622add0
Revises: ebfa31c139b9
Create Date: 2026-11-05 09:19:24.964630
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "1a2e2622add0"
down_revision: Union[str, None] = "ebfa31c139b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("file_assets", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "parsed_payload",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("parse_message", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("file_assets", schema=None) as batch_op:
        batch_op.drop_column("parse_message")
        batch_op.drop_column("parsed_payload")
