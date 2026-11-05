from uuid import UUID

from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, db_session, request_id
from app.core.response import ok
from app.db.models import User
from app.repositories import chat as chat_repo
from app.schemas.health import ApplyExtractedIn, MedicalHistoryIn, ProfilePatch
from app.services import file_service, profile_service

router = APIRouter(tags=["profile"])


@router.get("/profiles/me")
async def get_profile(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    profile = await profile_service.get_profile(session, user.id)
    return ok(request, profile.model_dump(mode="json"))


@router.patch("/profiles/me")
async def patch_profile(
    request: Request,
    payload: ProfilePatch,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    await profile_service.patch_profile(session, user.id, payload)
    profile = await profile_service.get_profile(session, user.id)
    return ok(request, profile.model_dump(mode="json"))


@router.post("/profiles/me/histories")
async def add_history(
    request: Request,
    payload: MedicalHistoryIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    record = await profile_service.add_history(session, user.id, payload)
    return ok(request, {"id": str(record.id)})


@router.post("/profiles/me/documents")
async def upload_document(
    request: Request,
    file: UploadFile,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    asset = await file_service.save_upload(session, user.id, file)
    chat_repo.audit(
        session,
        actor_user_id=user.id,
        action="document_upload",
        resource_type="file_asset",
        resource_id=str(asset.id),
        result="success",
        request_id=request_id(request),
    )
    await session.commit()
    return ok(request, {"id": str(asset.id), "parse_status": asset.parse_status})


@router.get("/profiles/me/documents")
async def list_documents(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    return ok(request, await file_service.list_files(session, user.id))


@router.get("/profiles/me/documents/{file_id}/extracted")
async def get_document_extracted(
    file_id: UUID,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    return ok(request, await file_service.get_extracted(session, user.id, file_id))


@router.post("/profiles/me/documents/{file_id}/apply")
async def apply_document_extracted(
    file_id: UUID,
    payload: ApplyExtractedIn,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    result = await file_service.apply_extracted(session, user.id, file_id, payload.metric_codes)
    chat_repo.audit(
        session,
        actor_user_id=user.id,
        action="document_apply",
        resource_type="file_asset",
        resource_id=str(file_id),
        result="success",
        request_id=request_id(request),
    )
    await session.commit()
    return ok(request, result)


@router.get("/profiles/me/emergency-events")
async def emergency_events(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    rows = await chat_repo.emergency_events_of(session, user.id)
    return ok(
        request,
        [
            {
                "id": str(row.id),
                "triggered_at": row.triggered_at,
                "trigger_reason": row.trigger_reason,
                "matched_rules": row.matched_rules or [],
                "urgency": row.urgency,
                "response_status": row.response_status,
            }
            for row in rows
        ],
    )


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    path = await file_service.resolve_download(session, user.id, file_id)
    return FileResponse(path)
