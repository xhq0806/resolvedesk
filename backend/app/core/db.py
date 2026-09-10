from sqlmodel import Session, col, create_engine, select

from app import crud
from app.core.config import settings
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import UserCreate

engine = create_engine(str(settings.DATABASE_URL))


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# 导入完整模型包，确保关系和表元数据在初始化前已经注册。


def init_db(session: Session) -> None:
    """初始化首个管理员并验证系统保留活跃 Admin。by AI.Coding"""
    # 数据库表统一由 Alembic 管理，初始化逻辑只负责业务种子数据。

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = crud.create_user(session=session, user_create=user_in)
        if user.role is not UserRole.ADMIN:
            user.role = UserRole.ADMIN
            session.add(user)
            session.commit()
            session.refresh(user)

    active_admin = session.exec(
        select(User).where(
            User.role == UserRole.ADMIN,
            col(User.is_active).is_(True),
        )
    ).first()
    if active_admin is None:
        raise RuntimeError("数据库初始化失败：系统中必须至少存在一位活跃管理员。")
