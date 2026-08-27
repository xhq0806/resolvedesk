"""三角色用户服务、事务与最后 Admin 并发测试。by AI.Coding"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import delete, update
from sqlmodel import Session, select

from app.core.db import engine
from app.core.errors import ConflictError, ErrorCode, ForbiddenError, NotFoundError
from app.core.security import verify_password
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import (
    UserCreateAdmin,
    UserFilters,
    UserRegister,
    UserUpdateAdmin,
    UserUpdateMe,
)
from app.services.user_service import UserService


def make_user(
    marker: str,
    *,
    role: UserRole = UserRole.CUSTOMER,
    is_active: bool = True,
    full_name: str | None = None,
) -> User:
    """构造具有唯一邮箱的服务测试用户。by AI.Coding"""
    return User(
        email=f"{marker}-{uuid.uuid4().hex}@example.com",
        role=role,
        is_active=is_active,
        full_name=full_name,
        hashed_password="not-a-real-password-hash",
    )


@pytest.fixture
def tracked_user_ids() -> Iterator[list[uuid.UUID]]:
    """登记并清理服务测试创建的用户。by AI.Coding"""
    user_ids: list[uuid.UUID] = []
    yield user_ids
    if not user_ids:
        return
    with Session(engine) as session:
        session.exec(delete(User).where(User.id.in_(user_ids)))
        session.commit()


def persist(user: User, tracked_user_ids: list[uuid.UUID]) -> User:
    """持久化用户并登记清理主键。by AI.Coding"""
    with Session(engine, expire_on_commit=False) as session:
        session.add(user)
        session.commit()
    tracked_user_ids.append(user.id)
    return user


def test_register_customer_forces_active_customer_and_hashes_password(
    tracked_user_ids: list[uuid.UUID],
) -> None:
    email = f"register-{uuid.uuid4().hex}@example.com"
    password = "valid-password"

    with Session(engine) as session:
        result = UserService(session).register_customer(
            UserRegister(email=email, password=password, full_name="New Customer")
        )
        tracked_user_ids.append(result.id)

    assert result.role is UserRole.CUSTOMER
    assert result.is_active is True
    with Session(engine) as session:
        saved = session.get(User, result.id)
        assert saved is not None
        verified, _ = verify_password(password, saved.hashed_password)
        assert verified is True


def test_register_customer_rejects_existing_email_and_rolls_back(
    tracked_user_ids: list[uuid.UUID],
) -> None:
    existing = persist(make_user("duplicate-register"), tracked_user_ids)

    with Session(engine) as session:
        with pytest.raises(ConflictError) as error:
            UserService(session).register_customer(
                UserRegister(email=existing.email, password="valid-password")
            )
        assert error.value.code is ErrorCode.EMAIL_CONFLICT
        assert session.in_transaction() is False


def test_concurrent_registration_maps_unique_violation_to_email_conflict(
    monkeypatch: pytest.MonkeyPatch,
    tracked_user_ids: list[uuid.UUID],
) -> None:
    email = f"concurrent-register-{uuid.uuid4().hex}@example.com"
    precheck_barrier = threading.Barrier(2)
    original_get_by_email = UserRepository.get_by_email

    def synchronized_get_by_email(
        repository: UserRepository, candidate_email: str
    ) -> User | None:
        existing = original_get_by_email(repository, candidate_email)
        if candidate_email == email:
            precheck_barrier.wait(timeout=5)
        return existing

    monkeypatch.setattr(UserRepository, "get_by_email", synchronized_get_by_email)

    def register() -> tuple[uuid.UUID | None, ErrorCode | None]:
        with Session(engine) as session:
            try:
                result = UserService(session).register_customer(
                    UserRegister(email=email, password="valid-password")
                )
            except ConflictError as error:
                return None, error.code
            return result.id, None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [
            future.result(timeout=5)
            for future in (executor.submit(register), executor.submit(register))
        ]

    created_ids = [user_id for user_id, error in results if error is None]
    errors = [error for user_id, error in results if user_id is None]
    assert len(created_ids) == 1
    assert errors == [ErrorCode.EMAIL_CONFLICT]
    tracked_user_ids.extend(created_ids)

    with Session(engine) as session:
        matching_users = session.exec(select(User).where(User.email == email)).all()
        assert len(matching_users) == 1


def test_admin_can_create_all_roles(
    tracked_user_ids: list[uuid.UUID],
) -> None:
    actor = make_user("admin-actor", role=UserRole.ADMIN)

    for role in UserRole:
        with Session(engine) as session:
            result = UserService(session).create_user(
                actor,
                UserCreateAdmin(
                    email=f"created-{role.value.lower()}-{uuid.uuid4().hex}@example.com",
                    password="valid-password",
                    role=role,
                    is_active=role is not UserRole.AGENT,
                ),
            )
            tracked_user_ids.append(result.id)
        assert result.role is role
        assert result.is_active is (role is not UserRole.AGENT)


@pytest.mark.parametrize("role", [UserRole.CUSTOMER, UserRole.AGENT])
def test_non_admin_cannot_manage_users(role: UserRole) -> None:
    actor = make_user("forbidden-actor", role=role)

    with Session(engine) as session:
        service = UserService(session)
        with pytest.raises(ForbiddenError) as create_error:
            service.create_user(
                actor,
                UserCreateAdmin(
                    email=f"forbidden-{uuid.uuid4().hex}@example.com",
                    password="valid-password",
                ),
            )
        with pytest.raises(ForbiddenError) as list_error:
            service.list_users(actor, UserFilters())
        with pytest.raises(ForbiddenError) as update_error:
            service.update_user(actor, uuid.uuid4(), UserUpdateAdmin(is_active=False))

    assert create_error.value.code is ErrorCode.ROLE_FORBIDDEN
    assert list_error.value.code is ErrorCode.ROLE_FORBIDDEN
    assert update_error.value.code is ErrorCode.ROLE_FORBIDDEN


def test_list_users_maps_repository_results_with_roles(
    tracked_user_ids: list[uuid.UUID],
) -> None:
    marker = uuid.uuid4().hex
    agent = persist(
        make_user(f"list-agent-{marker}", role=UserRole.AGENT, full_name=marker),
        tracked_user_ids,
    )
    actor = make_user("list-admin", role=UserRole.ADMIN)

    with Session(engine) as session:
        result = UserService(session).list_users(
            actor,
            UserFilters(role=UserRole.AGENT, query=marker),
        )

    assert result.count == 1
    assert result.data[0].id == agent.id
    assert result.data[0].role is UserRole.AGENT


@pytest.mark.parametrize("role", list(UserRole))
def test_update_me_changes_only_profile_fields(
    role: UserRole,
    tracked_user_ids: list[uuid.UUID],
) -> None:
    actor = persist(make_user("update-me", role=role), tracked_user_ids)
    original_hash = actor.hashed_password
    new_email = f"updated-me-{uuid.uuid4().hex}@example.com"

    with Session(engine) as session:
        attached_actor = session.get(User, actor.id)
        assert attached_actor is not None
        result = UserService(session).update_me(
            attached_actor,
            UserUpdateMe(email=new_email, full_name="Updated Name"),
        )

    assert str(result.email) == new_email
    assert result.full_name == "Updated Name"
    assert result.role is role
    with Session(engine) as session:
        saved = session.get(User, actor.id)
        assert saved is not None
        assert saved.role is role
        assert saved.is_active is True
        assert saved.hashed_password == original_hash


def test_admin_updates_role_status_profile_and_password(
    tracked_user_ids: list[uuid.UUID],
) -> None:
    actor = make_user("update-admin-actor", role=UserRole.ADMIN)
    target = persist(make_user("update-target"), tracked_user_ids)
    new_email = f"updated-target-{uuid.uuid4().hex}@example.com"

    with Session(engine) as session:
        result = UserService(session).update_user(
            actor,
            target.id,
            UserUpdateAdmin(
                email=new_email,
                full_name="Agent Updated",
                role=UserRole.AGENT,
                is_active=False,
                password="new-valid-password",
            ),
        )

    assert result.role is UserRole.AGENT
    assert result.is_active is False
    with Session(engine) as session:
        saved = session.get(User, target.id)
        assert saved is not None
        verified, _ = verify_password("new-valid-password", saved.hashed_password)
        assert verified is True


def test_admin_update_rejects_missing_user() -> None:
    actor = make_user("missing-admin-actor", role=UserRole.ADMIN)

    with Session(engine) as session:
        with pytest.raises(NotFoundError) as error:
            UserService(session).update_user(
                actor, uuid.uuid4(), UserUpdateAdmin(full_name="Missing")
            )
        assert error.value.code is ErrorCode.USER_NOT_FOUND
        assert session.in_transaction() is False


def isolate_active_admins(
    admins: list[User], tracked_user_ids: list[uuid.UUID]
) -> list[uuid.UUID]:
    """暂时停用环境 Admin，只保留给定测试 Admin。by AI.Coding"""
    admin_ids = [admin.id for admin in admins]
    with Session(engine) as session:
        original_ids = list(
            session.exec(
                select(User.id).where(
                    User.role == UserRole.ADMIN,
                    User.is_active.is_(True),
                )
            ).all()
        )
        session.exec(
            update(User)
            .where(User.id.in_(original_ids))
            .values(is_active=False)
        )
        session.add_all(admins)
        session.commit()
    tracked_user_ids.extend(admin_ids)
    return original_ids


def restore_active_admins(original_ids: list[uuid.UUID]) -> None:
    """恢复测试前的活跃 Admin。by AI.Coding"""
    with Session(engine) as session:
        session.exec(
            update(User).where(User.id.in_(original_ids)).values(is_active=True)
        )
        session.commit()


def test_last_active_admin_cannot_be_deactivated_or_demoted(
    tracked_user_ids: list[uuid.UUID],
) -> None:
    admin = make_user("last-admin", role=UserRole.ADMIN)
    admin_id = admin.id
    original_ids = isolate_active_admins([admin], tracked_user_ids)
    actor = make_user("last-admin-actor", role=UserRole.ADMIN)
    try:
        for payload in (
            UserUpdateAdmin(is_active=False),
            UserUpdateAdmin(role=UserRole.AGENT),
        ):
            with Session(engine) as session:
                with pytest.raises(ConflictError) as error:
                    UserService(session).update_user(actor, admin_id, payload)
                assert error.value.code is ErrorCode.LAST_ACTIVE_ADMIN

        with Session(engine) as session:
            saved = session.get(User, admin_id)
            assert saved is not None
            assert saved.role is UserRole.ADMIN
            assert saved.is_active is True
    finally:
        restore_active_admins(original_ids)


def test_concurrent_admin_deactivation_preserves_one_active_admin(
    monkeypatch: pytest.MonkeyPatch,
    tracked_user_ids: list[uuid.UUID],
) -> None:
    admin_a = make_user("concurrent-admin-a", role=UserRole.ADMIN)
    admin_b = make_user("concurrent-admin-b", role=UserRole.ADMIN)
    admin_a_id = admin_a.id
    admin_b_id = admin_b.id
    original_ids = isolate_active_admins([admin_a, admin_b], tracked_user_ids)
    actor = make_user("concurrent-admin-actor", role=UserRole.ADMIN)
    first_has_lock = threading.Event()
    release_first = threading.Event()
    second_attempted_lock = threading.Event()
    call_count = 0
    call_count_lock = threading.Lock()
    original_lock = UserRepository.lock_active_admins

    def controlled_lock(repository: UserRepository) -> list[User]:
        nonlocal call_count
        with call_count_lock:
            call_count += 1
            call_number = call_count
        if call_number == 2:
            second_attempted_lock.set()
        admins = original_lock(repository)
        if call_number == 1:
            first_has_lock.set()
            assert release_first.wait(timeout=5)
        return admins

    monkeypatch.setattr(UserRepository, "lock_active_admins", controlled_lock)

    def deactivate(user_id: uuid.UUID) -> ErrorCode | None:
        with Session(engine) as session:
            try:
                UserService(session).update_user(
                    actor, user_id, UserUpdateAdmin(is_active=False)
                )
            except ConflictError as error:
                return error.code
        return None

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(deactivate, admin_a_id)
            assert first_has_lock.wait(timeout=5)
            future_b = executor.submit(deactivate, admin_b_id)
            assert second_attempted_lock.wait(timeout=5)
            time.sleep(0.1)
            assert future_b.done() is False
            release_first.set()
            results = [future_a.result(timeout=5), future_b.result(timeout=5)]

        assert sorted(result.value if result else "SUCCESS" for result in results) == [
            "LAST_ACTIVE_ADMIN",
            "SUCCESS",
        ]
        with Session(engine) as session:
            active_test_admins = session.exec(
                select(User).where(
                    User.id.in_([admin_a_id, admin_b_id]),
                    User.role == UserRole.ADMIN,
                    User.is_active.is_(True),
                )
            ).all()
            assert len(active_test_admins) == 1
    finally:
        release_first.set()
        restore_active_admins(original_ids)
