import uuid
from typing import List, Optional

from models.book_model import BookStatus
from repository.book_repository import BookRepository
from schemas.book_schema import BookCreate, BookResponse, BookListResponse


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
    ) -> BookListResponse:
        books = await self.repository.get_all(
            status=status,
            author=author,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        book_responses = [BookResponse(**b) for b in books]
        return BookListResponse(total=len(book_responses), books=book_responses)

    async def get_book_by_id(self, book_id: str) -> Optional[BookResponse]:
        book = await self.repository.get_by_id(book_id)
        if book is None:
            return None
        return BookResponse(**book)

    async def create_book(self, book_data: BookCreate) -> BookResponse:
        new_book = {
            "id": str(uuid.uuid4()),
            **book_data.model_dump(),
        }
        created = await self.repository.create(new_book)
        return BookResponse(**created)

    async def delete_book(self, book_id: str) -> bool:
        """Повертає True якщо видалено, False якщо не знайдено.
        DELETE ідемпотентний — повторний виклик з тим самим ID поверне 204."""
        return await self.repository.delete(book_id)
