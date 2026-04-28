from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.errors import AppError
from backend.models.user import users
from backend.schemas.auth import TokenData, UserCreate, UserInDB, UserOut

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": user_id, "exp": expires_at},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise AppError("Authentication failed", "invalid_token", "Missing subject in token", 401)
        return TokenData(user_id=user_id)
    except JWTError as exc:
        raise AppError("Authentication failed", "invalid_token", "Invalid or expired token", 401) from exc


async def get_user_by_email(email: str, db: AsyncSession) -> UserInDB | None:
    result = await db.execute(select(users).where(users.c.email == email.lower()))
    row = result.mappings().first()
    return UserInDB.model_validate(row) if row else None


async def get_user_by_id(user_id: UUID, db: AsyncSession) -> UserOut | None:
    result = await db.execute(select(users).where(users.c.id == user_id))
    row = result.mappings().first()
    return UserOut.model_validate(row) if row else None


async def create_user(payload: UserCreate, db: AsyncSession) -> UserOut:
    existing = await get_user_by_email(payload.email, db)
    if existing is not None:
        raise AppError("Registration failed", "email_exists", "Email already registered", 400)

    statement = (
        insert(users)
        .values(
            email=payload.email.lower(),
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name,
            is_active=True,
        )
        .returning(users)
    )
    result = await db.execute(statement)
    created = result.mappings().one()
    return UserOut.model_validate(created)


async def authenticate_user(email: str, password: str, db: AsyncSession) -> UserInDB | None:
    user = await get_user_by_email(email, db)
    if user is None or not verify_password(password, user.hashed_password):
        return None
    return user
