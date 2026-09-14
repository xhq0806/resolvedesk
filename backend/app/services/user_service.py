"""用户角色管理、事务与并发不变量服务。by AI.Coding"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import settings
from app.core.errors import (
    AppError,
    ConflictError,
    ErrorCode,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.core.security import get_password_hash
from app.core.workspace import WorkspaceContext
from app.models.enums import UserRole
from app.models.user import User
from app.models.workspace import MembershipStatus, WorkspaceMember, WorkspaceRole
from app.repositories.user_repository import UserRepository
from app.schemas.user import (
    UserCreateAdmin,
    UserFilters,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdateAdmin,
    UserUpdateMe,
)

AVATAR_MIMES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


class AvatarUpload(Protocol):
    """头像上传对象所需的最小异步读取接口。by AI.Coding"""

    filename: str | None
    content_type: str | None

    async def read(self, size: int = -1) -> bytes:
        """读取上传图片字节。by AI.Coding"""
        ...


def validate_avatar_bytes(
    filename: str | None,
    content_type: str | None,
    content: bytes,
) -> tuple[str, str]:
    """校验头像扩展名、MIME、大小和图片文件签名。by AI.Coding"""
    if not filename or Path(filename).name != filename:
        raise ValidationError(ErrorCode.VALIDATION_ERROR)
    extension = Path(filename).suffix.lower()
    expected_mime = AVATAR_MIMES.get(extension)
    if (
        expected_mime is None
        or not content
        or len(content) > settings.AVATAR_MAX_FILE_BYTES
    ):
        raise ValidationError(ErrorCode.VALIDATION_ERROR)
    supplied_mime = (content_type or "").split(";", 1)[0].strip().lower()
    if supplied_mime and supplied_mime != expected_mime:
        raise ValidationError(ErrorCode.VALIDATION_ERROR)
    if extension == ".png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValidationError(ErrorCode.VALIDATION_ERROR)
    if extension in {".jpg", ".jpeg"} and not content.startswith(b"\xff\xd8\xff"):
        raise ValidationError(ErrorCode.VALIDATION_ERROR)
    if extension == ".webp" and not (
        len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    ):
        raise ValidationError(ErrorCode.VALIDATION_ERROR)
    return extension, expected_mime


class UserService:
    """封装三角色用户管理及其数据库事务边界。by AI.Coding"""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = UserRepository(session)

    def register_customer(self, payload: UserRegister) -> UserPublic:
        """公开注册固定创建活跃 Customer。by AI.Coding"""

        def operation() -> User:
            self._ensure_email_available(str(payload.email))
            user = User(
                email=payload.email,
                full_name=payload.full_name,
                role=UserRole.CUSTOMER,
                is_active=True,
                hashed_password=get_password_hash(payload.password),
            )
            self.repository.add(user)
            return user

        return self._write(operation)

    def create_user(
        self,
        actor: User,
        payload: UserCreateAdmin,
        *,
        context: WorkspaceContext | None = None,
    ) -> UserPublic:
        """由 Admin 创建用户，并在当前 Workspace 建立成员关系。by AI.Coding"""
        self._require_admin(actor)

        def operation() -> User:
            self._ensure_email_available(str(payload.email))
            user = User(
                email=payload.email,
                full_name=payload.full_name,
                role=payload.role,
                is_active=payload.is_active,
                hashed_password=get_password_hash(payload.password),
            )
            self.repository.add(user)
            if context is not None:
                # User 与 WorkspaceMember 必须同事务提交，避免新账号登录后没有可访问租户。by AI.Coding
                self.session.flush()
                self.session.add(
                    WorkspaceMember(
                        workspace_id=context.workspace_id,
                        user_id=user.id,
                        role=self._workspace_role(payload.role),
                        status=(
                            MembershipStatus.ACTIVE
                            if payload.is_active
                            else MembershipStatus.REMOVED
                        ),
                    )
                )
            return user

        return self._write(operation)

    def list_users(self, actor: User, filters: UserFilters) -> UsersPublic:
        """由 Admin 查询筛选后的用户分页。by AI.Coding"""
        self._require_admin(actor)
        users, count = self.repository.list_users(filters)
        return UsersPublic(
            data=[UserPublic.model_validate(user) for user in users],
            count=count,
        )

    def update_user(
        self,
        actor: User,
        user_id: uuid.UUID,
        payload: UserUpdateAdmin,
        *,
        context: WorkspaceContext | None = None,
    ) -> UserPublic:
        """由 Admin 更新用户、成员角色并保护最后一名活跃 Admin。by AI.Coding"""
        self._require_admin(actor)

        def operation() -> User:
            active_admins = self.repository.lock_active_admins()
            target = next((user for user in active_admins if user.id == user_id), None)
            if target is None:
                target = self.repository.get_by_id(user_id, for_update=True)
            if target is None:
                raise NotFoundError(ErrorCode.USER_NOT_FOUND)

            changes = payload.model_dump(exclude_unset=True)
            next_role = changes.get("role", target.role)
            next_is_active = changes.get("is_active", target.is_active)
            removes_active_admin = (
                target.role is UserRole.ADMIN
                and target.is_active
                and not (next_role is UserRole.ADMIN and next_is_active is True)
            )
            if removes_active_admin and len(active_admins) <= 1:
                raise ConflictError(ErrorCode.LAST_ACTIVE_ADMIN)

            email = changes.get("email")
            if email is not None:
                self._ensure_email_available(str(email), current_user_id=target.id)

            password = changes.pop("password", None)
            extra_data = (
                {"hashed_password": get_password_hash(password)}
                if password is not None
                else {}
            )
            target.sqlmodel_update(changes, update=extra_data)
            self.repository.add(target)
            if context is not None:
                # 管理端修改全局角色时同步当前 Workspace，避免导航角色和租户角色分裂。by AI.Coding
                self._sync_workspace_member(context, target.id, next_role, next_is_active)
            return target

        return self._write(operation)

    def update_me(self, actor: User, payload: UserUpdateMe) -> UserPublic:
        """更新当前用户的邮箱和姓名，不改变权限相关字段。by AI.Coding"""

        def operation() -> User:
            changes = payload.model_dump(exclude_unset=True)
            email = changes.get("email")
            if email is not None:
                self._ensure_email_available(str(email), current_user_id=actor.id)
            actor.sqlmodel_update(changes)
            self.repository.add(actor)
            return actor

        return self._write(operation)

    async def upload_avatar(self, actor: User, upload: AvatarUpload) -> UserPublic:
        """校验并保存当前用户头像，返回带新读取地址的用户资料。by AI.Coding"""
        filename = upload.filename or ""
        content = await upload.read(settings.AVATAR_MAX_FILE_BYTES + 1)
        extension, _mime_type = validate_avatar_bytes(
            filename,
            upload.content_type,
            content,
        )
        path = self._avatar_path(actor.id, extension)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._delete_avatar_files(actor.id)
        path.write_bytes(content)
        actor.avatar_url = (
            f"{settings.API_V1_STR}/users/{actor.id}/avatar"
            f"?version={uuid.uuid4().hex}"
        )
        self.repository.add(actor)
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            path.unlink(missing_ok=True)
            raise
        self.session.refresh(actor)
        return UserPublic.model_validate(actor)

    def delete_avatar(self, actor: User) -> UserPublic:
        """删除当前用户本地头像并清空公开头像地址。by AI.Coding"""
        self._delete_avatar_files(actor.id)
        actor.avatar_url = None
        self.repository.add(actor)
        self.session.commit()
        self.session.refresh(actor)
        return UserPublic.model_validate(actor)

    def get_avatar_content(self, user_id: uuid.UUID) -> tuple[Path, str]:
        """返回公开头像文件路径和 MIME，供浏览器图片标签直接读取。by AI.Coding"""
        user = self.repository.get_by_id(user_id)
        if user is None or not user.avatar_url:
            raise NotFoundError(ErrorCode.USER_NOT_FOUND)
        for extension, mime_type in AVATAR_MIMES.items():
            path = self._avatar_path(user_id, extension)
            if path.is_file():
                return path, mime_type
        raise NotFoundError(ErrorCode.USER_NOT_FOUND)

    def _write(self, operation: Callable[[], User]) -> UserPublic:
        """执行单次用户写事务并统一翻译数据库冲突。by AI.Coding"""
        try:
            user = operation()
            self.session.flush()
            self.session.commit()
            self.session.refresh(user)
            return UserPublic.model_validate(user)
        except AppError:
            self.session.rollback()
            raise
        except IntegrityError as error:
            self.session.rollback()
            if self._is_email_unique_violation(error):
                raise ConflictError(ErrorCode.EMAIL_CONFLICT) from error
            raise
        except Exception:
            self.session.rollback()
            raise

    def _ensure_email_available(
        self,
        email: str,
        *,
        current_user_id: uuid.UUID | None = None,
    ) -> None:
        """拒绝被其他用户占用的邮箱。by AI.Coding"""
        existing_user = self.repository.get_by_email(email)
        if existing_user is not None and existing_user.id != current_user_id:
            raise ConflictError(ErrorCode.EMAIL_CONFLICT)

    @staticmethod
    def _require_admin(actor: User) -> None:
        """限制用户管理能力仅对 Admin 开放。by AI.Coding"""
        if actor.role is not UserRole.ADMIN:
            raise ForbiddenError(ErrorCode.ROLE_FORBIDDEN)

    @staticmethod
    def _workspace_role(role: UserRole) -> WorkspaceRole:
        """将兼容期全局角色映射为 Workspace 成员角色。by AI.Coding"""
        return WorkspaceRole(role.value)

    def _sync_workspace_member(
        self,
        context: WorkspaceContext,
        user_id: uuid.UUID,
        role: UserRole,
        is_active: bool,
    ) -> None:
        """确保当前 Workspace 始终存在与用户账号一致的成员记录。by AI.Coding"""
        member = self.session.exec(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == context.workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        ).first()
        if member is None:
            member = WorkspaceMember(
                workspace_id=context.workspace_id,
                user_id=user_id,
                role=self._workspace_role(role),
                status=(
                    MembershipStatus.ACTIVE
                    if is_active
                    else MembershipStatus.REMOVED
                ),
            )
        else:
            member.role = self._workspace_role(role)
            member.status = (
                MembershipStatus.ACTIVE
                if is_active
                else MembershipStatus.REMOVED
            )
        self.session.add(member)

    @staticmethod
    def _is_email_unique_violation(error: IntegrityError) -> bool:
        """仅识别 PostgreSQL 用户邮箱唯一约束冲突。by AI.Coding"""
        original = error.orig
        sqlstate = getattr(original, "sqlstate", None) or getattr(
            original, "pgcode", None
        )
        diagnostic = getattr(original, "diag", None)
        constraint_name = getattr(diagnostic, "constraint_name", None)
        return sqlstate == "23505" and bool(
            constraint_name and "email" in constraint_name.lower()
        )

    @staticmethod
    def _avatar_path(user_id: uuid.UUID, extension: str) -> Path:
        """解析头像本地文件路径并阻断路径穿越。by AI.Coding"""
        root = settings.AVATAR_STORAGE_DIR.resolve()
        path = (root / f"{user_id}{extension}").resolve()
        if root not in path.parents:
            raise ValueError("非法头像路径")
        return path

    def _delete_avatar_files(self, user_id: uuid.UUID) -> None:
        """删除同一用户所有允许格式的历史头像文件。by AI.Coding"""
        for extension in AVATAR_MIMES:
            self._avatar_path(user_id, extension).unlink(missing_ok=True)
