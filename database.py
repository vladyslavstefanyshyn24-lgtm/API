import motor.motor_asyncio
from config import settings

client: motor.motor_asyncio.AsyncIOMotorClient | None = None


def get_client() -> motor.motor_asyncio.AsyncIOMotorClient:
    return motor.motor_asyncio.AsyncIOMotorClient(settings.MONGO_URL)


def get_database(mongo_client: motor.motor_asyncio.AsyncIOMotorClient | None = None):
    c = mongo_client or client
    return c[settings.MONGO_DB]


async def get_books_collection(mongo_client=None):
    db = get_database(mongo_client)
    yield db["books"]
