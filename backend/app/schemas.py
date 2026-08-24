from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.enums import ApplicationSource, ApplicationStatus


class ApplicationCreate(BaseModel):
    company: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., min_length=1, max_length=255)
    url: str | None = Field(default=None, max_length=2048)
    location: str | None = Field(default=None, max_length=255)
    status: ApplicationStatus = ApplicationStatus.SAVED
    source: ApplicationSource = ApplicationSource.MANUAL
    applied_date: date | None = None
    notes: str | None = None


class ApplicationUpdate(BaseModel):
    """All fields optional — PATCH semantics. Any provided field is applied;
    status changes are diffed against current status to produce a timeline
    event + audit log entry in the CRUD layer."""

    company: str | None = Field(default=None, min_length=1, max_length=255)
    role: str | None = Field(default=None, min_length=1, max_length=255)
    url: str | None = Field(default=None, max_length=2048)
    location: str | None = Field(default=None, max_length=255)
    status: ApplicationStatus | None = None
    applied_date: date | None = None
    notes: str | None = None


class ApplicationEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    from_status: str | None
    to_status: str | None
    description: str | None
    source: str
    created_at: datetime


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company: str
    role: str
    url: str | None
    location: str | None
    status: str
    source: str
    applied_date: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ApplicationDetailRead(ApplicationRead):
    events: list[ApplicationEventRead] = []


class ApplicationListResponse(BaseModel):
    items: list[ApplicationRead]
    total: int
    limit: int
    offset: int


class EmailIngestRequest(BaseModel):
    """Payload representing one recruiting email. In production this would
    come from a Gmail API pull; for now it's fed synthetic/sample data."""

    message_id: str = Field(..., min_length=1, max_length=512)
    from_address: str = Field(..., min_length=3, max_length=320)
    subject: str = Field(..., max_length=998)
    body: str = Field(default="", description="Full body — used for classification, not stored")
    received_at: datetime = Field(default_factory=datetime.utcnow)


class EmailEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    message_id: str
    from_address: str
    subject: str
    body_excerpt: str | None
    received_at: datetime
    signal_type: str
    classification_confidence: float
    classification_evidence: dict | None
    company_hint: str | None
    match_status: str
    matched_application_id: str | None
    created_at: datetime


class ProposalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    application_id: str
    email_event_id: str
    proposed_status: str
    status_at_proposal: str
    confidence: float
    evidence: str | None
    status: str
    decision_note: str | None
    created_at: datetime
    decided_at: datetime | None


class EmailIngestResponse(BaseModel):
    email_event: EmailEventRead
    proposal: ProposalRead | None = None
    message: str


class ExtractionRequest(BaseModel):
    """Page context the browser extension gathered client-side, sent here
    so the LLM call (and its API key) stays server-side. Deliberately not
    a full HTML/DOM dump — just enough for the model to work with, kept
    small for cost and so incidental page content isn't shipped wholesale
    to a third-party API."""

    url: str = Field(..., max_length=2048)
    title: str = Field(default="", max_length=500)
    job_posting_hints: dict | None = Field(
        default=None, description="Trimmed schema.org JobPosting fields, if the page had any"
    )
    visible_text: str = Field(default="", max_length=6000)


class ExtractionResponse(BaseModel):
    company: str = ""
    role: str = ""
    location: str = ""
    status: ApplicationStatus = ApplicationStatus.SAVED
    method: str = Field(description="'llm' or 'heuristic' — which path produced this result")
