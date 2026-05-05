from fastapi import APIRouter, Depends, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from backend.data_types import CurrentUser
from backend.database import get_db
from backend.dependencies import get_current_user
from backend.errors import AppError
from backend.schemas.auth import UserCreate, UserOut
from backend.services.auth_service import (
    authenticate_user,
    clear_auth_cookie,
    create_access_token,
    create_user,
    get_user_by_id,
    set_auth_cookie,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
async def register(payload: UserCreate, response: Response, db: AsyncSession = Depends(get_db)) -> UserOut:
    user = await create_user(payload, db)
    token = create_access_token(str(user.id))
    set_auth_cookie(response, token)
    return user


@router.post("/token", response_model=UserOut)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await authenticate_user(form_data.username, form_data.password, db)
    if user is None:
        raise AppError("Authentication failed", "invalid_credentials", "Incorrect email or password", 401)
    token = create_access_token(str(user.id))
    set_auth_cookie(response, token)
    return user


@router.post("/logout", status_code=204)
async def logout(response: Response) -> Response:
    clear_auth_cookie(response)
    response.status_code = 204
    return response


@router.get("/me", response_model=UserOut)
async def me(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await get_user_by_id(current_user.id, db)
    if user is None:
        raise AppError("Authentication failed", "user_not_found", "User not found or inactive", 401)
    return user
