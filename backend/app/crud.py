from typing import Any

from sqlmodel import Session, select

from app.core.security import get_password_hash, verify_password
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


def create_user(*, session: Session, user_create: UserCreate) -> User:
    """创建用户并将旧超级用户输入映射为单角色字段。by AI.Coding"""
    user_data = user_create.model_dump(exclude={"password", "is_superuser"})
    role = UserRole.ADMIN if user_create.is_superuser else UserRole.CUSTOMER
    db_obj = User.model_validate(
        user_data,
        update={
            "hashed_password": get_password_hash(user_create.password),
            "role": role,
        },
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    """更新用户并将旧超级用户输入安全翻译为角色。by AI.Coding"""
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data: dict[str, Any] = {}
    is_superuser = user_data.pop("is_superuser", None)
    if is_superuser is not None:
        # 兼容旧管理接口，但数据库只保留单一 role 真源。
        extra_data["role"] = UserRole.ADMIN if is_superuser else UserRole.CUSTOMER
    if "password" in user_data:
        password = user_data.pop("password")
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user


# Dummy hash to use for timing attack prevention when user is not found
# This is an Argon2 hash of a random password, used to ensure constant-time comparison
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    """校验用户密码并按需升级密码哈希。by AI.Coding"""
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        # Prevent timing attacks by running password verification even when user doesn't exist
        # This ensures the response time is similar whether or not the email exists
        verify_password(password, DUMMY_HASH)
        return None
    verified, updated_password_hash = verify_password(password, db_user.hashed_password)
    if not verified:
        return None
    if updated_password_hash:
        db_user.hashed_password = updated_password_hash
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
    return db_user
