"""用户持久化查询与行锁仓储。by AI.Coding"""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, col, select

from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import UserFilters


class UserRepository:
    """封装用户查询，并将事务边界留给调用方。by AI.Coding"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(
        self, user_id: uuid.UUID, *, for_update: bool = False
    ) -> User | None:
        """按主键读取用户，并可在当前事务中锁定该行。by AI.Coding"""
        statement = select(User).where(User.id == user_id)
        if for_update:
            statement = statement.with_for_update()
        return self.session.exec(statement).one_or_none()

    def get_by_email(self, email: str) -> User | None:
        """按邮箱读取用户。by AI.Coding"""
        statement = select(User).where(User.email == email)
        return self.session.exec(statement).one_or_none()

    def list_users(self, filters: UserFilters) -> tuple[list[User], int]:
        """按管理端筛选条件返回稳定分页数据及筛选后总数。by AI.Coding"""
        conditions = self._build_filter_conditions(filters)
        count_statement = select(func.count()).select_from(User).where(*conditions)
        count = self.session.exec(count_statement).one()

        offset = (filters.page - 1) * filters.page_size
        statement = (
            select(User)
            .where(*conditions)
            .order_by(
                col(User.created_at).desc().nulls_last(),
                col(User.id).desc(),
            )
            .offset(offset)
            .limit(filters.page_size)
        )
        users = list(self.session.exec(statement).all())
        return users, count

    def list_active_agents(self) -> list[User]:
        """返回可作为工单负责人的全部活跃 Agent。by AI.Coding"""
        statement = (
            select(User)
            .where(
                User.role == UserRole.AGENT,
                col(User.is_active).is_(True),
            )
            .order_by(col(User.id))
        )
        return list(self.session.exec(statement).all())

    def lock_active_admins(self) -> list[User]:
        """按固定顺序锁定当前全部活跃 Admin。by AI.Coding"""
        statement = (
            select(User)
            .where(
                User.role == UserRole.ADMIN,
                col(User.is_active).is_(True),
            )
            .order_by(col(User.id))
            .with_for_update()
        )
        return list(self.session.exec(statement).all())

    def add(self, user: User) -> None:
        """将用户加入当前 Session，但不提交事务。by AI.Coding"""
        self.session.add(user)

    @staticmethod
    def _build_filter_conditions(
        filters: UserFilters,
    ) -> list[ColumnElement[bool]]:
        """构造供计数与分页查询共同使用的筛选谓词。by AI.Coding"""
        conditions: list[ColumnElement[bool]] = []
        if filters.role is not None:
            conditions.append(col(User.role) == filters.role)
        if filters.is_active is not None:
            conditions.append(col(User.is_active).is_(filters.is_active))
        if filters.query is not None:
            escaped_query = (
                filters.query.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            pattern = f"%{escaped_query}%"
            conditions.append(
                or_(
                    col(User.email).ilike(pattern, escape="\\"),
                    col(User.full_name).ilike(pattern, escape="\\"),
                )
            )
        return conditions
