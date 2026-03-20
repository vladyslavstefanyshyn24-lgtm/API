"""
Юніт-тести для Library API v2 (SQLAlchemy + PostgreSQL).
Тести використовують SQLite (aiosqlite) щоб не потребувати реального PostgreSQL.

Покриття:
  - Repository  (12 тестів)
  - Service     (9 тестів)
  - API/HTTP    (21 тест)
"""
import sys
import os
import pytest
import pytest_asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

import database as db_module
from database import Base, get_db
from main import app
from models.book_model import Book, BookStatus
from repository.book_repository import BookRepository
from schemas.book_schema import BookCreate
from services.book_service import BookService


TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = async_sessionmaker(
    bind=test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Створює чисту БД для кожного тесту."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def seeded_session(db_session: AsyncSession):
    """БД з тестовими даними."""
    books = [
        Book(
            id="uuid-1",
            title="Кобзар",
            author="Тарас Шевченко",
            description="Поезії",
            status=BookStatus.AVAILABLE,
            year=1840,
        ),
        Book(
            id="uuid-2",
            title="Місто",
            author="Валер'ян Підмогильний",
            description="Роман",
            status=BookStatus.ISSUED,
            year=1928,
        ),
        Book(
            id="uuid-3",
            title="Захар Беркут",
            author="Іван Франко",
            description="Повість",
            status=BookStatus.AVAILABLE,
            year=1882,
        ),
    ]
    db_session.add_all(books)
    await db_session.commit()
    yield db_session


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession):
    """HTTP тест-клієнт з підміненою БД-сесією."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def seeded_client(seeded_session: AsyncSession):
    """HTTP тест-клієнт з даними."""

    async def override_get_db():
        yield seeded_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()



class TestBookRepository:

    @pytest.mark.asyncio
    async def test_get_all_returns_all_books(self, seeded_session):
        repo = BookRepository(seeded_session)
        books, total = await repo.get_all()
        assert total == 3
        assert len(books) == 3

    @pytest.mark.asyncio
    async def test_get_all_filter_by_status_available(self, seeded_session):
        repo = BookRepository(seeded_session)
        books, total = await repo.get_all(status=BookStatus.AVAILABLE)
        assert total == 2
        assert all(b.status == BookStatus.AVAILABLE for b in books)

    @pytest.mark.asyncio
    async def test_get_all_filter_by_status_issued(self, seeded_session):
        repo = BookRepository(seeded_session)
        books, total = await repo.get_all(status=BookStatus.ISSUED)
        assert total == 1
        assert books[0].author == "Валер'ян Підмогильний"

    @pytest.mark.asyncio
    async def test_get_all_filter_by_author_partial(self, seeded_session):
        repo = BookRepository(seeded_session)
        books, total = await repo.get_all(author="франко")
        assert total == 1
        assert books[0].author == "Іван Франко"

    @pytest.mark.asyncio
    async def test_get_all_sort_by_year_asc(self, seeded_session):
        repo = BookRepository(seeded_session)
        books, _ = await repo.get_all(sort_by="year", sort_order="asc")
        years = [b.year for b in books]
        assert years == sorted(years)

    @pytest.mark.asyncio
    async def test_get_all_sort_by_title_desc(self, seeded_session):
        repo = BookRepository(seeded_session)
        books, _ = await repo.get_all(sort_by="title", sort_order="desc")
        titles = [b.title for b in books]
        assert titles == sorted(titles, reverse=True)

    @pytest.mark.asyncio
    async def test_pagination_limit(self, seeded_session):
        repo = BookRepository(seeded_session)
        books, total = await repo.get_all(limit=2, offset=0)
        assert total == 3  
        assert len(books) == 2

    @pytest.mark.asyncio
    async def test_pagination_offset(self, seeded_session):
        repo = BookRepository(seeded_session)
        books, total = await repo.get_all(limit=10, offset=2)
        assert total == 3
        assert len(books) == 1

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, seeded_session):
        repo = BookRepository(seeded_session)
        book = await repo.get_by_id("uuid-1")
        assert book is not None
        assert book.title == "Кобзар"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, seeded_session):
        repo = BookRepository(seeded_session)
        book = await repo.get_by_id("no-such-id")
        assert book is None

    @pytest.mark.asyncio
    async def test_create_book(self, db_session):
        repo = BookRepository(db_session)
        book = await repo.create(
            {"title": "Нова", "author": "Автор", "description": None,
             "status": BookStatus.AVAILABLE, "year": 2024}
        )
        await db_session.commit()
        assert book.id is not None
        assert len(book.id) == 36

    @pytest.mark.asyncio
    async def test_delete_existing_book(self, seeded_session):
        repo = BookRepository(seeded_session)
        await repo.delete("uuid-1")
        await seeded_session.commit()
        book = await repo.get_by_id("uuid-1")
        assert book is None

    @pytest.mark.asyncio
    async def test_delete_idempotent_no_error(self, seeded_session):
        repo = BookRepository(seeded_session)
        await repo.delete("uuid-1")
        await seeded_session.commit()
        await repo.delete("uuid-1")
        await seeded_session.commit()



class TestBookService:

    def _service(self, session):
        return BookService(BookRepository(session))

    @pytest.mark.asyncio
    async def test_get_all_returns_paginated(self, seeded_session):
        svc = self._service(seeded_session)
        result = await svc.get_all_books(limit=10, offset=0)
        assert result.total == 3
        assert result.limit == 10
        assert result.offset == 0
        assert len(result.books) == 3

    @pytest.mark.asyncio
    async def test_get_all_pagination_limit(self, seeded_session):
        svc = self._service(seeded_session)
        result = await svc.get_all_books(limit=2, offset=0)
        assert result.total == 3
        assert len(result.books) == 2

    @pytest.mark.asyncio
    async def test_get_all_filter_by_status(self, seeded_session):
        svc = self._service(seeded_session)
        result = await svc.get_all_books(status=BookStatus.AVAILABLE)
        assert all(b.status == BookStatus.AVAILABLE for b in result.books)

    @pytest.mark.asyncio
    async def test_get_book_by_id_found(self, seeded_session):
        svc = self._service(seeded_session)
        book = await svc.get_book_by_id("uuid-3")
        assert book is not None
        assert book.author == "Іван Франко"

    @pytest.mark.asyncio
    async def test_get_book_by_id_not_found(self, seeded_session):
        svc = self._service(seeded_session)
        book = await svc.get_book_by_id("missing")
        assert book is None

    @pytest.mark.asyncio
    async def test_create_book_generates_uuid(self, db_session):
        svc = self._service(db_session)
        data = BookCreate(title="Тест", author="Автор", year=2020)
        created = await svc.create_book(data)
        assert len(created.id) == 36

    @pytest.mark.asyncio
    async def test_create_book_persists(self, db_session):
        svc = self._service(db_session)
        data = BookCreate(title="Тест", author="Автор", year=2020)
        created = await svc.create_book(data)
        await db_session.commit()
        found = await svc.get_book_by_id(created.id)
        assert found is not None

    @pytest.mark.asyncio
    async def test_delete_book_idempotent(self, seeded_session):
        svc = self._service(seeded_session)
        await svc.delete_book("uuid-1")
        await seeded_session.commit()
        await svc.delete_book("uuid-1")
        await seeded_session.commit()

    @pytest.mark.asyncio
    async def test_delete_non_existing_no_error(self, db_session):
        svc = self._service(db_session)
        await svc.delete_book("totally-fake-id")



class TestBooksAPI:


    @pytest.mark.asyncio
    async def test_get_all_books_200(self, seeded_client):
        r = await seeded_client.get("/books/")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 3
        assert data["limit"] == 10
        assert data["offset"] == 0
        assert len(data["books"]) == 3

    @pytest.mark.asyncio
    async def test_get_all_books_empty(self, client):
        r = await client.get("/books/")
        assert r.status_code == 200
        assert r.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_pagination_limit(self, seeded_client):
        r = await seeded_client.get("/books/?limit=2&offset=0")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 3
        assert len(data["books"]) == 2

    @pytest.mark.asyncio
    async def test_pagination_offset(self, seeded_client):
        r = await seeded_client.get("/books/?limit=10&offset=2")
        assert r.status_code == 200
        assert len(r.json()["books"]) == 1

    @pytest.mark.asyncio
    async def test_pagination_invalid_limit_422(self, seeded_client):
        r = await seeded_client.get("/books/?limit=0")
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_pagination_limit_over_100_422(self, seeded_client):
        r = await seeded_client.get("/books/?limit=200")
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_filter_by_status(self, seeded_client):
        r = await seeded_client.get("/books/?status=available")
        assert r.status_code == 200
        assert all(b["status"] == "available" for b in r.json()["books"])

    @pytest.mark.asyncio
    async def test_filter_by_author(self, seeded_client):
        r = await seeded_client.get("/books/?author=франко")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert "Франко" in data["books"][0]["author"]

    @pytest.mark.asyncio
    async def test_sort_by_year_asc(self, seeded_client):
        r = await seeded_client.get("/books/?sort_by=year&sort_order=asc")
        assert r.status_code == 200
        years = [b["year"] for b in r.json()["books"]]
        assert years == sorted(years)

    @pytest.mark.asyncio
    async def test_sort_by_title_desc(self, seeded_client):
        r = await seeded_client.get("/books/?sort_by=title&sort_order=desc")
        assert r.status_code == 200
        titles = [b["title"] for b in r.json()["books"]]
        assert titles == sorted(titles, reverse=True)

    @pytest.mark.asyncio
    async def test_invalid_sort_field_422(self, seeded_client):
        r = await seeded_client.get("/books/?sort_by=unknown")
        assert r.status_code == 422


    @pytest.mark.asyncio
    async def test_get_book_by_id_200(self, seeded_client):
        r = await seeded_client.get("/books/uuid-1")
        assert r.status_code == 200
        assert r.json()["title"] == "Кобзар"

    @pytest.mark.asyncio
    async def test_get_book_by_id_404(self, seeded_client):
        r = await seeded_client.get("/books/not-existing")
        assert r.status_code == 404
        assert "не знайдено" in r.json()["detail"]


    @pytest.mark.asyncio
    async def test_create_book_201(self, client):
        payload = {"title": "Нова книга", "author": "Автор", "year": 2022}
        r = await client.post("/books/", json=payload)
        assert r.status_code == 201
        data = r.json()
        assert data["title"] == "Нова книга"
        assert len(data["id"]) == 36

    @pytest.mark.asyncio
    async def test_create_book_default_status(self, client):
        r = await client.post("/books/", json={"title": "X", "author": "Y", "year": 2020})
        assert r.status_code == 201
        assert r.json()["status"] == "available"

    @pytest.mark.asyncio
    async def test_create_book_missing_title_422(self, client):
        r = await client.post("/books/", json={"author": "A", "year": 2020})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_create_book_missing_author_422(self, client):
        r = await client.post("/books/", json={"title": "T", "year": 2020})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_create_book_future_year_422(self, client):
        r = await client.post("/books/", json={"title": "T", "author": "A", "year": 9999})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_create_book_empty_title_422(self, client):
        r = await client.post("/books/", json={"title": "   ", "author": "A", "year": 2020})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_create_book_invalid_status_422(self, client):
        r = await client.post("/books/", json={"title": "T", "author": "A", "year": 2020, "status": "wrong"})
        assert r.status_code == 422


    @pytest.mark.asyncio
    async def test_delete_book_204(self, seeded_client):
        r = await seeded_client.delete("/books/uuid-1")
        assert r.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_idempotent_second_call_204(self, seeded_client):
        await seeded_client.delete("/books/uuid-2")
        r = await seeded_client.delete("/books/uuid-2")
        assert r.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_non_existing_204(self, client):
        r = await client.delete("/books/absolutely-wrong-id")
        assert r.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_removes_book(self, seeded_client):
        await seeded_client.delete("/books/uuid-3")
        r = await seeded_client.get("/books/uuid-3")
        assert r.status_code == 404
