import uuid
from typing import Optional
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.book_model import Book, BookStatus


class BookRepository:
    """Взаємодія з базою даних через SQLAlchemy async."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(
        self,
        status: Optional[BookStatus] = None,
        author: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[list[Book], int]:
        """Повертає (список книг, загальна кількість)."""
        query = select(Book)

        if status is not None:
            query = query.where(Book.status == status)

        sort_column_map = {"title": Book.title, "year": Book.year}
        if sort_by in sort_column_map:
            col = sort_column_map[sort_by]
            query = query.order_by(col.desc() if sort_order == "desc" else col.asc())

        result = await self.session.execute(query)
        books = list(result.scalars().all())

        if author is not None:
            search = author.lower()
            books = [b for b in books if search in b.author.lower()]

        total = len(books)

        books = books[offset: offset + limit]

        return books, total

    async def get_by_id(self, book_id: str) -> Optional[Book]:
        result = await self.session.execute(select(Book).where(Book.id == book_id))
        return result.scalar_one_or_none()

    async def create(self, book_data: dict) -> Book:
        book = Book(id=str(uuid.uuid4()), **book_data)
        self.session.add(book)
        await self.session.flush()
        await self.session.refresh(book)
        return book

    async def delete(self, book_id: str) -> None:
        """Не кидає помилку якщо книга не існує."""
        await self.session.execute(delete(Book).where(Book.id == book_id))
