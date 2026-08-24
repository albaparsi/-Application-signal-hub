from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import email_service
from app.database import get_db
from app.enums import ProposalStatus
from app.models import Proposal
from app.schemas import ProposalRead
from app.transitions import InvalidTransitionError

router = APIRouter(prefix="/proposals", tags=["proposals"])


@router.get("", response_model=list[ProposalRead])
def list_proposals(
    status: ProposalStatus | None = None,
    application_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Proposal)
    if status is not None:
        query = query.filter(Proposal.status == status.value)
    if application_id is not None:
        query = query.filter(Proposal.application_id == str(application_id))
    return (
        query.order_by(Proposal.created_at.desc()).limit(limit).offset(offset).all()
    )


@router.get("/{proposal_id}", response_model=ProposalRead)
def get_proposal(proposal_id: UUID, db: Session = Depends(get_db)):
    proposal = db.get(Proposal, str(proposal_id))
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return proposal


@router.post("/{proposal_id}/approve", response_model=ProposalRead)
def approve_proposal(
    proposal_id: UUID,
    force: bool = Query(
        default=False, description="Override transition rules when applying the proposed status"
    ),
    db: Session = Depends(get_db),
):
    proposal = db.get(Proposal, str(proposal_id))
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    try:
        return email_service.approve_proposal(db, proposal, force=force)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{proposal_id}/reject", response_model=ProposalRead)
def reject_proposal(proposal_id: UUID, note: str | None = None, db: Session = Depends(get_db)):
    proposal = db.get(Proposal, str(proposal_id))
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    try:
        return email_service.reject_proposal(db, proposal, note=note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
