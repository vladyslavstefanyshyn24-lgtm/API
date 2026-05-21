from typing import Optional, Literal

from fastapi import APIRouter, HTTPException, status, Query, Depends
from motor.motor_asyncio import AsyncIOMotorCollection

from database import get_books_collection
from models.book_model import BookStatus
from repository.book_repository import BookRepository
from schemas.book_schema import BookCreate, BookResponse, PaginatedBooksResponse
from services.book_service import BookService
from auth_utils import get_current_user

router = APIRouter()


def get_book_service(
    collection: AsyncIOMotorCollection = Depends(get_books_collection),
) -> BookService:
    return BookService(BookRepository(collection))


@router.get(
    "/",
    response_model=PaginatedBooksResponse,
    status_code=status.HTTP_200_OK,
    summary="Отримати всі книги (Limit-Offset пагінація)",
    description=(
        "Повертає сторінку книг. "
        "Використовуй `limit` та `offset` для навігації між сторінками. "
        "Якщо `has_more=false` — сторінок більше немає. "
        "Поле `total` містить загальну кількість записів. "
        "🔒 Потрібна автентифікація."
    ),
)
async def get_all_books(
    status_filter: Optional[BookStatus] = Query(None, alias="status"),
    author: Optional[str] = Query(None),
    sort_by: Optional[Literal["title", "year"]] = Query(None),
    sort_order: Literal["asc", "desc"] = Query("asc"),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0, description="Кількість записів, які потрібно пропустити"),
    service: BookService = Depends(get_book_service),
    current_user: dict = Depends(get_current_user),   # 🔒
):
    return await service.get_all_books(
        status=status_filter,
        author=author,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{book_id}",
    response_model=BookResponse,
    status_code=status.HTTP_200_OK,
    responses={404: {"description": "Книгу не знайдено"}},
    summary="Отримати книгу за ID 🔒",
)
async def get_book_by_id(
    book_id: str,
    service: BookService = Depends(get_book_service),
    current_user: dict = Depends(get_current_user),   # 🔒
):
    book = await service.get_book_by_id(book_id)
    if book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Книгу з ID '{book_id}' не знайдено",
        )
    return book


@router.post(
    "/",
    response_model=BookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Створити книгу 🔒",
)
async def create_book(
    book_data: BookCreate,
    service: BookService = Depends(get_book_service),
    current_user: dict = Depends(get_current_user),   # 🔒
):
    return await service.create_book(book_data)


@router.delete(
    "/{book_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Видалити книгу 🔒",
)
async def delete_book(
    book_id: str,
    service: BookService = Depends(get_book_service),
    current_user: dict = Depends(get_current_user),   # 🔒
):
    await service.delete_book(book_id)
    return None
