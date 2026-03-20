from typing import Optional

from models.book_model import BookStatus
from repository.book_repository import BookRepository
from schemas.book_schema import BookCreate, BookResponse, PaginatedBooksResponse


class BookService:
    """Бізнес-логіка для роботи з книгами."""

    def __init__(self, repository: BookRepository):
        self.repository = repository

    async def get_all_books(
        self,
        status: Optional[BookStatus] = None,
        author: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
        limit: int = 10,
        offset: int = 0,
    ) -> PaginatedBooksResponse:
        books, total = await self.repository.get_all(
            status=status,
            author=author,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )
        return PaginatedBooksResponse(
            total=total,
            limit=limit,
            offset=offset,
            books=[BookResponse.model_validate(b) for b in books],
        )

    async def get_book_by_id(self, book_id: str) -> Optional[BookResponse]:
        book = await self.repository.get_by_id(book_id)
        if book is None:
            return None
        return BookResponse.model_validate(book)

    async def create_book(self, book_data: BookCreate) -> BookResponse:
        created = await self.repository.create(book_data.model_dump())
        return BookResponse.model_validate(created)

    async def delete_book(self, book_id: str) -> None:
        """Ідемпотентне видалення — завжди повертає None (204)."""
        await self.repository.delete(book_id)
