"""用户角色管理、事务与并发不变量服务。by AI.Coding"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.core.errors import (
    AppError,
    ConflictError,
    ErrorCode,
    ForbiddenError,
    NotFoundError,
)
from app.core.security import get_password_hash
from app.models.enums import UserRole
from app.models.user import User
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

    def create_user(self, actor: User, payload: UserCreateAdmin) -> UserPublic:
        """由 Admin 创建指定角色和启用状态的用户。by AI.Coding"""
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
    ) -> UserPublic:
        """由 Admin 更新用户，并保护最后一名活跃 Admin。by AI.Coding"""
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
