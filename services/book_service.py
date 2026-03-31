from typing import Optional

from models.book_model import BookStatus
from repository.book_repository import BookRepository
from schemas.book_schema import BookCreate, BookResponse, CursorPaginatedBooksResponse


class BookService:

    def __init__(self, repository: BookRepository):
        self.repository = repository

    async def get_all_books(
        self,
        status: Optional[BookStatus] = None,
        author: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
        limit: int = 10,
        cursor: Optional[str] = None,
    ) -> CursorPaginatedBooksResponse:
        books, next_cursor, has_more = await self.repository.get_all(
            status=status,
            author=author,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            cursor=cursor,
        )
        return CursorPaginatedBooksResponse(
            items=[BookResponse.model_validate(b) for b in books],
            next_cursor=next_cursor,
            limit=limit,
            has_more=has_more,
        )

    async def get_book_by_id(self, book_id: str) -> Optional[BookResponse]:
        book = await self.repository.get_by_id(book_id)
        return BookResponse.model_validate(book) if book else None

    async def create_book(self, book_data: BookCreate) -> BookResponse:
        created = await self.repository.create(book_data.model_dump())
        return BookResponse.model_validate(created)

    async def delete_book(self, book_id: str) -> None:
        await self.repository.delete(book_id)
