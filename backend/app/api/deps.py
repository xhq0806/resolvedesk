import uuid
from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session, select

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.core.errors import ErrorCode, NotFoundError
from app.core.workspace import WorkspaceContext, build_workspace_context
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.schemas.auth import TokenPayload

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


def get_db() -> Generator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无法验证登录凭据",
        )
    user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="用户已停用")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_workspace_context(
    session: SessionDep,
    current_user: CurrentUser,
    current_workspace_id: Annotated[
        uuid.UUID | None, Header(alias="X-Workspace-ID")
    ] = None,
) -> WorkspaceContext:
    """按请求头解析当前 Workspace 并校验成员关系。by AI.Coding"""
    if current_workspace_id is None:
        raise NotFoundError(ErrorCode.WORKSPACE_REQUIRED)
    workspace = session.get(Workspace, current_workspace_id)
    member = session.exec(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == current_workspace_id,
            WorkspaceMember.user_id == current_user.id,
        )
    ).first()
    return build_workspace_context(workspace, member)


WorkspaceContextDep = Annotated[WorkspaceContext, Depends(get_workspace_context)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    """迁移期沿用旧依赖名称，并通过单角色模型识别 Admin。by AI.Coding"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="用户权限不足")
    return current_user
