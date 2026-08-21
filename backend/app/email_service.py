"""Orchestrates email ingestion: dedup -> classify -> match -> propose.

This is intentionally synchronous for Phase 3 (no queue yet — that's
Phase 5). Kept as its own module rather than folded into crud.py because
it composes multiple concerns (classifier, matcher, application CRUD)
rather than being a single table's data-access layer.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.classifier import classify_email
from app.enums import SIGNAL_TO_STATUS, EmailSignalType, MatchStatus, ProposalStatus
from app.matcher import extract_company_hint, match_application
from app.models import Application, EmailEvent, Proposal
from app.schemas import EmailIngestRequest
from app.transitions import InvalidTransitionError

_BODY_EXCERPT_LEN = 300


@dataclass
class IngestResult:
    email_event: EmailEvent
    proposal: Proposal | None
    message: str
    was_duplicate: bool = False


def ingest_email(db: Session, data: EmailIngestRequest) -> IngestResult:
    existing = db.execute(
        select(EmailEvent).where(EmailEvent.message_id == data.message_id)
    ).scalar_one_or_none()
    if existing is not None:
        # Idempotent: re-ingesting the same email_message (e.g. a retried
        # webhook delivery) is a no-op, not a duplicate proposal.
        existing_proposal = None
        if existing.matched_application_id:
            existing_proposal = db.execute(
                select(Proposal).where(Proposal.email_event_id == existing.id)
            ).scalar_one_or_none()
        return IngestResult(
            email_event=existing,
            proposal=existing_proposal,
            message="Duplicate message_id — email already processed, no new proposal created.",
            was_duplicate=True,
        )

    classification = classify_email(data.subject, data.body)
    company_hint = extract_company_hint(data.from_address, data.subject)
    match = match_application(db, company_hint)

    email_event = EmailEvent(
        message_id=data.message_id,
        from_address=data.from_address,
        subject=data.subject,
        body_excerpt=(data.body or "")[:_BODY_EXCERPT_LEN],
        received_at=data.received_at,
        signal_type=classification.signal_type.value,
        classification_confidence=classification.confidence,
        classification_evidence={"matched_phrases": classification.matched_phrases},
        company_hint=match.company_hint,
        match_status=match.status.value,
        matched_application_id=(
            match.application.id if match.status == MatchStatus.MATCHED else None
        ),
    )
    db.add(email_event)
    db.flush()

    proposal: Proposal | None = None
    message: str

    if classification.signal_type == EmailSignalType.UNKNOWN:
        message = "Email did not match any known signal type — no proposal created."
    elif match.status != MatchStatus.MATCHED:
        message = (
            f"Signal classified as '{classification.signal_type.value}' but application "
            f"match was '{match.status.value}' — no proposal created (avoiding a guess)."
        )
    else:
        proposal = _create_proposal(db, email_event, match.application, classification)
        message = "Proposal created for review."

    db.commit()
    db.refresh(email_event)
    if proposal is not None:
        db.refresh(proposal)

    return IngestResult(email_event=email_event, proposal=proposal, message=message)


def _create_proposal(
    db: Session, email_event: EmailEvent, application: Application, classification
) -> Proposal:
    proposed_status = SIGNAL_TO_STATUS[classification.signal_type]
    evidence_bits = [f"matched phrase(s): {', '.join(classification.matched_phrases)}"]
    if email_event.company_hint:
        evidence_bits.append(f"sender/subject company hint: '{email_event.company_hint}'")

    proposal = Proposal(
        application_id=application.id,
        email_event_id=email_event.id,
        proposed_status=proposed_status.value,
        status_at_proposal=application.status,
        confidence=classification.confidence,
        evidence="; ".join(evidence_bits),
        status=ProposalStatus.PENDING.value,
    )
    db.add(proposal)
    db.flush()
    return proposal


def approve_proposal(db: Session, proposal: Proposal, force: bool = False) -> Proposal:
    from app import crud
    from app.enums import ApplicationStatus
    from app.schemas import ApplicationUpdate

    if proposal.status != ProposalStatus.PENDING.value:
        raise ValueError(f"Proposal is already '{proposal.status}', cannot approve again.")

    application = db.get(Application, proposal.application_id)
    if application is None:
        raise ValueError("The application this proposal refers to no longer exists.")

    try:
        crud.update_application(
            db,
            application,
            ApplicationUpdate(status=ApplicationStatus(proposal.proposed_status)),
            force=force,
        )
    except InvalidTransitionError:
        # Leave the proposal pending — surface the conflict to the caller
        # rather than silently dropping or force-applying it.
        raise

    proposal.status = ProposalStatus.APPROVED.value
    proposal.decided_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(proposal)
    return proposal


def reject_proposal(db: Session, proposal: Proposal, note: str | None = None) -> Proposal:
    if proposal.status != ProposalStatus.PENDING.value:
        raise ValueError(f"Proposal is already '{proposal.status}', cannot reject again.")

    proposal.status = ProposalStatus.REJECTED.value
    proposal.decision_note = note
    proposal.decided_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(proposal)
    return proposal
