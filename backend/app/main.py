from fastapi import FastAPI

from app.routers import applications, emails, extraction, proposals

# Schema is owned by Alembic migrations (see migrations/), applied via
# `alembic upgrade head` before the server starts — not created here.
app = FastAPI(
    title="Application Signal Hub API",
    description="Privacy-first job application tracker.",
    version="0.1.0",
)

app.include_router(applications.router)
app.include_router(emails.router)
app.include_router(extraction.router)
app.include_router(proposals.router)


@app.get("/health")
def health():
    return {"status": "ok"}
