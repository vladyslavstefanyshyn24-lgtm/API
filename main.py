import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contextlib import asynccontextmanager
from fastapi import FastAPI
import database
from api.books import router as books_router
from api.auth import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.client = database.get_client()
    yield
    database.client.close()


app = FastAPI(
    title="Library API",
    description=(
        "REST API для управління бібліотекою книг (FastAPI + MongoDB + JWT).\n\n"
    ),
    version="4.0.0",
    lifespan=lifespan,
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(books_router, prefix="/books", tags=["books"])


@app.get("/", tags=["root"])
async def root():
    return {"message": "Library API v4 is running 📚 (MongoDB + JWT)"}
