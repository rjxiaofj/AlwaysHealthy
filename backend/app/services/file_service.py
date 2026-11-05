import hashlib
import secrets
from datetime import datetime
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import FileRejected, InvalidHealthData, NotFound
from app.db.models import FileAsset, HealthMetricRecord
from app.repositories import chat as chat_repo
from app.services import document_parser
from app.tools.metrics import METRIC_DEFS

SOURCE_DOCUMENT = "document"

ALLOWED = {
    "pdf": ("application/pdf", b"%PDF"),
    "jpg": ("image/jpeg", b"\xff\xd8\xff"),
    "jpeg": ("image/jpeg", b"\xff\xd8\xff"),
    "png": ("image/png", b"\x89PNG\r\n\x1a\n"),
}


async def save_upload(session: AsyncSession, user_id: UUID, upload: UploadFile) -> FileAsset:
    settings = get_settings()
    suffix = Path(upload.filename or "").suffix.lower().lstrip(".")
    # 扩展名决定预期类型，实际类型以文件头为准，两者不一致直接拒绝
    if suffix not in ALLOWED:
        raise FileRejected("只允许上传 PDF、JPG、PNG 文件")
    expected_mime, signature = ALLOWED[suffix]

    content = await upload.read(settings.upload_max_bytes + 1)
    if len(content) > settings.upload_max_bytes:
        raise FileRejected(f"文件超过 {settings.upload_max_mb}MB 限制")
    if not content.startswith(signature):
        raise FileRejected("文件内容与扩展名不匹配")

    stored_name = f"{secrets.token_hex(16)}.{suffix}"
    directory = Path(settings.storage_dir) / "uploads" / str(user_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / stored_name
    path.write_bytes(content)

    asset = FileAsset(
        user_id=user_id,
        original_filename=Path(upload.filename or stored_name).name,
        stored_filename=stored_name,
        storage_path=str(path),
        mime_type=expected_mime,
        file_size=len(content),
        checksum=hashlib.sha256(content).hexdigest(),
        parse_status="pending",
    )
    session.add(asset)

    # 解析在落库前完成，用户看到的状态就是真实结果，不存在一直卡在 pending 的中间态
    outcome = document_parser.parse_document(path, expected_mime)
    asset.parse_status = outcome.status
    asset.parse_message = outcome.message
    asset.parsed_payload = {
        "fields": [
            {"metric_code": item.metric_code, "value": item.value, "raw": item.raw} for item in outcome.fields
        ]
    }

    await session.commit()
    return asset


async def resolve_download(session: AsyncSession, user_id: UUID, file_id: UUID) -> Path:
    asset = await chat_repo.file_of(session, user_id, file_id)
    if asset is None:
        raise NotFound("文件不存在")
    path = Path(asset.storage_path).resolve()
    root = (Path(get_settings().storage_dir) / "uploads").resolve()
    # 数据库路径被篡改时不能读到目录外的文件
    if root not in path.parents:
        raise NotFound("文件不存在")
    if not path.exists():
        raise NotFound("文件已被清理")
    return path


async def list_files(session: AsyncSession, user_id: UUID) -> list[dict]:
    rows = await chat_repo.files_of(session, user_id)
    return [
        {
            "id": row.id,
            "original_filename": row.original_filename,
            "mime_type": row.mime_type,
            "file_size": row.file_size,
            "parse_status": row.parse_status,
            "created_at": row.created_at,
        }
        for row in rows
    ]


async def get_extracted(session: AsyncSession, user_id: UUID, file_id: UUID) -> dict:
    asset = await chat_repo.file_of(session, user_id, file_id)
    if asset is None:
        raise NotFound("文件不存在")

    raw_fields = (asset.parsed_payload or {}).get("fields", [])
    fields = []
    for item in raw_fields:
        definition = METRIC_DEFS.get(item.get("metric_code"))
        if definition is None:
            continue
        fields.append(
            {
                "metric_code": item["metric_code"],
                "label": definition.label,
                "unit": definition.unit,
                "value": item["value"],
                "raw": item.get("raw", ""),
            }
        )

    return {
        "id": str(asset.id),
        "parse_status": asset.parse_status,
        "parse_message": asset.parse_message,
        "fields": fields,
    }


async def apply_extracted(
    session: AsyncSession,
    user_id: UUID,
    file_id: UUID,
    metric_codes: list[str],
) -> dict:
    asset = await chat_repo.file_of(session, user_id, file_id)
    if asset is None:
        raise NotFound("文件不存在")

    available = {
        item["metric_code"]: item["value"]
        for item in (asset.parsed_payload or {}).get("fields", [])
        if item.get("metric_code") in METRIC_DEFS
    }
    # 只认这份资料里真实识别到的编码，挡住借接口写任意指标的路径
    unknown = [code for code in metric_codes if code not in available]
    if unknown:
        raise InvalidHealthData(f"这份资料里没有这些指标：{'、'.join(unknown)}")

    measured_at = asset.created_at
    existing = set(
        await session.scalars(
            select(HealthMetricRecord.metric_code).where(
                HealthMetricRecord.user_id == user_id,
                HealthMetricRecord.source_type == SOURCE_DOCUMENT,
                HealthMetricRecord.measured_at == measured_at,
            )
        )
    )

    written = 0
    for code in metric_codes:
        if code in existing:
            continue
        session.add(
            HealthMetricRecord(
                user_id=user_id,
                metric_code=code,
                value=available[code],
                unit=METRIC_DEFS[code].unit,
                measured_at=measured_at,
                measurement_context={"file_id": str(asset.id)},
                source_type=SOURCE_DOCUMENT,
            )
        )
        existing.add(code)
        written += 1

    if written:
        await session.commit()
    return {"applied": written, "skipped": len(metric_codes) - written}
