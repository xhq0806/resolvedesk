"""用户仓储筛选、分页和 PostgreSQL 行锁测试。by AI.Coding"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, text
from sqlalchemy.exc import DBAPIError
from sqlmodel import Session

from app.core.db import engine
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserFilters


def make_user(
    marker: str,
    *,
    role: UserRole = UserRole.CUSTOMER,
    is_active: bool = True,
    full_name: str | None = None,
    created_at: datetime | None = None,
    user_id: uuid.UUID | None = None,
) -> User:
    """构造具有唯一邮箱的仓储测试用户。by AI.Coding"""
    return User(
        id=user_id or uuid.uuid4(),
        email=f"{marker}-{uuid.uuid4().hex}@example.com",
        role=role,
        is_active=is_active,
        full_name=full_name,
        hashed_password="not-a-real-password-hash",
        created_at=created_at or datetime.now(UTC),
    )


@pytest.fixture
def persisted_users() -> Iterator[list[User]]:
    """持久化测试用户，并在单例结束后按主键清理。by AI.Coding"""
    users: list[User] = []
    yield users
    if not users:
        return
    with Session(engine) as cleanup_session:
        cleanup_session.exec(delete(User).where(User.id.in_([user.id for user in users])))
        cleanup_session.commit()


def persist(users: list[User], tracked_users: list[User]) -> None:
    """提交测试数据并登记清理范围。by AI.Coding"""
    with Session(engine, expire_on_commit=False) as session:
        session.add_all(users)
        session.commit()
    tracked_users.extend(users)


def test_user_filters_normalize_query_and_validate_pagination() -> None:
    filters = UserFilters(query="  Agent Smith  ")
    assert filters.query == "Agent Smith"
    assert UserFilters(query="   ").query is None

    for invalid_filters in (
        {"page": 0},
        {"page_size": 0},
        {"page_size": 101},
    ):
        with pytest.raises(ValidationError):
            UserFilters.model_validate(invalid_filters)


def test_getters_and_add_use_the_callers_session(
    persisted_users: list[User],
) -> None:
    user = make_user("repository-getters")

    with Session(engine) as session:
        repository = UserRepository(session)
        repository.add(user)
        assert user in session.new
        session.commit()
        persisted_users.append(user)

        assert repository.get_by_id(user.id) is user
        assert repository.get_by_email(str(user.email)) is user
        assert repository.get_by_id(uuid.uuid4()) is None
        assert repository.get_by_email("missing@example.com") is None


def test_list_users_combines_filters_count_and_stable_pagination(
    persisted_users: list[User],
) -> None:
    marker = f"users-{uuid.uuid4().hex}"
    base_time = datetime(2026, 8, 26, 12, tzinfo=UTC)
    users = [
        make_user(
            marker,
            user_id=uuid.UUID(int=index + 1),
            role=UserRole.AGENT if index != 3 else UserRole.CUSTOMER,
            is_active=index != 2,
            full_name=f"{marker} Agent {index}",
            created_at=base_time if index < 3 else base_time - timedelta(days=index),
        )
        for index in range(5)
    ]
    persist(users, persisted_users)

    with Session(engine) as session:
        repository = UserRepository(session)
        first_page, count = repository.list_users(
            UserFilters(query=marker.upper(), page=1, page_size=2)
        )
        second_page, second_count = repository.list_users(
            UserFilters(query=marker, page=2, page_size=2)
        )
        active_agents, active_agent_count = repository.list_users(
            UserFilters(
                role=UserRole.AGENT,
                is_active=True,
                query=marker,
                page_size=100,
            )
        )
        inactive_users, inactive_count = repository.list_users(
            UserFilters(is_active=False, query=marker)
        )

    assert count == second_count == 5
    assert [user.id for user in first_page] == [uuid.UUID(int=3), uuid.UUID(int=2)]
    assert [user.id for user in second_page] == [uuid.UUID(int=1), uuid.UUID(int=4)]
    assert active_agent_count == 3
    assert {user.id for user in active_agents} == {
        uuid.UUID(int=1),
        uuid.UUID(int=2),
        uuid.UUID(int=5),
    }
    assert inactive_count == 1
    assert [user.id for user in inactive_users] == [uuid.UUID(int=3)]


def test_list_users_matches_email_and_full_name_with_literal_like_characters(
    persisted_users: list[User],
) -> None:
    marker = uuid.uuid4().hex
    email_match = make_user(f"emailmatch-{marker}", full_name="ordinary")
    name_match = make_user(
        f"ordinary-{marker}", full_name=f"Literal 100%_match {marker}"
    )
    wildcard_only = make_user(
        f"wildcard-{marker}", full_name=f"Literal 100XXmatch {marker}"
    )
    persist([email_match, name_match, wildcard_only], persisted_users)

    with Session(engine) as session:
        repository = UserRepository(session)
        by_email, email_count = repository.list_users(
            UserFilters(query=f"EMAILMATCH-{marker.upper()}")
        )
        by_literal_name, literal_count = repository.list_users(
            UserFilters(query=f"100%_match {marker}")
        )

    assert email_count == 1
    assert [user.id for user in by_email] == [email_match.id]
    assert literal_count == 1
    assert [user.id for user in by_literal_name] == [name_match.id]


def test_list_active_agents_returns_only_active_agents_in_id_order(
    persisted_users: list[User],
) -> None:
    active_high = make_user(
        "active-agent-high", role=UserRole.AGENT, user_id=uuid.UUID(int=102)
    )
    active_low = make_user(
        "active-agent-low", role=UserRole.AGENT, user_id=uuid.UUID(int=101)
    )
    inactive_agent = make_user(
        "inactive-agent", role=UserRole.AGENT, is_active=False
    )
    active_admin = make_user("active-admin", role=UserRole.ADMIN)
    active_customer = make_user("active-customer")
    users = [
        active_high,
        active_low,
        inactive_agent,
        active_admin,
        active_customer,
    ]
    persist(users, persisted_users)

    with Session(engine) as session:
        result = UserRepository(session).list_active_agents()

    result_ids = [user.id for user in result]
    assert result_ids == sorted(result_ids)
    assert active_low.id in result_ids
    assert active_high.id in result_ids
    assert inactive_agent.id not in result_ids
    assert active_admin.id not in result_ids
    assert active_customer.id not in result_ids


def test_lock_active_admins_returns_only_active_admins_in_id_order(
    persisted_users: list[User],
) -> None:
    active_high = make_user(
        "locked-admin-high", role=UserRole.ADMIN, user_id=uuid.UUID(int=202)
    )
    active_low = make_user(
        "locked-admin-low", role=UserRole.ADMIN, user_id=uuid.UUID(int=201)
    )
    inactive_admin = make_user(
        "unlocked-inactive-admin", role=UserRole.ADMIN, is_active=False
    )
    active_agent = make_user("unlocked-agent", role=UserRole.AGENT)
    users = [active_high, active_low, inactive_admin, active_agent]
    persist(users, persisted_users)

    with Session(engine) as session:
        result = UserRepository(session).lock_active_admins()
        result_ids = [user.id for user in result]
        session.rollback()

    assert result_ids == sorted(result_ids)
    assert active_low.id in result_ids
    assert active_high.id in result_ids
    assert inactive_admin.id not in result_ids
    assert active_agent.id not in result_ids


def test_active_admin_lock_blocks_an_independent_session_until_transaction_ends(
    persisted_users: list[User],
) -> None:
    admin = make_user("blocking-admin", role=UserRole.ADMIN)
    persist([admin], persisted_users)

    with Session(engine) as locking_session, Session(engine) as competing_session:
        UserRepository(locking_session).lock_active_admins()

        competing_session.exec(text("SET LOCAL lock_timeout = '100ms'"))
        with pytest.raises(DBAPIError):
            UserRepository(competing_session).get_by_id(admin.id, for_update=True)
        competing_session.rollback()

        locking_session.rollback()

        locked_after_release = UserRepository(competing_session).get_by_id(
            admin.id, for_update=True
        )
        assert locked_after_release is not None
        competing_session.rollback()
