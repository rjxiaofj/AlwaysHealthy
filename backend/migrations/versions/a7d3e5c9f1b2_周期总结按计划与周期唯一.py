"""周期总结按计划与周期唯一

Revision ID: a7d3e5c9f1b2
Revises: 1a2e2622add0
Create Date: 2026-11-05 12:26:11.402815
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a7d3e5c9f1b2"
down_revision: Union[str, None] = "1a2e2622add0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 一个计划的一个周期只留一份总结，重复生成走已有记录，并发双击也不会写出两行
    with op.batch_alter_table("tracking_summaries", schema=None) as batch_op:
        batch_op.create_unique_constraint("uq_summary_per_plan_period", ["plan_id", "period_end"])


def downgrade() -> None:
    with op.batch_alter_table("tracking_summaries", schema=None) as batch_op:
        batch_op.drop_constraint("uq_summary_per_plan_period", type_="unique")
