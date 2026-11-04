from fastapi import APIRouter

from app.api.v1.endpoints import (
    assessments,
    auth,
    conversations,
    health,
    plans,
    profiles,
    reminders,
    reports,
    tracking,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(profiles.router)
api_router.include_router(conversations.router)
api_router.include_router(assessments.router)
api_router.include_router(plans.router)
api_router.include_router(tracking.router)
api_router.include_router(reports.router)
api_router.include_router(reminders.router)

health_router = APIRouter()
health_router.include_router(health.router)
