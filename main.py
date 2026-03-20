import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from database import create_tables
from api.books import router as books_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield


app = FastAPI(
    title="Library API",
    description="REST API для управління бібліотекою книг (PostgreSQL + SQLAlchemy)",
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(books_router, prefix="/books", tags=["books"])


@app.get("/", tags=["root"])
async def root():
    return {"message": "Library API v2 is running 📚"}
