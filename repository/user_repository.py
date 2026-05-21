from typing import Optional
from motor.motor_asyncio import AsyncIOMotorCollection
from pydantic_mongo import PydanticObjectId
import bcrypt


class UserRepository:

    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    # ── password helpers ──────────────────────────────────────────────────────

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        return bcrypt.checkpw(plain.encode(), hashed.encode())

    # ── CRUD ──────────────────────────────────────────────────────────────────

    async def get_by_username(self, username: str) -> Optional[dict]:
        doc = await self.collection.find_one({"username": username})
        if doc is None:
            return None
        doc["id"] = str(doc.pop("_id"))
        return doc

    async def get_by_id(self, user_id: str) -> Optional[dict]:
        try:
            doc = await self.collection.find_one({"_id": PydanticObjectId(user_id)})
        except Exception:
            return None
        if doc is None:
            return None
        doc["id"] = str(doc.pop("_id"))
        return doc

    async def create(self, username: str, password: str) -> dict:
        hashed = self.hash_password(password)
        result = await self.collection.insert_one(
            {"username": username, "password": hashed}
        )
        doc = await self.collection.find_one({"_id": result.inserted_id})
        doc["id"] = str(doc.pop("_id"))
        return doc
