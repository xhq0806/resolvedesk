from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app.core.config import settings
from app.core.db import engine, init_db
from app.main import app
from app.models.ai import (
    AiAgent,
    AiConversation,
    AiMessage,
    AiProviderConfig,
    AiRun,
    AiRunEvent,
    AiToolPermission,
)
from app.models.attachment import Attachment
from app.models.knowledge import DocumentIngestionJob, KnowledgeChunk, KnowledgeDocument
from app.models.ticket import Ticket, TicketAuditLog, TicketMessage
from app.models.user import User
from app.models.workspace import (
    Workspace,
    WorkspaceInvitation,
    WorkspaceMember,
    WorkspaceRole,
)
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers


def _default_workspace(session: Session) -> Workspace:
    """读取测试库中的默认 Workspace。by AI.Coding"""
    workspace = session.exec(select(Workspace).where(Workspace.slug == "default")).one()
    return workspace


def _ensure_default_workspace_member(
    session: Session, user: User, role: WorkspaceRole
) -> Workspace:
    """确保测试登录用户具备默认 Workspace 成员身份。by AI.Coding"""
    workspace = _default_workspace(session)
    member = session.exec(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == user.id,
        )
    ).first()
    if member is None:
        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role=role,
        )
    else:
        member.role = role
    session.add(member)
    session.commit()
    return workspace


def _with_workspace_header(headers: dict[str, str], workspace: Workspace) -> dict[str, str]:
    """为需要租户上下文的 API 测试补充 Workspace 请求头。by AI.Coding"""
    return {**headers, "X-Workspace-ID": str(workspace.id)}


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session]:
    """提供应用数据库会话并按 RESTRICT 外键顺序清理数据。by AI.Coding"""
    with Session(engine) as session:
        init_db(session)
        yield session
        # 先删除子表和工单，再删除被历史记录引用的用户。
        # 按外键依赖从叶子实体向根实体清理新增租户数据。by AI.Coding
        for model in (
            AiRunEvent,
            AiRun,
            AiMessage,
            Attachment,
            AiConversation,
            KnowledgeChunk,
            DocumentIngestionJob,
            KnowledgeDocument,
            TicketAuditLog,
            TicketMessage,
            Ticket,
            AiToolPermission,
            AiProviderConfig,
            AiAgent,
            WorkspaceInvitation,
            WorkspaceMember,
            Workspace,
            User,
        ):
            session.execute(delete(model))
        session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).one()
    workspace = _ensure_default_workspace_member(db, user, WorkspaceRole.OWNER)
    return _with_workspace_header(get_superuser_token_headers(client), workspace)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    headers = authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )
    user = db.exec(select(User).where(User.email == settings.EMAIL_TEST_USER)).one()
    workspace = _ensure_default_workspace_member(db, user, WorkspaceRole.CUSTOMER)
    return _with_workspace_header(headers, workspace)
