from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.enums import ApplicationSource, ApplicationStatus
from app.schemas import (
    ApplicationCreate,
    ApplicationDetailRead,
    ApplicationListResponse,
    ApplicationRead,
    ApplicationUpdate,
)

router = APIRouter(prefix="/applications", tags=["applications"])


@router.post("", response_model=ApplicationRead, status_code=201)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db)):
    return crud.create_application(db, payload)


@router.get("", response_model=ApplicationListResponse)
def list_applications(
    status: ApplicationStatus | None = None,
    company: str | None = None,
    source: ApplicationSource | None = None,
    q: str | None = Query(default=None, description="Free-text search across company/role/notes"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    items, total = crud.list_applications(
        db, status=status, company=company, source=source, q=q, limit=limit, offset=offset
    )
    return ApplicationListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{application_id}", response_model=ApplicationDetailRead)
def get_application(application_id: str, db: Session = Depends(get_db)):
    application = crud.get_application(db, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


@router.patch("/{application_id}", response_model=ApplicationRead)
def update_application(
    application_id: str, payload: ApplicationUpdate, db: Session = Depends(get_db)
):
    application = crud.get_application(db, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return crud.update_application(db, application, payload)


@router.delete("/{application_id}", status_code=204)
def delete_application(application_id: str, db: Session = Depends(get_db)):
    application = crud.get_application(db, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    crud.delete_application(db, application)
