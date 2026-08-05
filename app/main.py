"""
App entrypoint. Route logic lives in app/routers/. Deliberately does NOT
call Base.metadata.create_all() here — the schema is built and evolved
entirely through Alembic migrations (`alembic upgrade head`).
"""
from fastapi import FastAPI

from app.routers import notes

app = FastAPI(title="Notes API")

app.include_router(notes.router)


@app.get("/health")
def healthcheck() -> dict:
    return {"status": "ok"}
