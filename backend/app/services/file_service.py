import hashlib
import secrets
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import FileRejected, NotFound
from app.db.models import FileAsset
from app.repositories import chat as chat_repo

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
