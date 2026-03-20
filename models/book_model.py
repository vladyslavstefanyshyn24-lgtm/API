import uuid
import enum
from sqlalchemy import String, Integer, Enum as SAEnum, Text
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class BookStatus(str, enum.Enum):
    AVAILABLE = "available"
    ISSUED = "issued"


class Book(Base):
    __tablename__ = "books"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[BookStatus] = mapped_column(
        SAEnum(BookStatus), nullable=False, default=BookStatus.AVAILABLE
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"<Book id={self.id} title={self.title!r}>"
