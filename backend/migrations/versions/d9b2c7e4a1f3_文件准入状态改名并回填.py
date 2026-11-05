"""文件准入状态改名并回填

Revision ID: d9b2c7e4a1f3
Revises: c4f8a1d6e2b9
Create Date: 2026-11-05 13:18:52.664071
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d9b2c7e4a1f3"
down_revision: Union[str, None] = "c4f8a1d6e2b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 列原先叫扫毒状态，实际做的是扩展名、大小与文件头准入。当初一律写 skipped，
    # 看起来像没检查过。改名后语义是准入校验，历史行同样通过过校验，一并回填
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column("file_assets", "scan_status", new_column_name="admission_status")
        op.alter_column("file_assets", "admission_status", server_default="passed")
    else:
        with op.batch_alter_table("file_assets", schema=None) as batch_op:
            batch_op.alter_column("scan_status", new_column_name="admission_status", server_default="passed")
    op.execute(sa.text("UPDATE file_assets SET admission_status = 'passed' WHERE admission_status = 'skipped'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE file_assets SET admission_status = 'skipped' WHERE admission_status = 'passed'"))
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column("file_assets", "admission_status", server_default="skipped")
        op.alter_column("file_assets", "admission_status", new_column_name="scan_status")
    else:
        with op.batch_alter_table("file_assets", schema=None) as batch_op:
            batch_op.alter_column("admission_status", new_column_name="scan_status", server_default="skipped")
