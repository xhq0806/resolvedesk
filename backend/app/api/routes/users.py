import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from app import crud
from app.api.deps import (
    CurrentUser,
    SessionDep,
)
from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.auth import UpdatePassword
from app.schemas.common import Message
from app.schemas.user import (
    UserCreateAdmin,
    UserFilters,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdateAdmin,
    UserUpdateMe,
)
from app.services.user_service import UserService
from app.utils import generate_new_account_email, send_email

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=UsersPublic)
def read_users(
    session: SessionDep,
    current_user: CurrentUser,
    filters: Annotated[UserFilters, Depends()],
) -> Any:
    """按角色、启停和关键字返回服务端分页用户列表。by AI.Coding"""
    return UserService(session).list_users(current_user, filters)


@router.post("/", response_model=UserPublic)
def create_user(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    user_in: UserCreateAdmin,
) -> Any:
    """由 Admin 创建指定角色和启用状态的用户。by AI.Coding"""
    user = UserService(session).create_user(current_user, user_in)
    if user_in.email:
        email_data = generate_new_account_email(
            email_to=str(user_in.email),
            username=str(user_in.email),
            password=user_in.password,
        )
        send_email(
            email_to=str(user_in.email),
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return user


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """
    Update own user.
    """

    if user_in.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=409, detail="该邮箱已被其他用户使用"
            )
    user_data = user_in.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@router.patch("/me/password", response_model=Message)
def update_password_me(
    *, session: SessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    """
    Update own password.
    """
    verified, _ = verify_password(body.current_password, current_user.hashed_password)
    if not verified:
        raise HTTPException(status_code=400, detail="当前密码错误")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="新密码不能与当前密码相同"
        )
    hashed_password = get_password_hash(body.new_password)
    current_user.hashed_password = hashed_password
    session.add(current_user)
    session.commit()
    return Message(message="密码更新成功")


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return current_user


@router.post("/signup", response_model=UserPublic)
def register_user(session: SessionDep, user_in: UserRegister) -> Any:
    """
    Create new user without the need to be logged in.
    """
    return UserService(session).register_customer(user_in)


@router.get("/{user_id}", response_model=UserPublic)
def read_user_by_id(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    user = session.get(User, user_id)
    if user == current_user:
        return user
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="用户权限不足",
        )
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.patch(
    "/{user_id}",
    response_model=UserPublic,
)
def update_user(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    user_id: uuid.UUID,
    user_in: UserUpdateAdmin,
) -> Any:
    """由 Admin 修改其他用户的角色、启停和个人资料。by AI.Coding"""
    return UserService(session).update_user(current_user, user_id, user_in)
