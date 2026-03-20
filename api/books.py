from typing import Optional, Literal

from fastapi import APIRouter, HTTPException, status, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.book_model import BookStatus
from repository.book_repository import BookRepository
from schemas.book_schema import BookCreate, BookResponse, PaginatedBooksResponse
from services.book_service import BookService

router = APIRouter()


def get_book_service(db: AsyncSession = Depends(get_db)) -> BookService:
    return BookService(BookRepository(db))


@router.get(
    "/",
    response_model=PaginatedBooksResponse,
    status_code=status.HTTP_200_OK,
    summary="Отримати всі книги",
    description="Повертає пагінований список книг з фільтрацією та сортуванням.",
)
async def get_all_books(
    status_filter: Optional[BookStatus] = Query(None, alias="status"),
    author: Optional[str] = Query(None, description="Фільтр за автором (частковий збіг)"),
    sort_by: Optional[Literal["title", "year"]] = Query(None),
    sort_order: Literal["asc", "desc"] = Query("asc"),
    limit: int = Query(10, ge=1, le=100, description="Кількість записів на сторінці"),
    offset: int = Query(0, ge=0, description="Зміщення від початку"),
    service: BookService = Depends(get_book_service),
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
    summary="Отримати книгу за ID",
    responses={404: {"description": "Книгу не знайдено"}},
)
async def get_book_by_id(
    book_id: str,
    service: BookService = Depends(get_book_service),
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
    summary="Додати нову книгу",
    responses={422: {"description": "Помилка валідації"}},
)
async def create_book(
    book_data: BookCreate,
    service: BookService = Depends(get_book_service),
):
    return await service.create_book(book_data)


@router.delete(
    "/{book_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Видалити книгу (ідемпотентно)",
    description="Завжди повертає 204, навіть якщо книги не існує.",
)
async def delete_book(
    book_id: str,
    service: BookService = Depends(get_book_service),
):
    await service.delete_book(book_id)
    return None
