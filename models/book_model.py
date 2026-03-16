from enum import Enum
from typing import List, Dict

class BookStatus(str, Enum):
    AVAILABLE = "available"
    ISSUED = "issued"


books_db: List[Dict] = [
    {
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "title": "Кобзар",
        "author": "Тарас Шевченко",
        "description": "Збірка поетичних творів Тараса Шевченка.",
        "status": BookStatus.AVAILABLE,
        "year": 1840,
    },
    {
        "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
        "title": "Тіні забутих предків",
        "author": "Михайло Коцюбинський",
        "description": "Повість про гуцульське життя та кохання.",
        "status": BookStatus.ISSUED,
        "year": 1911,
    },
    {
        "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
        "title": "Місто",
        "author": "Валер'ян Підмогильний",
        "description": "Роман про молодого українця, який приїжджає до Києва.",
        "status": BookStatus.AVAILABLE,
        "year": 1928,
    },
]
