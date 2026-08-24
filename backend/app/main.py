from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import applications, emails, extraction, proposals

# Schema is owned by Alembic migrations (see migrations/), applied via
# `alembic upgrade head` before the server starts — not created here.
app = FastAPI(
    title="Application Signal Hub API",
    description="Privacy-first job application tracker.",
    version="0.1.0",
)

# The dashboard (dashboard/) is a plain static page served from its own
# origin (localhost:8080), not an extension context — it doesn't get the
# host_permissions CORS exemption the browser extension has, so it needs
# an explicit allow. Scoped to just that origin, not "*".
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)

app.include_router(applications.router)
app.include_router(emails.router)
app.include_router(extraction.router)
app.include_router(proposals.router)


@app.get("/health")
def health():
    return {"status": "ok"}
