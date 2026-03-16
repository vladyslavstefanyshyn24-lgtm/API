import sys
import os


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from api.books import router as books_router

app = FastAPI(
    title="Library API",
    description="REST API для управління бібліотекою книг",
    version="1.0.0",
)

app.include_router(books_router, prefix="/books", tags=["books"])


@app.get("/", tags=["root"])
async def root():
    return {"message": "Library API is running 📚"}
