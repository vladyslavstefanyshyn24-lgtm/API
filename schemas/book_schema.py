from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from models.book_model import BookStatus


class BookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Назва книги")
    author: str = Field(..., min_length=1, max_length=255, description="Автор книги")
    description: Optional[str] = Field(None, max_length=2000, description="Опис книги")
    status: BookStatus = Field(default=BookStatus.AVAILABLE, description="Статус книги")
    year: int = Field(..., ge=1, le=datetime.now().year, description="Рік випуску")

    @field_validator("title", "author")
    @classmethod
    def strip_and_validate(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Поле не може бути порожнім або складатися лише з пробілів")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Кобзар",
                "author": "Тарас Шевченко",
                "description": "Збірка поезій",
                "status": "available",
                "year": 1840,
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


class PaginatedBooksResponse(BaseModel):
    """
    Limit-Offset пагінація.
    Передавай ?limit=10&offset=0 для першої сторінки,
    ?limit=10&offset=10 для другої і т.д.
    """
    items: list[BookResponse]
    total: int
    limit: int
    offset: int
    has_more: bool
