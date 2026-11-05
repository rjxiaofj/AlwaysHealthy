"""指标质量状态回填到列

Revision ID: c4f8a1d6e2b9
Revises: a7d3e5c9f1b2
Create Date: 2026-11-05 13:12:41.118302
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4f8a1d6e2b9"
down_revision: Union[str, None] = "a7d3e5c9f1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

POSTGRES_BACKFILL = sa.text(
    """
    UPDATE health_metric_records
    SET quality_status = measurement_context ->> 'quality_status'
    WHERE source_type = 'wearable'
      AND quality_status = 'valid'
      AND measurement_context ->> 'quality_status' IS NOT NULL
    """
)

SQLITE_BACKFILL = sa.text(
    """
    UPDATE health_metric_records
    SET quality_status = json_extract(measurement_context, '$.quality_status')
    WHERE source_type = 'wearable'
      AND quality_status = 'valid'
      AND json_extract(measurement_context, '$.quality_status') IS NOT NULL
    """
)

POSTGRES_RESET = sa.text(
    """
    UPDATE health_metric_records
    SET quality_status = 'valid'
    WHERE source_type = 'wearable' AND quality_status <> 'valid'
    """
)

SQLITE_RESET = POSTGRES_RESET


def upgrade() -> None:
    # 设备读数原先只把质量状态写在 measurement_context 里，列一栏是默认值。
    # 回填后列成为唯一真相，过滤点不用再兼顾两份来源
    bind = op.get_bind()
    bind.execute(POSTGRES_BACKFILL if bind.dialect.name == "postgresql" else SQLITE_BACKFILL)


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(POSTGRES_RESET if bind.dialect.name == "postgresql" else SQLITE_RESET)
