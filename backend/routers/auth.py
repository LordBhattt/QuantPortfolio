from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from backend.data_types import CurrentUser
from backend.database import get_db
from backend.dependencies import get_current_user
from backend.errors import AppError
from backend.schemas.auth import Token, UserCreate, UserOut
from backend.services.auth_service import authenticate_user, create_access_token, create_user, get_user_by_id

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> UserOut:
    return await create_user(payload, db)


@router.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Token:
    user = await authenticate_user(form_data.username, form_data.password, db)
    if user is None:
        raise AppError("Authentication failed", "invalid_credentials", "Incorrect email or password", 401)
    token = create_access_token(str(user.id))
    return Token(access_token=token, token_type="bearer")


@router.get("/me", response_model=UserOut)
async def me(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await get_user_by_id(current_user.id, db)
    if user is None:
        raise AppError("Authentication failed", "user_not_found", "User not found or inactive", 401)
    return user
