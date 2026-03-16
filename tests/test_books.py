import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

import models.book_model as book_model_module
from models.book_model import BookStatus
from repository.book_repository import BookRepository
from schemas.book_schema import BookCreate
from services.book_service import BookService
from main import app

client = TestClient(app)



SAMPLE_BOOKS = [
    {
        "id": "uuid-1",
        "title": "Кобзар",
        "author": "Тарас Шевченко",
        "description": "Поезії",
        "status": BookStatus.AVAILABLE,
        "year": 1840,
    },
    {
        "id": "uuid-2",
        "title": "Місто",
        "author": "Валер'ян Підмогильний",
        "description": "Роман",
        "status": BookStatus.ISSUED,
        "year": 1928,
    },
    {
        "id": "uuid-3",
        "title": "Захар Беркут",
        "author": "Іван Франко",
        "description": "Повість",
        "status": BookStatus.AVAILABLE,
        "year": 1882,
    },
]


@pytest.fixture(autouse=True)
def reset_db():
    """Перед кожним тестом відновлюємо стан in-memory бази."""
    original = list(SAMPLE_BOOKS)
    book_model_module.books_db.clear()
    book_model_module.books_db.extend([dict(b) for b in original])
    yield
    book_model_module.books_db.clear()
    book_model_module.books_db.extend([dict(b) for b in original])


class TestBookRepository:

    @pytest.mark.asyncio
    async def test_get_all_returns_all_books(self):
        repo = BookRepository()
        result = await repo.get_all()
        assert len(result) == len(book_model_module.books_db)

    @pytest.mark.asyncio
    async def test_get_all_filter_by_status_available(self):
        repo = BookRepository()
        result = await repo.get_all(status=BookStatus.AVAILABLE)
        assert all(b["status"] == BookStatus.AVAILABLE for b in result)

    @pytest.mark.asyncio
    async def test_get_all_filter_by_status_issued(self):
        repo = BookRepository()
        result = await repo.get_all(status=BookStatus.ISSUED)
        assert all(b["status"] == BookStatus.ISSUED for b in result)

    @pytest.mark.asyncio
    async def test_get_all_filter_by_author_partial(self):
        repo = BookRepository()
        result = await repo.get_all(author="франко")
        assert len(result) == 1
        assert result[0]["author"] == "Іван Франко"

    @pytest.mark.asyncio
    async def test_get_all_sort_by_title_asc(self):
        repo = BookRepository()
        result = await repo.get_all(sort_by="title", sort_order="asc")
        titles = [b["title"] for b in result]
        assert titles == sorted(titles)

    @pytest.mark.asyncio
    async def test_get_all_sort_by_year_desc(self):
        repo = BookRepository()
        result = await repo.get_all(sort_by="year", sort_order="desc")
        years = [b["year"] for b in result]
        assert years == sorted(years, reverse=True)

    @pytest.mark.asyncio
    async def test_get_by_id_existing(self):
        repo = BookRepository()
        result = await repo.get_by_id("uuid-1")
        assert result is not None
        assert result["id"] == "uuid-1"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self):
        repo = BookRepository()
        result = await repo.get_by_id("non-existent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_create_adds_book(self):
        repo = BookRepository()
        new_book = {
            "id": "uuid-new",
            "title": "Нова книга",
            "author": "Автор",
            "description": "Опис",
            "status": BookStatus.AVAILABLE,
            "year": 2024,
        }
        created = await repo.create(new_book)
        assert created["id"] == "uuid-new"
        assert any(b["id"] == "uuid-new" for b in book_model_module.books_db)

    @pytest.mark.asyncio
    async def test_delete_existing_book(self):
        repo = BookRepository()
        result = await repo.delete("uuid-1")
        assert result is True
        assert not any(b["id"] == "uuid-1" for b in book_model_module.books_db)

    @pytest.mark.asyncio
    async def test_delete_non_existing_book_returns_false(self):
        repo = BookRepository()
        result = await repo.delete("no-such-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_idempotent_second_call_returns_false(self):
        repo = BookRepository()
        await repo.delete("uuid-2")
        second = await repo.delete("uuid-2")
        assert second is False


class TestBookService:

    def _make_service(self) -> BookService:
        return BookService(BookRepository())

    @pytest.mark.asyncio
    async def test_get_all_books_returns_list_response(self):
        service = self._make_service()
        response = await service.get_all_books()
        assert response.total == len(book_model_module.books_db)
        assert len(response.books) == response.total

    @pytest.mark.asyncio
    async def test_get_book_by_id_found(self):
        service = self._make_service()
        book = await service.get_book_by_id("uuid-3")
        assert book is not None
        assert book.id == "uuid-3"
        assert book.author == "Іван Франко"

    @pytest.mark.asyncio
    async def test_get_book_by_id_not_found(self):
        service = self._make_service()
        book = await service.get_book_by_id("xxxx")
        assert book is None

    @pytest.mark.asyncio
    async def test_create_book_generates_uuid(self):
        service = self._make_service()
        book_data = BookCreate(
            title="Тест",
            author="Автор",
            description="Опис",
            status=BookStatus.AVAILABLE,
            year=2023,
        )
        created = await service.create_book(book_data)
        assert created.id is not None
        assert len(created.id) == 36

    @pytest.mark.asyncio
    async def test_create_book_saves_to_store(self):
        service = self._make_service()
        book_data = BookCreate(
            title="Тест",
            author="Автор",
            description=None,
            status=BookStatus.AVAILABLE,
            year=2024,
        )
        created = await service.create_book(book_data)
        assert any(b["id"] == created.id for b in book_model_module.books_db)

    @pytest.mark.asyncio
    async def test_delete_book_existing(self):
        service = self._make_service()
        result = await service.delete_book("uuid-1")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_book_idempotent(self):
        service = self._make_service()
        await service.delete_book("uuid-1")
        result = await service.delete_book("uuid-1")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_all_with_filter_and_sort(self):
        service = self._make_service()
        response = await service.get_all_books(
            status=BookStatus.AVAILABLE,
            sort_by="year",
            sort_order="asc",
        )
        assert all(b.status == BookStatus.AVAILABLE for b in response.books)
        years = [b.year for b in response.books]
        assert years == sorted(years)


class TestBooksAPI:

    def test_get_all_books_200(self):
        response = client.get("/books/")
        assert response.status_code == 200
        data = response.json()
        assert "books" in data
        assert "total" in data
        assert data["total"] == len(book_model_module.books_db)

    def test_get_all_books_filter_by_status(self):
        response = client.get("/books/?status=available")
        assert response.status_code == 200
        data = response.json()
        assert all(b["status"] == "available" for b in data["books"])

    def test_get_all_books_filter_by_author(self):
        response = client.get("/books/?author=франко")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert "Франко" in data["books"][0]["author"]

    def test_get_all_books_sort_by_year_asc(self):
        response = client.get("/books/?sort_by=year&sort_order=asc")
        assert response.status_code == 200
        years = [b["year"] for b in response.json()["books"]]
        assert years == sorted(years)

    def test_get_all_books_sort_by_title_desc(self):
        response = client.get("/books/?sort_by=title&sort_order=desc")
        assert response.status_code == 200
        titles = [b["title"] for b in response.json()["books"]]
        assert titles == sorted(titles, reverse=True)

    def test_get_all_books_invalid_sort_returns_422(self):
        response = client.get("/books/?sort_by=invalid_field")
        assert response.status_code == 422


    def test_get_book_by_id_200(self):
        response = client.get("/books/uuid-1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "uuid-1"
        assert data["title"] == "Кобзар"

    def test_get_book_by_id_404(self):
        response = client.get("/books/non-existing-uuid")
        assert response.status_code == 404
        assert "не знайдено" in response.json()["detail"]


    def test_create_book_201(self):
        payload = {
            "title": "Нова книга",
            "author": "Тест Автор",
            "description": "Опис",
            "status": "available",
            "year": 2022,
        }
        response = client.post("/books/", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Нова книга"
        assert "id" in data
        assert len(data["id"]) == 36

    def test_create_book_default_status_available(self):
        payload = {"title": "Книга без статусу", "author": "Автор", "year": 2021}
        response = client.post("/books/", json=payload)
        assert response.status_code == 201
        assert response.json()["status"] == "available"

    def test_create_book_missing_title_422(self):
        payload = {"author": "Автор", "year": 2021}
        response = client.post("/books/", json=payload)
        assert response.status_code == 422

    def test_create_book_missing_author_422(self):
        payload = {"title": "Книга", "year": 2021}
        response = client.post("/books/", json=payload)
        assert response.status_code == 422

    def test_create_book_missing_year_422(self):
        payload = {"title": "Книга", "author": "Автор"}
        response = client.post("/books/", json=payload)
        assert response.status_code == 422

    def test_create_book_invalid_status_422(self):
        payload = {"title": "Книга", "author": "Автор", "year": 2021, "status": "unknown"}
        response = client.post("/books/", json=payload)
        assert response.status_code == 422

    def test_create_book_future_year_422(self):
        payload = {"title": "Книга", "author": "Автор", "year": 9999}
        response = client.post("/books/", json=payload)
        assert response.status_code == 422

    def test_create_book_empty_title_422(self):
        payload = {"title": "   ", "author": "Автор", "year": 2020}
        response = client.post("/books/", json=payload)
        assert response.status_code == 422


    def test_delete_book_204(self):
        response = client.delete("/books/uuid-1")
        assert response.status_code == 204

    def test_delete_book_idempotent_returns_204_again(self):
        client.delete("/books/uuid-2")
        response = client.delete("/books/uuid-2")
        assert response.status_code == 204 

    def test_delete_non_existing_book_204(self):
        response = client.delete("/books/absolutely-wrong-id")
        assert response.status_code == 204

    def test_delete_removes_book_from_store(self):
        client.delete("/books/uuid-3")
        response = client.get("/books/uuid-3")
        assert response.status_code == 404
