"""文件下载端点的归属与路径边界。

`/profiles/me/documents/{id}/extracted` 的越权已有 test_document_extract.py 守着，
但 `/files/{id}/download` 直接返回磁盘文件，是读文件那条路里最该验的：归属过滤漏了
就是任意用户能下别人的体检单，storage_path 被篡改还能读目录外的文件。
"""
import io
import uuid
from pathlib import Path

from pypdf import PdfWriter

from app.db.models import FileAsset


def blank_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


async def upload(client, headers) -> dict:
    files = {"file": ("report.pdf", blank_pdf(), "application/pdf")}
    response = await client.post("/api/v1/profiles/me/documents", files=files, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def other_user(client) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={"username": f"dl{uuid.uuid4().hex[:8]}", "password": "demo12345"},
    )
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


async def test_owner_can_download(client, auth) -> None:
    data = await upload(client, auth)

    response = await client.get(f"/api/v1/files/{data['id']}/download", headers=auth)

    assert response.status_code == 200, response.text
    assert response.content.startswith(b"%PDF")


async def test_other_user_cannot_download(client, auth) -> None:
    data = await upload(client, auth)
    other = await other_user(client)

    response = await client.get(f"/api/v1/files/{data['id']}/download", headers=other)

    assert response.status_code == 404


async def test_download_requires_login(client, auth) -> None:
    data = await upload(client, auth)

    response = await client.get(f"/api/v1/files/{data['id']}/download")

    assert response.status_code == 401


async def test_tampered_storage_path_cannot_escape_uploads(client, auth, session) -> None:
    data = await upload(client, auth)
    asset = await session.get(FileAsset, uuid.UUID(data["id"]))
    # 指向一个真实存在的越界文件。用不存在的文件会假绿：即便去掉目录边界检查，
    # 也会被后面的 path.exists() 挡住，测不到防护本身
    outside = Path(__file__).resolve().parents[2] / "app" / "main.py"
    assert outside.exists()
    asset.storage_path = str(outside)
    await session.commit()

    response = await client.get(f"/api/v1/files/{data['id']}/download", headers=auth)

    assert response.status_code == 404


async def test_missing_file_returns_404(client, auth, session) -> None:
    data = await upload(client, auth)
    asset = await session.get(FileAsset, uuid.UUID(data["id"]))
    # 保留真实路径前缀，只把文件名换掉：这样能穿过目录边界检查，
    # 真正命中 resolve_download 里的 path.exists() 分支
    asset.storage_path = str(Path(asset.storage_path).with_name("this-file-was-deleted.pdf"))
    await session.commit()

    response = await client.get(f"/api/v1/files/{data['id']}/download", headers=auth)

    assert response.status_code == 404
