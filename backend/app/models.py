import uuid
from datetime import date, datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base
from app.enums import (
    ApplicationSource,
    ApplicationStatus,
    AuditAction,
    EmailSignalType,
    EventType,
    MatchStatus,
    ProposalStatus,
)


def _uuid() -> str:
    return str(uuid.uuid4())


def _sql_in_list(*enums) -> str:
    """Build a SQL 'val1','val2',... literal list from one or more enum
    classes, so CHECK constraints can never drift out of sync with the
    Python-side enum they're meant to mirror."""
    values = [member.value for enum_cls in enums for member in enum_cls]
    return ", ".join(f"'{v}'" for v in values)


_APPLICATION_STATUS_LIST = _sql_in_list(ApplicationStatus)
_APPLICATION_SOURCE_LIST = _sql_in_list(ApplicationSource)
_EMAIL_SIGNAL_TYPE_LIST = _sql_in_list(EmailSignalType)
_MATCH_STATUS_LIST = _sql_in_list(MatchStatus)
_PROPOSAL_STATUS_LIST = _sql_in_list(ProposalStatus)


# JSONB is Postgres-only; fall back to generic JSON so tests can run on
# SQLite without a separate schema.
def _json_type():
    from app.config import settings

    if settings.database_url.startswith("sqlite"):
        return JSON
    return JSONB


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_APPLICATION_STATUS_LIST})", name="ck_applications_status_valid"
        ),
        CheckConstraint(
            f"source IN ({_APPLICATION_SOURCE_LIST})", name="ck_applications_source_valid"
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=_uuid,
    )
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ApplicationStatus.SAVED.value, index=True
    )
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ApplicationSource.MANUAL.value
    )
    applied_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    events: Mapped[list["ApplicationEvent"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="ApplicationEvent.created_at",
    )


class ApplicationEvent(Base):
    """Append-only, user-facing timeline: 'what happened to this application'."""

    __tablename__ = "application_events"
    __table_args__ = (
        CheckConstraint(
            f"from_status IS NULL OR from_status IN ({_APPLICATION_STATUS_LIST})",
            name="ck_application_events_from_status_valid",
        ),
        CheckConstraint(
            f"to_status IS NULL OR to_status IN ({_APPLICATION_STATUS_LIST})",
            name="ck_application_events_to_status_valid",
        ),
        CheckConstraint(
            f"source IN ({_APPLICATION_SOURCE_LIST})",
            name="ck_application_events_source_valid",
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=_uuid,
    )
    application_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False).with_variant(String(36), "sqlite"),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ApplicationSource.MANUAL.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    application: Mapped["Application"] = relationship(back_populates="events")


class AuditLog(Base):
    """System-facing, stricter trail of state changes: who/what/why.

    Kept separate from ApplicationEvent (the user-facing timeline) so the
    timeline stays clean while this stays exhaustive. Every mutation to an
    application should produce exactly one AuditLog row.
    """

    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=_uuid,
    )
    application_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False).with_variant(String(36), "sqlite"),
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor: Mapped[str] = mapped_column(String(64), nullable=False, default="user")
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict | None] = mapped_column(_json_type(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class EmailEvent(Base):
    """A single ingested recruiting email, after classification/matching.

    Privacy note: we deliberately do NOT store the full email body. Only a
    short, truncated excerpt is kept (see `body_excerpt`) — enough to show
    the user *why* something was classified a certain way, not a full copy
    of their inbox. `message_id` is unique so re-ingesting the same email
    (e.g. a retried webhook) is a no-op rather than a duplicate proposal.
    """

    __tablename__ = "email_events"
    __table_args__ = (
        UniqueConstraint("message_id", name="uq_email_events_message_id"),
        CheckConstraint(
            f"signal_type IN ({_EMAIL_SIGNAL_TYPE_LIST})",
            name="ck_email_events_signal_type_valid",
        ),
        CheckConstraint(
            f"match_status IN ({_MATCH_STATUS_LIST})", name="ck_email_events_match_status_valid"
        ),
        CheckConstraint(
            "classification_confidence >= 0 AND classification_confidence <= 1",
            name="ck_email_events_confidence_range",
        ),
        CheckConstraint(
            "length(body_excerpt) <= 300", name="ck_email_events_body_excerpt_maxlen"
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=_uuid,
    )
    message_id: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    from_address: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(998), nullable=False)
    body_excerpt: Mapped[str | None] = mapped_column(String(300), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    signal_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=EmailSignalType.UNKNOWN.value
    )
    classification_confidence: Mapped[float] = mapped_column(nullable=False, default=0.0)
    classification_evidence: Mapped[dict | None] = mapped_column(_json_type(), nullable=True)

    company_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    match_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=MatchStatus.UNMATCHED.value
    )
    matched_application_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False).with_variant(String(36), "sqlite"),
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class Proposal(Base):
    """A user-reviewable suggestion to change an application's status,
    generated from a matched + classified email. Never applied automatically.
    """

    __tablename__ = "proposals"
    __table_args__ = (
        UniqueConstraint("email_event_id", name="uq_proposals_email_event_id"),
        CheckConstraint(f"status IN ({_PROPOSAL_STATUS_LIST})", name="ck_proposals_status_valid"),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_proposals_confidence_range"
        ),
        CheckConstraint(
            f"proposed_status IN ({_APPLICATION_STATUS_LIST})",
            name="ck_proposals_proposed_status_valid",
        ),
        CheckConstraint(
            f"status_at_proposal IN ({_APPLICATION_STATUS_LIST})",
            name="ck_proposals_status_at_proposal_valid",
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=_uuid,
    )
    application_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False).with_variant(String(36), "sqlite"),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email_event_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False).with_variant(String(36), "sqlite"),
        ForeignKey("email_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    proposed_status: Mapped[str] = mapped_column(String(32), nullable=False)
    status_at_proposal: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False, default=0.0)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ProposalStatus.PENDING.value, index=True
    )
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    application: Mapped["Application"] = relationship()
    email_event: Mapped["EmailEvent"] = relationship()
