from typing import List, Dict, Optional
from models.book_model import books_db, BookStatus


class BookRepository:
    """Взаємодія зі сховищем даних (in-memory List[Dict]).
    У майбутньому методи будуть замінені на ORM-запити."""

    async def get_all(
        self,
        status: Optional[BookStatus] = None,
        author: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
    ) -> List[Dict]:
        result = list(books_db)

        if status is not None:
            result = [b for b in result if b["status"] == status]
        if author is not None:
            result = [
                b for b in result if author.lower() in b["author"].lower()
            ]

        allowed_sort_fields = {"title", "year"}
        if sort_by in allowed_sort_fields:
            reverse = sort_order.lower() == "desc"
            result = sorted(result, key=lambda b: b[sort_by], reverse=reverse)

        return result

    async def get_by_id(self, book_id: str) -> Optional[Dict]:
        for book in books_db:
            if book["id"] == book_id:
                return book
        return None

    async def create(self, book_data: Dict) -> Dict:
        books_db.append(book_data)
        return book_data

    async def delete(self, book_id: str) -> bool:
        """Повертає True якщо книгу було знайдено і видалено, False якщо не знайдено."""
        for i, book in enumerate(books_db):
            if book["id"] == book_id:
                books_db.pop(i)
                return True
        return False
