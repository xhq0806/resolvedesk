from fastapi import APIRouter

from app.api.routes import (
    ai,
    attachments,
    knowledge,
    login,
    private,
    tickets,
    users,
    utils,
    workspaces,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(tickets.router)
api_router.include_router(utils.router)
api_router.include_router(workspaces.router)
api_router.include_router(ai.router)
api_router.include_router(ai.conversation_router)
api_router.include_router(knowledge.router)
api_router.include_router(attachments.router)


if settings.FASTAPI_ENV == "development":
    api_router.include_router(private.router)
