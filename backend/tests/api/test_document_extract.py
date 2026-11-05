import io
import uuid

from pypdf import PdfWriter
from sqlalchemy import select

from app.db.models import FileAsset, HealthMetricRecord, User


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


async def test_upload_records_real_parse_state(client, auth) -> None:
    data = await upload(client, auth)
    assert data["parse_status"] == "unsupported"

    listed = await client.get("/api/v1/profiles/me/documents", headers=auth)
    item = listed.json()["data"][0]
    assert item["parse_status"] == "unsupported"


async def test_extracted_of_blank_pdf_is_empty(client, auth) -> None:
    data = await upload(client, auth)
    response = await client.get(f"/api/v1/profiles/me/documents/{data['id']}/extracted", headers=auth)
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["fields"] == []
    assert "文字层" in body["parse_message"]


async def test_extracted_requires_ownership(client, auth) -> None:
    data = await upload(client, auth)

    other = await client.post("/api/v1/auth/register", json={"username": f"x{uuid.uuid4().hex[:8]}", "password": "demo12345"})
    other_headers = {"Authorization": f"Bearer {other.json()['data']['access_token']}"}

    response = await client.get(f"/api/v1/profiles/me/documents/{data['id']}/extracted", headers=other_headers)
    assert response.status_code == 404

    applied = await client.post(
        f"/api/v1/profiles/me/documents/{data['id']}/apply",
        json={"metric_codes": ["systolic_bp"]},
        headers=other_headers,
    )
    assert applied.status_code == 404


async def test_apply_rejects_code_not_in_payload(client, auth, session) -> None:
    data = await upload(client, auth)
    file_id = uuid.UUID(data["id"])

    response = await client.post(
        f"/api/v1/profiles/me/documents/{file_id}/apply",
        json={"metric_codes": ["hba1c"]},
        headers=auth,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_HEALTH_DATA"


async def test_apply_writes_metrics_and_is_idempotent(client, auth, session) -> None:
    data = await upload(client, auth)
    file_id = uuid.UUID(data["id"])

    asset = await session.get(FileAsset, file_id)
    asset.parsed_payload = {
        "fields": [
            {"metric_code": "systolic_bp", "value": 148.0, "raw": "收缩压 148"},
            {"metric_code": "diastolic_bp", "value": 96.0, "raw": "舒张压 96"},
        ]
    }
    await session.commit()

    body = {"metric_codes": ["systolic_bp", "diastolic_bp"]}
    first = await client.post(f"/api/v1/profiles/me/documents/{file_id}/apply", json=body, headers=auth)
    assert first.status_code == 200
    assert first.json()["data"] == {"applied": 2, "skipped": 0}

    second = await client.post(f"/api/v1/profiles/me/documents/{file_id}/apply", json=body, headers=auth)
    assert second.json()["data"] == {"applied": 0, "skipped": 2}

    rows = await session.scalars(
        select(HealthMetricRecord).where(HealthMetricRecord.source_type == "document")
    )
    records = list(rows)
    assert len(records) == 2
    assert {item.metric_code for item in records} == {"systolic_bp", "diastolic_bp"}
    assert records[0].measurement_context["file_id"] == str(file_id)


async def test_upload_records_admission_status(client, auth, session) -> None:
    data = await upload(client, auth)
    asset = await session.get(FileAsset, uuid.UUID(data["id"]))
    assert asset is not None
    assert asset.admission_status == "passed"


async def test_upload_with_fake_signature_is_rejected(client, auth, session) -> None:
    files = {"file": ("report.pdf", b"not a real pdf", "application/pdf")}
    response = await client.post("/api/v1/profiles/me/documents", files=files, headers=auth)
    assert response.status_code == 400
    assert response.json()["code"] == "FILE_REJECTED"

    user_id = await session.scalar(select(User.id).where(User.username == auth["username"]))
    rows = await session.scalars(select(FileAsset).where(FileAsset.user_id == user_id))
    assert list(rows) == []
