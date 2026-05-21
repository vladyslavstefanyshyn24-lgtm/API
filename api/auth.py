from fastapi import APIRouter, HTTPException, status, Depends
from motor.motor_asyncio import AsyncIOMotorCollection

from database import get_users_collection
from repository.user_repository import UserRepository
from schemas.auth_schema import (
    UserRegister,
    UserLogin,
    TokenResponse,
    RefreshRequest,
    AccessTokenResponse,
    UserResponse,
)
from auth_utils import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_current_user,
)

router = APIRouter()


def get_user_repo(
    collection: AsyncIOMotorCollection = Depends(get_users_collection),
) -> UserRepository:
    return UserRepository(collection)


# ── POST /auth/register ───────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Реєстрація нового користувача",
)
async def register(
    body: UserRegister,
    repo: UserRepository = Depends(get_user_repo),
):
    if await repo.get_by_username(body.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Користувач '{body.username}' вже існує",
        )
    user = await repo.create(body.username, body.password)
    return UserResponse(id=user["id"], username=user["username"])


# ── POST /auth/login ──────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Отримати access + refresh токени",
    description=(
        "Передай `username` та `password`. "
        "У відповідь отримаєш **access_token** (15 хв) та **refresh_token** (7 днів)."
    ),
)
async def login(
    body: UserLogin,
    repo: UserRepository = Depends(get_user_repo),
):
    user = await repo.get_by_username(body.username)
    if user is None or not UserRepository.verify_password(body.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невірний логін або пароль",
        )

    token_data = {"sub": user["username"], "user_id": user["id"]}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


# ── POST /auth/refresh ────────────────────────────────────────────────────────

@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    summary="Оновити access token за допомогою refresh token",
    description=(
        "Передай дійсний **refresh_token**. "
        "У відповідь отримаєш новий **access_token**. "
        "Refresh token залишається тим самим до закінчення терміну дії."
    ),
)
async def refresh(
    body: RefreshRequest,
    repo: UserRepository = Depends(get_user_repo),
):
    payload = decode_refresh_token(body.refresh_token)

    # Verify user still exists in DB
    user = await repo.get_by_username(payload["sub"])
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Користувача не знайдено",
        )

    token_data = {"sub": user["username"], "user_id": user["id"]}
    return AccessTokenResponse(access_token=create_access_token(token_data))


# ── GET /auth/me ──────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Отримати інформацію про поточного користувача",
)
async def me(
    current_user: dict = Depends(get_current_user),
    repo: UserRepository = Depends(get_user_repo),
):
    user = await repo.get_by_username(current_user["username"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Користувача не знайдено")
    return UserResponse(id=user["id"], username=user["username"])
