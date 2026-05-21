from typing import Optional
from motor.motor_asyncio import AsyncIOMotorCollection
from pydantic_mongo import PydanticObjectId

from models.book_model import BookDocument, BookStatus
from schemas.book_schema import BookCreate


def _build_filter(
    status: Optional[BookStatus] = None,
    author: Optional[str] = None,
) -> dict:
    query: dict = {}
    if status is not None:
        query["status"] = status.value
    if author is not None:
        query["author"] = {"$regex": author, "$options": "i"}
    return query


def _build_sort(sort_by: Optional[str], sort_order: str) -> list[tuple[str, int]]:
    direction = 1 if sort_order == "asc" else -1
    field_map = {"title": "title", "year": "year"}
    field = field_map.get(sort_by or "", None)
    if field:
        return [(field, direction), ("_id", 1)]
    return [("_id", 1)]


def _doc_to_response(doc: dict) -> dict:
    """Convert a raw MongoDB document to a serialisable dict."""
    doc["id"] = str(doc.pop("_id"))
    return doc


class BookRepository:

    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def get_all(
        self,
        status: Optional[BookStatus] = None,
        author: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[list[dict], int]:

        query = _build_filter(status, author)
        sort = _build_sort(sort_by, sort_order)

        total = await self.collection.count_documents(query)

        cursor = self.collection.find(query).sort(sort).skip(offset).limit(limit)
        books = [_doc_to_response(doc) async for doc in cursor]

        return books, total

    async def get_by_id(self, book_id: str) -> Optional[dict]:
        doc = await self.collection.find_one({"_id": PydanticObjectId(book_id)})
        if doc is None:
            return None
        return _doc_to_response(doc)

    async def create(self, book_data: BookCreate) -> dict:
        payload = book_data.model_dump()
        result = await self.collection.insert_one(payload)
        doc = await self.collection.find_one({"_id": result.inserted_id})
        return _doc_to_response(doc)

    async def delete(self, book_id: str) -> bool:
        """Returns True if the document existed and was deleted."""
        try:
            response = await self.collection.delete_one(
                {"_id": PydanticObjectId(book_id)}
            )
        except Exception:
            return False
        return response.deleted_count > 0
