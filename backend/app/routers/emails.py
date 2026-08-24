from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import email_service
from app.database import get_db
from app.enums import EmailSignalType, MatchStatus
from app.models import EmailEvent
from app.schemas import EmailEventRead, EmailIngestRequest, EmailIngestResponse

router = APIRouter(prefix="/email-events", tags=["email-events"])


@router.post("/ingest", response_model=EmailIngestResponse, status_code=201)
def ingest_email(payload: EmailIngestRequest, db: Session = Depends(get_db)):
    result = email_service.ingest_email(db, payload)
    return EmailIngestResponse(
        email_event=result.email_event, proposal=result.proposal, message=result.message
    )


@router.get("", response_model=list[EmailEventRead])
def list_email_events(
    signal_type: EmailSignalType | None = None,
    match_status: MatchStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(EmailEvent)
    if signal_type is not None:
        query = query.filter(EmailEvent.signal_type == signal_type.value)
    if match_status is not None:
        query = query.filter(EmailEvent.match_status == match_status.value)
    return (
        query.order_by(EmailEvent.created_at.desc()).limit(limit).offset(offset).all()
    )


@router.get("/{email_event_id}", response_model=EmailEventRead)
def get_email_event(email_event_id: UUID, db: Session = Depends(get_db)):
    event = db.get(EmailEvent, str(email_event_id))
    if event is None:
        raise HTTPException(status_code=404, detail="Email event not found")
    return event
