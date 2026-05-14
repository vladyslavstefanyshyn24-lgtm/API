import enum
from typing import Optional
from pydantic import BaseModel, Field
from pydantic_mongo import PydanticObjectId


class BookStatus(str, enum.Enum):
    AVAILABLE = "available"
    ISSUED = "issued"


class BookDocument(BaseModel):
    """Represents a book document as stored in MongoDB."""

    id: Optional[PydanticObjectId] = Field(None, alias="_id")
    title: str
    author: str
    description: Optional[str] = None
    status: BookStatus = BookStatus.AVAILABLE
    year: int

    model_config = {"populate_by_name": True}
