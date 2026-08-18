from fastapi import FastAPI

from app.database import Base, engine
from app.routers import applications

# Phase 1: create tables directly on startup for dev convenience.
# Once schema changes get more frequent (Phase 3+), switch to Alembic
# migrations exclusively and drop this.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Application Signal Hub API",
    description="Privacy-first job application tracker.",
    version="0.1.0",
)

app.include_router(applications.router)


@app.get("/health")
def health():
    return {"status": "ok"}
