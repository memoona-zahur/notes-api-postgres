"""
App entrypoint. Route logic lives in app/routers/. Deliberately does NOT
call Base.metadata.create_all() here — the schema is built and evolved
entirely through Alembic migrations (`alembic upgrade head`), per the
assignment's requirement. See README's setup steps for the correct order.
"""
from fastapi import FastAPI

from app.routers import auth, notes, admin

app = FastAPI(title="Notes API")

app.include_router(auth.router)
app.include_router(notes.router)
app.include_router(admin.router)


@app.get("/")
def root() -> dict:
    return {"name": "Notes API", "docs": "/docs", "health": "/health", "api": "/api/v1"}


@app.get("/health")
def healthcheck() -> dict:
    return {"status": "ok"}
