from pydantic import BaseModel, Field, field_validator
from typing import Optional
from models.book_model import BookStatus
from datetime import datetime


class BookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Назва книги")
    author: str = Field(..., min_length=1, max_length=255, description="Автор книги")
    description: Optional[str] = Field(None, max_length=2000, description="Опис книги")
    status: BookStatus = Field(default=BookStatus.AVAILABLE, description="Статус книги")
    year: int = Field(..., ge=1, le=datetime.now().year, description="Рік випуску")

    @field_validator("title", "author")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Поле не може бути порожнім або складатися лише з пробілів")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Назва книги",
                "author": "Ім'я Автора",
                "description": "Короткий опис книги.",
                "status": "available",
                "year": 2020,
            }
        }
    }


class BookResponse(BaseModel):
    id: str
    title: str
    author: str
    description: Optional[str]
    status: BookStatus
    year: int

    model_config = {"from_attributes": True}


class BookListResponse(BaseModel):
    total: int
    books: list[BookResponse]
