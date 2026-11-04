from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, db_session
from app.core.exceptions import NotFound
from app.core.response import ok
from app.core.sse import SSEEventMapper
from app.db.models import User
from app.repositories import chat as chat_repo
from app.schemas.chat import ConversationIn, MessageIn, ResumeIn
from app.services import conversation_service

router = APIRouter(tags=["conversation"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.post("/conversations")
async def create_conversation(
    request: Request,
    payload: ConversationIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    conversation = await conversation_service.create(session, user.id, payload.title)
    return ok(request, {"id": str(conversation.id), "thread_id": conversation.thread_id})


@router.get("/conversations")
async def list_conversations(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    return ok(request, await conversation_service.list_conversations(session, user.id))


@router.get("/conversations/{conversation_id}")
async def conversation_detail(
    conversation_id: UUID,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    conversation = await conversation_service.get_conversation(session, user.id, conversation_id)
    runs = await chat_repo.runs_of_conversation(session, conversation.id)
    return ok(
        request,
        {
            "id": str(conversation.id),
            "title": conversation.title,
            "status": conversation.status,
            "runs": [
                {
                    "id": str(run.id),
                    "status": run.status,
                    "started_at": run.started_at,
                    "meta": run.meta,
                }
                for run in runs[:5]
            ],
        },
    )


@router.get("/conversations/{conversation_id}/messages")
async def messages(
    conversation_id: UUID,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    return ok(request, await conversation_service.messages(session, user.id, conversation_id))


@router.post("/conversations/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: UUID,
    payload: MessageIn,
    request: Request,
    user: User = Depends(current_user),
):
    graph_service = request.app.state.graph_service

    async def event_stream():
        yield SSEEventMapper.heartbeat()
        async for event, data in graph_service.start_run(user.id, conversation_id, payload.content):
            yield SSEEventMapper.format(event, data)

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.get("/runs/{run_id}")
async def run_detail(
    run_id: UUID,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    run = await chat_repo.run_of(session, user.id, run_id)
    if run is None:
        raise NotFound("运行记录不存在")
    return ok(
        request,
        {
            "id": str(run.id),
            "status": run.status,
            "run_type": run.run_type,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "error_code": run.error_code,
            "meta": run.meta,
        },
    )


@router.post("/runs/{run_id}/resume/stream")
async def resume_run(
    run_id: UUID,
    payload: ResumeIn,
    request: Request,
    user: User = Depends(current_user),
):
    graph_service = request.app.state.graph_service

    async def event_stream():
        yield SSEEventMapper.heartbeat()
        async for event, data in graph_service.resume_run(user.id, run_id, payload):
            yield SSEEventMapper.format(event, data)

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=SSE_HEADERS)
