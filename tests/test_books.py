import sys
import os
import pytest
import pytest_asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from httpx import AsyncClient, ASGITransport
from mongomock_motor import AsyncMongoMockClient

import database
from main import app
from models.book_model import BookStatus
from repository.book_repository import BookRepository
from schemas.book_schema import BookCreate
from services.book_service import BookService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def mock_collection():
    """In-memory MongoDB collection powered by mongomock-motor."""
    client = AsyncMongoMockClient()
    collection = client["test_db"]["books"]
    yield collection


@pytest_asyncio.fixture
async def seeded_collection(mock_collection):
    books = [
        {"title": "Кобзар", "author": "Тарас Шевченко", "description": "Поезії",
         "status": "available", "year": 1840},
        {"title": "Місто", "author": "Валер'ян Підмогильний", "description": "Роман",
         "status": "issued", "year": 1928},
        {"title": "Захар Беркут", "author": "Іван Франко", "description": "Повість",
         "status": "available", "year": 1882},
        {"title": "Тіні забутих предків", "author": "Михайло Коцюбинський", "description": "Повість",
         "status": "available", "year": 1911},
        {"title": "Земля", "author": "Ольга Кобилянська", "description": "Роман",
         "status": "issued", "year": 1902},
    ]
    await mock_collection.insert_many(books)
    yield mock_collection


@pytest_asyncio.fixture
async def client(mock_collection):
    async def override():
        yield mock_collection

    app.dependency_overrides[database.get_books_collection] = override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_client(seeded_collection):
    async def override():
        yield seeded_collection

    app.dependency_overrides[database.get_books_collection] = override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Repository tests
# ---------------------------------------------------------------------------

class TestBookRepository:

    @pytest.mark.asyncio
    async def test_get_all_returns_all_books(self, seeded_collection):
        repo = BookRepository(seeded_collection)
        books, total = await repo.get_all(limit=10)
        assert len(books) == 5
        assert total == 5

    @pytest.mark.asyncio
    async def test_limit_offset_first_page(self, seeded_collection):
        repo = BookRepository(seeded_collection)
        books, total = await repo.get_all(limit=2, offset=0)
        assert len(books) == 2
        assert total == 5

    @pytest.mark.asyncio
    async def test_limit_offset_second_page_no_overlap(self, seeded_collection):
        repo = BookRepository(seeded_collection)
        page1, _ = await repo.get_all(limit=2, offset=0)
        page2, _ = await repo.get_all(limit=2, offset=2)
        ids1 = {b["id"] for b in page1}
        ids2 = {b["id"] for b in page2}
        assert ids1.isdisjoint(ids2)

    @pytest.mark.asyncio
    async def test_limit_offset_last_page(self, seeded_collection):
        repo = BookRepository(seeded_collection)
        books, total = await repo.get_all(limit=2, offset=4)
        assert len(books) == 1
        assert total == 5

    @pytest.mark.asyncio
    async def test_limit_offset_covers_all_records(self, seeded_collection):
        repo = BookRepository(seeded_collection)
        all_ids = set()
        offset = 0
        while True:
            books, total = await repo.get_all(limit=2, offset=offset)
            all_ids.update(b["id"] for b in books)
            offset += 2
            if offset >= total:
                break
        assert len(all_ids) == 5

    @pytest.mark.asyncio
    async def test_filter_by_status_available(self, seeded_collection):
        repo = BookRepository(seeded_collection)
        books, total = await repo.get_all(status=BookStatus.AVAILABLE, limit=10)
        assert total == 3
        assert all(b["status"] == "available" for b in books)

    @pytest.mark.asyncio
    async def test_filter_by_author_partial(self, seeded_collection):
        repo = BookRepository(seeded_collection)
        books, total = await repo.get_all(author="франко", limit=10)
        assert total == 1
        assert books[0]["author"] == "Іван Франко"

    @pytest.mark.asyncio
    async def test_sort_by_year_asc(self, seeded_collection):
        repo = BookRepository(seeded_collection)
        books, _ = await repo.get_all(sort_by="year", sort_order="asc", limit=10)
        years = [b["year"] for b in books]
        assert years == sorted(years)

    @pytest.mark.asyncio
    async def test_sort_by_title_desc(self, seeded_collection):
        repo = BookRepository(seeded_collection)
        books, _ = await repo.get_all(sort_by="title", sort_order="desc", limit=10)
        titles = [b["title"] for b in books]
        assert titles == sorted(titles, reverse=True)

    @pytest.mark.asyncio
    async def test_get_by_id_not_found_returns_none(self, seeded_collection):
        repo = BookRepository(seeded_collection)
        # Use a valid-looking but non-existent ObjectId
        result = await repo.get_by_id("000000000000000000000001")
        assert result is None

    @pytest.mark.asyncio
    async def test_create_book(self, mock_collection):
        repo = BookRepository(mock_collection)
        book_data = BookCreate(title="Нова книга", author="Автор", year=2020)
        created = await repo.create(book_data)
        assert "id" in created
        assert created["title"] == "Нова книга"

    @pytest.mark.asyncio
    async def test_delete_existing(self, seeded_collection):
        repo = BookRepository(seeded_collection)
        books, _ = await repo.get_all(limit=1)
        book_id = books[0]["id"]
        deleted = await repo.delete(book_id)
        assert deleted is True
        assert await repo.get_by_id(book_id) is None

    @pytest.mark.asyncio
    async def test_delete_non_existing_returns_false(self, mock_collection):
        repo = BookRepository(mock_collection)
        result = await repo.delete("000000000000000000000001")
        assert result is False


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------

class TestBookService:

    def _svc(self, col):
        return BookService(BookRepository(col))

    @pytest.mark.asyncio
    async def test_get_all_response_shape(self, seeded_collection):
        r = await self._svc(seeded_collection).get_all_books(limit=10, offset=0)
        assert len(r.items) == 5
        assert r.total == 5
        assert r.has_more is False

    @pytest.mark.asyncio
    async def test_has_more_true_on_partial_page(self, seeded_collection):
        r = await self._svc(seeded_collection).get_all_books(limit=2, offset=0)
        assert r.has_more is True
        assert len(r.items) == 2

    @pytest.mark.asyncio
    async def test_offset_pagination_no_overlap(self, seeded_collection):
        svc = self._svc(seeded_collection)
        p1 = await svc.get_all_books(limit=2, offset=0)
        p2 = await svc.get_all_books(limit=2, offset=2)
        assert {b.id for b in p1.items}.isdisjoint({b.id for b in p2.items})

    @pytest.mark.asyncio
    async def test_get_book_by_id_not_found(self, seeded_collection):
        result = await self._svc(seeded_collection).get_book_by_id("000000000000000000000001")
        assert result is None

    @pytest.mark.asyncio
    async def test_create_book_generates_id(self, mock_collection):
        created = await self._svc(mock_collection).create_book(
            BookCreate(title="X", author="Y", year=2020)
        )
        assert created.id is not None and len(created.id) == 24

    @pytest.mark.asyncio
    async def test_delete_existing_returns_true(self, seeded_collection):
        svc = self._svc(seeded_collection)
        r = await svc.get_all_books(limit=1)
        book_id = r.items[0].id
        result = await svc.delete_book(book_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_non_existing_returns_false(self, mock_collection):
        result = await self._svc(mock_collection).delete_book("000000000000000000000001")
        assert result is False


# ---------------------------------------------------------------------------
# API (integration) tests
# ---------------------------------------------------------------------------

class TestBooksAPI:

    @pytest.mark.asyncio
    async def test_get_all_200_shape(self, seeded_client):
        r = await seeded_client.get("/books/")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data and "total" in data and "has_more" in data
        assert len(data["items"]) == 5

    @pytest.mark.asyncio
    async def test_get_all_empty(self, client):
        r = await client.get("/books/")
        assert r.status_code == 200
        assert r.json()["items"] == []
        assert r.json()["has_more"] is False
        assert r.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_limit_offset_first_page(self, seeded_client):
        r = await seeded_client.get("/books/?limit=2&offset=0")
        data = r.json()
        assert len(data["items"]) == 2
        assert data["has_more"] is True
        assert data["total"] == 5

    @pytest.mark.asyncio
    async def test_limit_offset_no_overlap(self, seeded_client):
        r1 = await seeded_client.get("/books/?limit=2&offset=0")
        r2 = await seeded_client.get("/books/?limit=2&offset=2")
        ids1 = {b["id"] for b in r1.json()["items"]}
        ids2 = {b["id"] for b in r2.json()["items"]}
        assert ids1.isdisjoint(ids2)

    @pytest.mark.asyncio
    async def test_limit_offset_traverse_all(self, seeded_client):
        all_ids, offset = set(), 0
        while True:
            r = await seeded_client.get(f"/books/?limit=2&offset={offset}")
            data = r.json()
            all_ids.update(b["id"] for b in data["items"])
            if not data["has_more"]:
                break
            offset += 2
        assert len(all_ids) == 5

    @pytest.mark.asyncio
    async def test_limit_0_422(self, client):
        assert (await client.get("/books/?limit=0")).status_code == 422

    @pytest.mark.asyncio
    async def test_limit_over_100_422(self, client):
        assert (await client.get("/books/?limit=200")).status_code == 422

    @pytest.mark.asyncio
    async def test_negative_offset_422(self, client):
        assert (await client.get("/books/?offset=-1")).status_code == 422

    @pytest.mark.asyncio
    async def test_filter_by_status(self, seeded_client):
        r = await seeded_client.get("/books/?status=available")
        assert all(b["status"] == "available" for b in r.json()["items"])
        assert r.json()["total"] == 3

    @pytest.mark.asyncio
    async def test_filter_by_author(self, seeded_client):
        r = await seeded_client.get("/books/?author=франко")
        assert len(r.json()["items"]) == 1

    @pytest.mark.asyncio
    async def test_sort_by_year_asc(self, seeded_client):
        r = await seeded_client.get("/books/?sort_by=year&sort_order=asc")
        years = [b["year"] for b in r.json()["items"]]
        assert years == sorted(years)

    @pytest.mark.asyncio
    async def test_sort_by_title_desc(self, seeded_client):
        r = await seeded_client.get("/books/?sort_by=title&sort_order=desc")
        titles = [b["title"] for b in r.json()["items"]]
        assert titles == sorted(titles, reverse=True)

    @pytest.mark.asyncio
    async def test_invalid_sort_422(self, client):
        assert (await client.get("/books/?sort_by=invalid")).status_code == 422

    @pytest.mark.asyncio
    async def test_get_by_id_404(self, client):
        assert (await client.get("/books/000000000000000000000001")).status_code == 404

    @pytest.mark.asyncio
    async def test_create_201(self, client):
        r = await client.post("/books/", json={"title": "X", "author": "Y", "year": 2022})
        assert r.status_code == 201
        assert len(r.json()["id"]) == 24  # MongoDB ObjectId as hex string

    @pytest.mark.asyncio
    async def test_create_default_status(self, client):
        r = await client.post("/books/", json={"title": "X", "author": "Y", "year": 2020})
        assert r.json()["status"] == "available"

    @pytest.mark.asyncio
    async def test_create_missing_title_422(self, client):
        assert (await client.post("/books/", json={"author": "A", "year": 2020})).status_code == 422

    @pytest.mark.asyncio
    async def test_create_missing_author_422(self, client):
        assert (await client.post("/books/", json={"title": "T", "year": 2020})).status_code == 422

    @pytest.mark.asyncio
    async def test_create_future_year_422(self, client):
        assert (await client.post("/books/", json={"title": "T", "author": "A", "year": 9999})).status_code == 422

    @pytest.mark.asyncio
    async def test_create_empty_title_422(self, client):
        assert (await client.post("/books/", json={"title": "   ", "author": "A", "year": 2020})).status_code == 422

    @pytest.mark.asyncio
    async def test_create_invalid_status_422(self, client):
        assert (await client.post("/books/", json={"title": "T", "author": "A", "year": 2020, "status": "wrong"})).status_code == 422

    @pytest.mark.asyncio
    async def test_delete_204(self, seeded_client):
        r = await seeded_client.get("/books/?limit=1")
        book_id = r.json()["items"][0]["id"]
        assert (await seeded_client.delete(f"/books/{book_id}")).status_code == 204

    @pytest.mark.asyncio
    async def test_delete_non_existing_204(self, client):
        # Idempotent — returns 204 even if not found
        assert (await client.delete("/books/000000000000000000000001")).status_code == 204

    @pytest.mark.asyncio
    async def test_delete_removes_book(self, seeded_client):
        r = await seeded_client.get("/books/?limit=1")
        book_id = r.json()["items"][0]["id"]
        await seeded_client.delete(f"/books/{book_id}")
        assert (await seeded_client.get(f"/books/{book_id}")).status_code == 404
