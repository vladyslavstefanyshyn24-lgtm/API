import sys, os, pytest, pytest_asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from database import Base, get_db
from main import app
from models.book_model import Book, BookStatus
from repository.book_repository import BookRepository
from schemas.book_schema import BookCreate
from services.book_service import BookService

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

@pytest_asyncio.fixture(scope="function")
async def db_session():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestSessionLocal() as session:
        yield session
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture(scope="function")
async def seeded_session(db_session):
    books = [
        Book(id="uuid-1", title="Кобзар", author="Тарас Шевченко", description="Поезії", status=BookStatus.AVAILABLE, year=1840),
        Book(id="uuid-2", title="Місто", author="Валер'ян Підмогильний", description="Роман", status=BookStatus.ISSUED, year=1928),
        Book(id="uuid-3", title="Захар Беркут", author="Іван Франко", description="Повість", status=BookStatus.AVAILABLE, year=1882),
        Book(id="uuid-4", title="Тіні забутих предків", author="Михайло Коцюбинський", description="Повість", status=BookStatus.AVAILABLE, year=1911),
        Book(id="uuid-5", title="Земля", author="Ольга Кобилянська", description="Роман", status=BookStatus.ISSUED, year=1902),
    ]
    db_session.add_all(books)
    await db_session.commit()
    yield db_session

@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    async def override():
        yield db_session
    app.dependency_overrides[get_db] = override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest_asyncio.fixture(scope="function")
async def seeded_client(seeded_session):
    async def override():
        yield seeded_session
    app.dependency_overrides[get_db] = override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class TestBookRepository:

    @pytest.mark.asyncio
    async def test_get_all_returns_all_books(self, seeded_session):
        repo = BookRepository(seeded_session)
        books, next_cursor, has_more = await repo.get_all(limit=10)
        assert len(books) == 5
        assert has_more is False
        assert next_cursor is None

    @pytest.mark.asyncio
    async def test_cursor_first_page(self, seeded_session):
        repo = BookRepository(seeded_session)
        books, next_cursor, has_more = await repo.get_all(limit=2)
        assert len(books) == 2
        assert has_more is True
        assert next_cursor == books[-1].id

    @pytest.mark.asyncio
    async def test_cursor_second_page_no_overlap(self, seeded_session):
        repo = BookRepository(seeded_session)
        books1, cursor1, _ = await repo.get_all(limit=2)
        books2, _, _ = await repo.get_all(limit=2, cursor=cursor1)
        assert {b.id for b in books1}.isdisjoint({b.id for b in books2})

    @pytest.mark.asyncio
    async def test_cursor_last_page_has_more_false(self, seeded_session):
        repo = BookRepository(seeded_session)
        _, c1, _ = await repo.get_all(limit=2)
        _, c2, _ = await repo.get_all(limit=2, cursor=c1)
        books3, c3, has_more3 = await repo.get_all(limit=2, cursor=c2)
        assert len(books3) == 1
        assert has_more3 is False
        assert c3 is None

    @pytest.mark.asyncio
    async def test_cursor_covers_all_records(self, seeded_session):
        repo = BookRepository(seeded_session)
        all_ids, cursor = set(), None
        while True:
            books, cursor, has_more = await repo.get_all(limit=2, cursor=cursor)
            all_ids.update(b.id for b in books)
            if not has_more:
                break
        assert all_ids == {"uuid-1", "uuid-2", "uuid-3", "uuid-4", "uuid-5"}

    @pytest.mark.asyncio
    async def test_filter_by_status_available(self, seeded_session):
        repo = BookRepository(seeded_session)
        books, _, _ = await repo.get_all(status=BookStatus.AVAILABLE, limit=10)
        assert len(books) == 3
        assert all(b.status == BookStatus.AVAILABLE for b in books)

    @pytest.mark.asyncio
    async def test_filter_by_author_partial(self, seeded_session):
        repo = BookRepository(seeded_session)
        books, _, _ = await repo.get_all(author="франко", limit=10)
        assert len(books) == 1
        assert books[0].author == "Іван Франко"

    @pytest.mark.asyncio
    async def test_sort_by_year_asc(self, seeded_session):
        repo = BookRepository(seeded_session)
        books, _, _ = await repo.get_all(sort_by="year", sort_order="asc", limit=10)
        years = [b.year for b in books]
        assert years == sorted(years)

    @pytest.mark.asyncio
    async def test_sort_by_title_desc(self, seeded_session):
        repo = BookRepository(seeded_session)
        books, _, _ = await repo.get_all(sort_by="title", sort_order="desc", limit=10)
        titles = [b.title for b in books]
        assert titles == sorted(titles, reverse=True)

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, seeded_session):
        repo = BookRepository(seeded_session)
        book = await repo.get_by_id("uuid-1")
        assert book is not None and book.title == "Кобзар"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, seeded_session):
        assert await BookRepository(seeded_session).get_by_id("nope") is None

    @pytest.mark.asyncio
    async def test_create_book(self, db_session):
        book = await BookRepository(db_session).create({"title": "X", "author": "Y", "description": None, "status": BookStatus.AVAILABLE, "year": 2024})
        await db_session.commit()
        assert len(book.id) == 36

    @pytest.mark.asyncio
    async def test_delete_existing(self, seeded_session):
        repo = BookRepository(seeded_session)
        await repo.delete("uuid-1")
        await seeded_session.commit()
        assert await repo.get_by_id("uuid-1") is None

    @pytest.mark.asyncio
    async def test_delete_idempotent(self, seeded_session):
        repo = BookRepository(seeded_session)
        await repo.delete("uuid-1")
        await seeded_session.commit()
        await repo.delete("uuid-1")
        await seeded_session.commit()


class TestBookService:

    def _svc(self, s): return BookService(BookRepository(s))

    @pytest.mark.asyncio
    async def test_get_all_cursor_response_shape(self, seeded_session):
        r = await self._svc(seeded_session).get_all_books(limit=10)
        assert len(r.items) == 5
        assert r.has_more is False
        assert r.next_cursor is None

    @pytest.mark.asyncio
    async def test_cursor_pagination_no_overlap(self, seeded_session):
        svc = self._svc(seeded_session)
        p1 = await svc.get_all_books(limit=2)
        p2 = await svc.get_all_books(limit=2, cursor=p1.next_cursor)
        assert {b.id for b in p1.items}.isdisjoint({b.id for b in p2.items})

    @pytest.mark.asyncio
    async def test_get_book_by_id_found(self, seeded_session):
        book = await self._svc(seeded_session).get_book_by_id("uuid-3")
        assert book.author == "Іван Франко"

    @pytest.mark.asyncio
    async def test_get_book_by_id_not_found(self, seeded_session):
        assert await self._svc(seeded_session).get_book_by_id("x") is None

    @pytest.mark.asyncio
    async def test_create_book_generates_uuid(self, db_session):
        created = await self._svc(db_session).create_book(BookCreate(title="X", author="Y", year=2020))
        assert len(created.id) == 36

    @pytest.mark.asyncio
    async def test_delete_idempotent(self, seeded_session):
        svc = self._svc(seeded_session)
        await svc.delete_book("uuid-1")
        await seeded_session.commit()
        await svc.delete_book("uuid-1")


class TestBooksAPI:

    @pytest.mark.asyncio
    async def test_get_all_200_shape(self, seeded_client):
        r = await seeded_client.get("/books/")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data and "next_cursor" in data and "has_more" in data
        assert len(data["items"]) == 5

    @pytest.mark.asyncio
    async def test_get_all_empty(self, client):
        r = await client.get("/books/")
        assert r.status_code == 200
        assert r.json()["items"] == []
        assert r.json()["has_more"] is False

    @pytest.mark.asyncio
    async def test_cursor_first_page(self, seeded_client):
        r = await seeded_client.get("/books/?limit=2")
        data = r.json()
        assert len(data["items"]) == 2
        assert data["has_more"] is True
        assert data["next_cursor"] is not None

    @pytest.mark.asyncio
    async def test_cursor_next_page_no_overlap(self, seeded_client):
        r1 = await seeded_client.get("/books/?limit=2")
        cursor = r1.json()["next_cursor"]
        r2 = await seeded_client.get(f"/books/?limit=2&cursor={cursor}")
        assert r2.status_code == 200
        assert {b["id"] for b in r1.json()["items"]}.isdisjoint({b["id"] for b in r2.json()["items"]})

    @pytest.mark.asyncio
    async def test_cursor_traverse_all(self, seeded_client):
        all_ids, cursor = set(), None
        while True:
            url = "/books/?limit=2" + (f"&cursor={cursor}" if cursor else "")
            r = await seeded_client.get(url)
            data = r.json()
            all_ids.update(b["id"] for b in data["items"])
            if not data["has_more"]:
                break
            cursor = data["next_cursor"]
        assert len(all_ids) == 5

    @pytest.mark.asyncio
    async def test_limit_0_422(self, seeded_client):
        assert (await seeded_client.get("/books/?limit=0")).status_code == 422

    @pytest.mark.asyncio
    async def test_limit_over_100_422(self, seeded_client):
        assert (await seeded_client.get("/books/?limit=200")).status_code == 422

    @pytest.mark.asyncio
    async def test_filter_by_status(self, seeded_client):
        r = await seeded_client.get("/books/?status=available")
        assert all(b["status"] == "available" for b in r.json()["items"])

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
    async def test_invalid_sort_422(self, seeded_client):
        assert (await seeded_client.get("/books/?sort_by=invalid")).status_code == 422

    @pytest.mark.asyncio
    async def test_get_by_id_200(self, seeded_client):
        r = await seeded_client.get("/books/uuid-1")
        assert r.status_code == 200 and r.json()["title"] == "Кобзар"

    @pytest.mark.asyncio
    async def test_get_by_id_404(self, seeded_client):
        assert (await seeded_client.get("/books/nope")).status_code == 404

    @pytest.mark.asyncio
    async def test_create_201(self, client):
        r = await client.post("/books/", json={"title": "X", "author": "Y", "year": 2022})
        assert r.status_code == 201 and len(r.json()["id"]) == 36

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
        assert (await seeded_client.delete("/books/uuid-1")).status_code == 204

    @pytest.mark.asyncio
    async def test_delete_idempotent_204(self, seeded_client):
        await seeded_client.delete("/books/uuid-2")
        assert (await seeded_client.delete("/books/uuid-2")).status_code == 204

    @pytest.mark.asyncio
    async def test_delete_non_existing_204(self, client):
        assert (await client.delete("/books/fake")).status_code == 204

    @pytest.mark.asyncio
    async def test_delete_removes_book(self, seeded_client):
        await seeded_client.delete("/books/uuid-3")
        assert (await seeded_client.get("/books/uuid-3")).status_code == 404
